import { DataSource, QueryFailedError } from 'typeorm';
import { AST, Parser } from 'node-sql-parser';
import { QueryExecutionResult } from '../shared/interfaces/http';
import { t, SupportedLanguage } from '../shared/i18n';

/**
 * Executes a raw SQL SELECT query against a live DataSource and returns the
 * result rows together with the row count.
 *
 * Responsibilities:
 *  - Validate that the query string is non-empty.
 *  - Ensure only SELECT statements are accepted (INSERT / UPDATE / DELETE /
 *    DDL are rejected before hitting the database).
 *  - Execute the query via a TypeORM QueryRunner so the DataSource lifecycle
 *    (connection pool) is respected.
 *  - Translate database-level errors into a structured error with a
 *    human-readable, localised message.
 */
export class QueryExecutionService {
	private readonly parser = new Parser();

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
		try {
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
			await queryRunner.release();
		}
	}

	/**
	 * Executes the given SQL SELECT query against an in-process PGlite
	 * database.  Enforces the same SELECT-only constraint as `executeQuery`.
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
			const result = await db.query(trimmed);
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

		// node-sql-parser returns an array for multi-statement input.
		if (Array.isArray(ast)) {
			throw new QueryExecutionError(
				t('QUERY_MULTIPLE_STATEMENTS', lang),
				'MULTIPLE_STATEMENTS',
			);
		}

		if (!ast || ast.type !== 'select') {
			const type = ast?.type ?? 'unknown';
			throw new QueryExecutionError(
				t('QUERY_NON_SELECT', lang, type),
				'NON_SELECT',
			);
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
