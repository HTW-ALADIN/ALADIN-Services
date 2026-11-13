import { DataSource, QueryFailedError } from 'typeorm';
import { AST, Parser } from 'node-sql-parser';
import { QueryExecutionResult } from '../shared/interfaces/http';
import { t, SupportedLanguage } from '../shared/i18n';

/**
 * AST node types that can mutate data even when the statement root is a
 * SELECT — e.g. data-modifying CTEs and `SELECT ... INTO`.
 */
const MUTATING_NODE_TYPES = new Set(['insert', 'update', 'delete', 'into']);

/**
 * Sequence functions are not transactional: their increments survive a
 * rollback, and read-only transactions still permit them on temporary
 * sequences.  Reject them before they touch the database.
 */
const UNSAFE_FUNCTION_NAMES = new Set(['nextval', 'setval']);

/**
 * Force the extended query protocol.
 *
 * `pg` uses the simple query protocol for plain strings, and that protocol
 * accepts multiple `;`-separated commands.  A parser/protocol mismatch such as
 * `SELECT 'x\'; COMMIT; DELETE FROM products; --'` would otherwise commit the
 * read-only transaction and run the DELETE.  The extended protocol rejects
 * multiple commands in a single prepared statement.
 */
function extendedQuery(text: string): string {
	return { text, queryMode: 'extended' } as unknown as string;
}

/** Returns the lower-cased function name of a node-sql-parser function node. */
function getFunctionName(node: unknown): string | undefined {
	const { name } = node as { name?: unknown };
	if (!name || typeof name !== 'object') return undefined;
	const parts = (name as { name?: unknown }).name;
	if (!Array.isArray(parts) || parts.length === 0) return undefined;
	const last = parts[parts.length - 1] as { value?: unknown } | undefined;
	return typeof last?.value === 'string' ? last.value.toLowerCase() : undefined;
}

/**
 * True when the character can be part of an unquoted identifier.  PostgreSQL
 * allows `$` inside identifiers, so a `$tag$` sequence that follows an
 * identifier character is not a dollar-quoted string opener.
 */
function isIdentifierChar(ch: string | undefined): boolean {
	return ch !== undefined && /[A-Za-z0-9_$]/.test(ch);
}

/**
 * Detects literals where a backslash escapes a quote.
 *
 * node-sql-parser treats `\'` as an escaped quote, but PostgreSQL with the
 * default `standard_conforming_strings = on` closes the literal at that quote.
 * The mismatch lets a query such as `SELECT 'x\', nextval($$seq$$) --'` hide a
 * function call from the AST, so reject it instead of guessing which side is
 * right.
 *
 * Comments and dollar-quoted strings are skipped; E-strings are not supported
 * by the parser and therefore already end in `QUERY_PARSE_ERROR`.
 */
function hasAmbiguousBackslashEscape(sql: string): boolean {
	let i = 0;
	while (i < sql.length) {
		const ch = sql[i];

		if (ch === '-' && sql[i + 1] === '-') {
			const newline = sql.indexOf('\n', i + 2);
			if (newline === -1) return false;
			i = newline + 1;
			continue;
		}

		if (ch === '/' && sql[i + 1] === '*') {
			let depth = 1;
			i += 2;
			while (i < sql.length && depth > 0) {
				if (sql[i] === '/' && sql[i + 1] === '*') {
					depth += 1;
					i += 2;
				} else if (sql[i] === '*' && sql[i + 1] === '/') {
					depth -= 1;
					i += 2;
				} else {
					i += 1;
				}
			}
			continue;
		}

		if (ch === '$' && !isIdentifierChar(sql[i - 1])) {
			const tag = /^\$([A-Za-z_][A-Za-z0-9_]*)?\$/.exec(sql.slice(i));
			if (tag) {
				const end = sql.indexOf(tag[0], i + tag[0].length);
				if (end === -1) return false;
				i = end + tag[0].length;
				continue;
			}
		}

		if (ch === "'" || ch === '"') {
			const quote = ch;
			i += 1;
			while (i < sql.length) {
				if (sql[i] === '\\') {
					let j = i;
					while (j < sql.length && sql[j] === '\\') j += 1;
					if ((j - i) % 2 === 1 && sql[j] === quote) return true;
					i = j;
					continue;
				}
				if (sql[i] === quote) {
					if (sql[i + 1] === quote) {
						i += 2;
						continue;
					}
					i += 1;
					break;
				}
				i += 1;
			}
			continue;
		}

		i += 1;
	}
	return false;
}

interface TempSequenceState {
	name: string;
	lastValue: number | string;
	isCalled: boolean;
}

/**
 * Captures the state of every temporary sequence in the current PGlite
 * session.  Sequence increments are non-transactional, so they survive the
 * rollback that discards temporary-table writes.
 */
async function snapshotTempSequences(tx: any): Promise<TempSequenceState[]> {
	const { rows } = await tx.query(
		`SELECT format('%I.%I', n.nspname, c.relname) AS name
		 FROM pg_class c
		 JOIN pg_namespace n ON n.oid = c.relnamespace
		 WHERE c.relkind = 'S' AND n.oid = pg_my_temp_schema()
		 ORDER BY c.oid`,
	);
	const snapshots: TempSequenceState[] = [];
	for (const row of rows as { name: string }[]) {
		const state = await tx.query(
			`SELECT last_value, is_called FROM ${row.name}`,
		);
		const current = (
			state.rows as { last_value: number | string; is_called: boolean }[]
		)[0];
		snapshots.push({
			name: row.name,
			lastValue: current.last_value,
			isCalled: current.is_called,
		});
	}
	return snapshots;
}

async function restoreTempSequences(
	tx: any,
	snapshots: TempSequenceState[],
): Promise<void> {
	for (const snapshot of snapshots) {
		await tx.query('SELECT setval($1::regclass, $2, $3)', [
			snapshot.name,
			snapshot.lastValue,
			snapshot.isCalled,
		]);
	}
}

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
			const rows: Record<string, unknown>[] = await queryRunner.query(
				extendedQuery(trimmed),
			);
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
	 * instance can safely hold a short-lived read-only transaction.  The
	 * transaction is always rolled back: a read-only transaction still permits
	 * session settings and writes to temporary tables, and PGlite would commit
	 * them if the callback returned normally.  PGlite also always uses the
	 * extended query protocol, which rejects multiple commands in one
	 * statement.
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
					const tempSequences = await snapshotTempSequences(tx);
					if (tempSequences.length === 0) {
						const queryResult = await tx.query(trimmed);
						// PGlite commits when the callback resolves, which would
						// persist session settings and temporary-table writes that
						// a read-only transaction still permits.  Roll back instead.
						await tx.rollback();
						return queryResult;
					}

					// Functions can advance a temporary sequence, and sequence
					// increments are non-transactional: they survive the rollback
					// that removes the temporary-table writes.  Run the query
					// behind a savepoint so the snapshot can be restored even when
					// the query itself fails.
					await tx.query('SAVEPOINT user_query');
					let queryResult: any;
					let queryError: unknown;
					try {
						queryResult = await tx.query(trimmed);
					} catch (err) {
						queryError = err;
						await tx.query('ROLLBACK TO SAVEPOINT user_query');
					}
					await restoreTempSequences(tx, tempSequences);
					await tx.rollback();
					if (queryError) throw queryError;
					return queryResult;
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
		if (hasAmbiguousBackslashEscape(query)) {
			throw new QueryExecutionError(
				t('QUERY_AMBIGUOUS_STRING', lang),
				'PARSE_ERROR',
			);
		}

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
	 * Rejects side effects that hide beneath a SELECT root:
	 *
	 *  - data-modifying CTEs (`WITH ... AS (UPDATE ...) SELECT ...`)
	 *  - `SELECT ... INTO`
	 *  - sequence functions (`nextval` / `setval`), whose increments are not
	 *    transactional and therefore survive a rollback even on temporary
	 *    sequences, which read-only transactions permit
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

			if (type === 'function') {
				const name = getFunctionName(node);
				if (name && UNSAFE_FUNCTION_NAMES.has(name)) {
					throw new QueryExecutionError(
						t('QUERY_UNSAFE_FUNCTION', lang, name),
						'NON_SELECT',
					);
				}
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
