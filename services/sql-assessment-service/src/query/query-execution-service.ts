import { DataSource, QueryFailedError } from 'typeorm';
import { AST, Parser } from 'node-sql-parser';
import { QueryExecutionResult } from '../shared/interfaces/http';
import { t, SupportedLanguage } from '../shared/i18n';

/**
 * AST node types that can mutate data even when the statement root is a
 * SELECT — e.g. data-modifying CTEs and `SELECT ... INTO`.
 */
const MUTATING_NODE_TYPES = new Set(['insert', 'update', 'delete', 'into']);

export interface QueryExecutionServiceOptions {
	/**
	 * Run every query inside a read-only transaction so the database itself
	 * rejects writes that the AST check cannot see (e.g. `SELECT nextval(...)`
	 * or a volatile function).  Production backends (PostgreSQL and PGlite)
	 * support `SET TRANSACTION READ ONLY`; disable only for engines that do
	 * not, such as the pg-mem test adapter.
	 */
	enforceReadOnly?: boolean;
}

/**
 * Executes a raw SQL SELECT query against a live DataSource and returns the
 * result rows together with the row count.
 *
 * Responsibilities:
 *  - Validate that the query string is non-empty.
 *  - Ensure only SELECT statements are accepted (INSERT / UPDATE / DELETE /
 *    DDL are rejected before hitting the database).
 *  - Execute the query via a TypeORM QueryRunner so the DataSource lifecycle
 *    (connection pool) is respected, inside a read-only transaction.
 *  - Translate database-level errors into a structured error with a
 *    human-readable, localised message.
 */
export class QueryExecutionService {
	private readonly parser = new Parser();
	private readonly enforceReadOnly: boolean;

	constructor(options: QueryExecutionServiceOptions = {}) {
		this.enforceReadOnly = options.enforceReadOnly ?? true;
	}

	/**
	 * Executes the given SQL query and returns the rows.
	 *
	 * @param query      - Raw SQL string to execute.
	 * @param dataSource - Initialised TypeORM DataSource.
	 * @param lang       - Language for error messages (defaults to 'en').
	 *
	 * @throws {QueryExecutionError} on empty input, non-SELECT statements, or
	 *   database-level failures.
	 */
	public async executeQuery(
		query: string,
		dataSource: DataSource,
		lang: SupportedLanguage = 'en',
	): Promise<QueryExecutionResult> {
		const trimmed = query.trim();

		if (!trimmed) {
			throw new QueryExecutionError(t('QUERY_EMPTY', lang), 'EMPTY_QUERY');
		}

		this.assertSelectOnly(trimmed, lang);

		const queryRunner = dataSource.createQueryRunner();
		let inTransaction = false;
		try {
			if (this.enforceReadOnly) {
				await queryRunner.startTransaction();
				inTransaction = true;
				await queryRunner.query('SET TRANSACTION READ ONLY');
			}
			const rows: Record<string, unknown>[] = await queryRunner.query(trimmed);
			return { rows, rowCount: rows.length };
		} catch (err) {
			const detail =
				err instanceof QueryFailedError
					? (err.driverError?.message ?? err.message)
					: String(err);
			throw new QueryExecutionError(
				t('QUERY_EXECUTION_FAILED', lang, detail),
				'EXECUTION_FAILED',
			);
		} finally {
			if (inTransaction) {
				await queryRunner.rollbackTransaction().catch(() => undefined);
			}
			await queryRunner.release();
		}
	}

	/**
	 * Executes the given SQL SELECT query against an in-process PGlite
	 * database.  Enforces the same SELECT-only constraint as `executeQuery`.
	 *
	 * PGlite serialises `db.transaction()` calls internally, so the shared
	 * instance can safely hold a short-lived read-only transaction.
	 *
	 * @param query - Raw SQL string to execute.
	 * @param db    - Live PGlite instance.
	 * @param lang  - Language for error messages (defaults to 'en').
	 *
	 * @throws {QueryExecutionError} on empty input, non-SELECT statements, or
	 *   database-level failures.
	 */
	public async executeQueryOnPGlite(
		query: string,
		db: any,
		lang: SupportedLanguage = 'en',
	): Promise<QueryExecutionResult> {
		const trimmed = query.trim();

		if (!trimmed) {
			throw new QueryExecutionError(t('QUERY_EMPTY', lang), 'EMPTY_QUERY');
		}

		this.assertSelectOnly(trimmed, lang);

		try {
			const result = this.enforceReadOnly
				? await db.transaction(async (tx: any) => {
					await tx.query('SET TRANSACTION READ ONLY');
					return tx.query(trimmed);
				})
				: await db.query(trimmed);
			const rows = result.rows as Record<string, unknown>[];
			return { rows, rowCount: rows.length };
		} catch (err) {
			const detail = err instanceof Error ? err.message : String(err);
			throw new QueryExecutionError(
				t('QUERY_EXECUTION_FAILED', lang, detail),
				'EXECUTION_FAILED',
			);
		}
	}

	// -------------------------------------------------------------------------
	// Private helpers
	// -------------------------------------------------------------------------

	/**
	 * Parses the SQL and throws if it is not a plain SELECT statement.
	 * Rejects multi-statement input, DDL, DML mutations, and anything that
	 * cannot be parsed as valid SQL.
	 */
	private assertSelectOnly(query: string, lang: SupportedLanguage): void {
		let ast: AST | AST[];
		try {
			ast = this.parser.astify(query, { database: 'PostgreSQL' });
		} catch {
			throw new QueryExecutionError(
				t('QUERY_PARSE_ERROR', lang),
				'PARSE_ERROR',
			);
		}

		// node-sql-parser returns an array both for multi-statement input and
		// for a single statement that ends with a terminator (e.g. `SELECT 1;`).
		const statements = Array.isArray(ast) ? ast : [ast];
		if (statements.length > 1) {
			throw new QueryExecutionError(
				t('QUERY_MULTIPLE_STATEMENTS', lang),
				'MULTIPLE_STATEMENTS',
			);
		}

		const statement = statements[0];
		if (!statement || statement.type !== 'select') {
			const type = statement?.type ?? 'unknown';
			throw new QueryExecutionError(
				t('QUERY_NON_SELECT', lang, type),
				'NON_SELECT',
			);
		}

		this.assertNoMutations(statement, lang);
	}

	/**
	 * Rejects mutations that hide beneath a SELECT root: data-modifying CTEs
	 * (`WITH ... AS (UPDATE ...) SELECT ...`) and `SELECT ... INTO`.
	 *
	 * Walks the AST iteratively so deeply nested queries cannot overflow the
	 * call stack.  `node-sql-parser` emits `into: { type: 'into' }` only when
	 * the clause is actually present; the default `into` node has no `type`.
	 */
	private assertNoMutations(statement: AST, lang: SupportedLanguage): void {
		const stack: unknown[] = [statement];
		while (stack.length > 0) {
			const node = stack.pop();
			if (!node || typeof node !== 'object') continue;

			const { type } = node as { type?: unknown };
			if (typeof type === 'string' && MUTATING_NODE_TYPES.has(type)) {
				throw new QueryExecutionError(
					t('QUERY_NON_SELECT', lang, type),
					'NON_SELECT',
				);
			}

			for (const child of Object.values(node)) stack.push(child);
		}
	}
}

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export type QueryExecutionErrorCode =
	| 'EMPTY_QUERY'
	| 'PARSE_ERROR'
	| 'MULTIPLE_STATEMENTS'
	| 'NON_SELECT'
	| 'EXECUTION_FAILED';

export class QueryExecutionError extends Error {
	public readonly code: QueryExecutionErrorCode;

	constructor(message: string, code: QueryExecutionErrorCode) {
		super(message);
		this.name = 'QueryExecutionError';
		this.code = code;
	}
}
