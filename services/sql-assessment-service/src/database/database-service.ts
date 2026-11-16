import { DataSource } from 'typeorm';
import { PostgresConnectionOptions } from 'typeorm/driver/postgres/PostgresConnectionOptions';
import * as fs from 'fs/promises';
import { PGlite } from '@electric-sql/pglite';
import { DatabaseAnalyzer } from './database-analyzer';
import {
	connectToPostgresCandidates,
	generatePostgresDatabaseKey,
	generatePGliteKey,
} from '../shared/utils/database-utils';
import {
	isDatabaseRegistered,
	validateConnectionInfo,
} from '../shared/utils/validation';
import { t, SupportedLanguage } from '../shared/i18n';
import { IAliasMap } from '../shared/interfaces/domain';
import {
	databaseMetadata,
	pgliteInstances,
	selfJoinDatabaseMetadata,
} from './internal-memory';

/** Canonical registry key used for the single shared init-SQL PGlite instance. */
const INIT_PGLITE_ID = '__pglite_init__';

export interface AnalyzeResult {
	ok: boolean;
	status: number;
	message: string;
	databaseKey?: string;
	schema?: string;
	dataSource?: DataSource;
}

/**
 * Pure business-logic service for analyzing / registering databases.
 *
 * Used by {@link DatabaseController} to handle `/api/database/analyze-database`
 * and by the four downstream controllers to auto-analyze before their own logic.
 *
 * When {@link initSqlFilePath} is configured (via constructor, the
 * `PGLITE_INIT_SQL_FILE` environment variable, or the `--init-sql-file` CLI
 * flag), a PGlite request that carries **no** `sqlContent` field will
 * automatically fall back to reading that file as the initialisation SQL.
 */
export class DatabaseService {
	private readonly initSqlFilePath?: string;
	private cachedInitSql?: string;
	/** Single shared PGlite instance used for all init-SQL-backed databases. */
	private cachedInitSqlPGlite?: PGlite;
	/** In-flight promise for the first initialisation of {@link cachedInitSqlPGlite}. */
	private initSqlPGlitePromise?: Promise<PGlite | null>;

	constructor(
		private readonly databaseAnalyzer: DatabaseAnalyzer,
		initSqlFilePath?: string,
	) {
		this.initSqlFilePath = initSqlFilePath;
	}
	/**
	 * Ensures the database described by `connectionInfo` is analyzed and its
	 * schema metadata stored in the in-memory registry.
	 *
	 * Behaviour by connection type:
	 * - **PGlite** – always (re-)creates the in-process instance when
	 *   `sqlContent` is present.  If `sqlContent` is absent and `required` is
	 *   `false` (the default for the four downstream controllers), the call is a
	 *   no-op (assumes a prior registration is still valid for the process).
	 *   When `required` is `true` (used by the `/api/database/analyze-database`
	 *   endpoint), `sqlContent` is mandatory and its absence is an error.
	 */
	async ensureAnalyzed(
		connectionInfo: any,
		aliasMap?: IAliasMap,
		lang: SupportedLanguage = 'en',
		required = false,
		retainPostgresConnection = false,
	): Promise<AnalyzeResult> {
		if (!connectionInfo) {
			return {
				ok: false,
				status: 400,
				message: t('MISSING_CONNECTION_INFO', lang),
			};
		}

		if (connectionInfo.type === 'pglite') {
			// Resolve sqlContent: use the value from the request body first.
			const sqlContent: string | undefined = connectionInfo.sqlContent;

			// Distinguish "absent" (null/undefined) from "present but invalid"
			// (e.g. empty string). An explicitly-supplied empty string is not
			// treated as absent — it falls through to analyzePGlite, which
			// validates it and returns a 400.
			if (sqlContent == null) {
				// If the DB is already registered and the caller did not supply new
				// sqlContent, treat this as a no-op — same semantics as the PG branch.
				const databaseId: string | undefined = connectionInfo.databaseId;
				if (
					!required &&
					databaseId &&
					isDatabaseRegistered(generatePGliteKey(databaseId))
				) {
					return { ok: true, status: 200, message: 'already registered' };
				}

				// Fall back to the configured init-SQL file (if any).
				// All callers share a single PGlite instance — no per-databaseId copy.
				if (this.initSqlFilePath) {
					if (!databaseId || typeof databaseId !== 'string') {
						return {
							ok: false,
							status: 400,
							message: t('INVALID_CONNECTION_INFO', lang),
						};
					}
					return this.ensureInitSqlPGliteRegistered(databaseId, aliasMap, lang);
				}

				if (required) {
					return {
						ok: false,
						status: 400,
						message: t('INVALID_CONNECTION_INFO', lang),
					};
				}
				return { ok: true, status: 200, message: 'skipped' };
			}
			return this.analyzePGlite(
				{ ...connectionInfo, sqlContent },
				aliasMap,
				lang,
			);
		}

		// PostgreSQL – validate first so we never generate a bogus key from undefined fields.
		const pgInfo = connectionInfo as PostgresConnectionOptions;
		const validation = await validateConnectionInfo(pgInfo, lang);
		if (!validation.ok) {
			return { ok: false, status: 400, message: validation.message };
		}

		const connection = await connectToPostgresCandidates(validation.connectionInfos);
		if (!connection) {
			return { ok: false, status: 400, message: t('UNABLE_TO_CONNECT', lang) };
		}

		let retained = false;
		try {
			const databaseKey = generatePostgresDatabaseKey(
				validation.requestedHost,
				connection.connectionInfo,
			);
			let message = 'already registered';
			if (required || !isDatabaseRegistered(databaseKey)) {
				const extracted = await this.databaseAnalyzer.extractDatabaseSchema(
					connection.dataSource,
					connection.connectionInfo.schema!,
					databaseKey,
					aliasMap,
				);
				if (!extracted) {
					return {
						ok: false,
						status: 500,
						message: t('DATABASE_SCHEMA_EXTRACTION_FAILED', lang),
					};
				}
				message = t('DATABASE_ANALYSIS_SUCCESS', lang);
			}
			retained = retainPostgresConnection;
			return {
				ok: true,
				status: 200,
				message,
				databaseKey,
				schema: connection.connectionInfo.schema,
				...(retained ? { dataSource: connection.dataSource } : {}),
			};
		} finally {
			if (!retained) await connection.dataSource.destroy();
		}
	}

	// -------------------------------------------------------------------------
	// PGlite helpers
	// -------------------------------------------------------------------------

	private async analyzePGlite(
		rawInfo: any,
		aliasMap: IAliasMap | undefined,
		lang: SupportedLanguage,
	): Promise<AnalyzeResult> {
		const { databaseId, sqlContent } = rawInfo ?? {};

		if (!databaseId || typeof databaseId !== 'string') {
			return {
				ok: false,
				status: 400,
				message: t('INVALID_CONNECTION_INFO', lang),
			};
		}
		if (!sqlContent || typeof sqlContent !== 'string') {
			return {
				ok: false,
				status: 400,
				message: t('INVALID_CONNECTION_INFO', lang),
			};
		}

		// Close and evict any existing instance for this id,
		// but never close the shared init-SQL instance.
		const existing = pgliteInstances.get(databaseId);
		if (existing && existing !== this.cachedInitSqlPGlite) {
			try {
				await existing.close();
			} catch {
				/* ignore */
			}
		}
		pgliteInstances.delete(databaseId);

		let db: PGlite;
		try {
			db = new PGlite();
			await db.exec(sqlContent);
		} catch (error) {
			console.error('PGlite initialisation failed', error);
			return {
				ok: false,
				status: 500,
				message: t('DATABASE_SCHEMA_EXTRACTION_FAILED', lang),
			};
		}

		const key = generatePGliteKey(databaseId);
		const success = await this.databaseAnalyzer.extractSchemaFromPGlite(
			db,
			key,
			aliasMap,
		);

		if (!success) {
			try {
				await db.close();
			} catch {
				/* ignore */
			}
			return {
				ok: false,
				status: 500,
				message: t('DATABASE_SCHEMA_EXTRACTION_FAILED', lang),
			};
		}

		pgliteInstances.set(databaseId, db);
		return {
			ok: true,
			status: 200,
			message: t('DATABASE_ANALYSIS_SUCCESS', lang),
		};
	}

	/**
	 * Lazily creates a single shared PGlite instance from the configured init
	 * SQL file, then registers `databaseId` as an alias pointing at that shared
	 * instance.  All callers that omit `sqlContent` share the same in-memory
	 * database — no per-databaseId copy is ever created.
	 */
	private async ensureInitSqlPGliteRegistered(
		databaseId: string,
		aliasMap: IAliasMap | undefined,
		lang: SupportedLanguage,
	): Promise<AnalyzeResult> {
		// Read and cache the init SQL file.
		try {
			if (!this.cachedInitSql) {
				this.cachedInitSql = await fs.readFile(this.initSqlFilePath!, 'utf-8');
			}
		} catch (err) {
			console.error(
				`Failed to read init SQL file: ${this.initSqlFilePath}`,
				err,
			);
			return {
				ok: false,
				status: 500,
				message: t('INIT_SQL_READ_ERROR', lang),
			};
		}

		// Create the shared PGlite instance once — race-safe via a stored Promise
		// so concurrent callers coalesce onto the same initialisation rather than
		// each spawning their own PGlite instance.
		if (!this.initSqlPGlitePromise) {
			this.initSqlPGlitePromise = (async (): Promise<PGlite | null> => {
				let db: PGlite;
				try {
					db = new PGlite();
					await db.exec(this.cachedInitSql!);
				} catch (error) {
					console.error('PGlite initialisation failed', error);
					return null;
				}

				const canonicalKey = generatePGliteKey(INIT_PGLITE_ID);
				const success = await this.databaseAnalyzer.extractSchemaFromPGlite(
					db,
					canonicalKey,
					aliasMap,
				);
				if (!success) {
					try {
						await db.close();
					} catch {
						/* ignore */
					}
					return null;
				}

				return db;
			})();
		}
		const db = await this.initSqlPGlitePromise;
		if (!db) {
			// Allow future calls to retry after a failed initialisation.
			this.initSqlPGlitePromise = undefined;
			return {
				ok: false,
				status: 500,
				message: t('DATABASE_SCHEMA_EXTRACTION_FAILED', lang),
			};
		}
		this.cachedInitSqlPGlite = db;

		// Register the caller's databaseId pointing to the shared instance.
		const databaseKey = generatePGliteKey(databaseId);
		if (!databaseMetadata.has(databaseKey)) {
			const canonicalKey = generatePGliteKey(INIT_PGLITE_ID);
			databaseMetadata.set(databaseKey, databaseMetadata.get(canonicalKey)!);
			const selfJoin = selfJoinDatabaseMetadata.get(canonicalKey);
			if (selfJoin !== undefined) {
				selfJoinDatabaseMetadata.set(databaseKey, selfJoin);
			}
		}
		pgliteInstances.set(databaseId, this.cachedInitSqlPGlite);

		return {
			ok: true,
			status: 200,
			message: t('DATABASE_ANALYSIS_SUCCESS', lang),
		};
	}

}
