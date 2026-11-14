import { DataSource, QueryFailedError, QueryRunner } from 'typeorm';
import { BroadcasterResult } from 'typeorm/subscriber/BroadcasterResult';
import type { PGlite } from '@electric-sql/pglite';
import { AST, Parser } from 'node-sql-parser';
import { IAliasMap, IParsedTable } from '../interfaces/domain';

/**
 * Database-agnostic query executor: accepts a SQL string and returns the
 * result rows as a plain array.  Works with both Postgres (TypeORM) and
 * PGlite execution paths.
 */
export type RowQueryFn = (sql: string) => Promise<any[]>;

function assertReadOnlyStatement(sql: string): void {
	const statement = sql.replace(
		/^\s*EXPLAIN\s*\(\s*FORMAT\s+JSON\s*\)\s+/i,
		'',
	);
	let ast: AST | AST[];
	try {
		ast = new Parser().astify(statement, { database: 'postgresql' });
	} catch (error) {
		if (statement === sql && /^\s*select\b/i.test(statement)) {
			return;
		}
		throw error;
	}
	if (
		Array.isArray(ast) ||
		!ast ||
		ast.type !== 'select' ||
		(ast as any).into?.position
	) {
		throw new Error('Only a single SELECT without INTO is allowed');
	}
}

export function makeReadOnlyRowQueryFn(dataSource: DataSource): RowQueryFn {
	return async (sql: string) => {
		assertReadOnlyStatement(sql);
		const runner = dataSource.createQueryRunner();
		try {
			await runner.startTransaction();
			await runner.query('SET TRANSACTION READ ONLY');
			const connection = await runner.connect();
			dataSource.logger.logQuery(sql, undefined, runner);
			const beforeEvents = new BroadcasterResult();
			runner.broadcaster.broadcastBeforeQueryEvent(beforeEvents, sql, undefined);
			await beforeEvents.wait();
			const afterEvents = new BroadcasterResult();
			const startedAt = Date.now();
			let result: { rows: any[] };
			try {
				result = await connection.query({ text: sql, queryMode: 'extended' });
			} catch (error) {
				const loggedError =
					error instanceof Error || typeof error === 'string'
						? error
						: String(error);
				dataSource.logger.logQueryError(loggedError, sql, undefined, runner);
				runner.broadcaster.broadcastAfterQueryEvent(
					afterEvents,
					sql,
					undefined,
					false,
					undefined,
					undefined,
					error,
				);
				await afterEvents.wait();
				if (error instanceof Error) {
					throw new QueryFailedError(sql, undefined, error);
				}
				throw error;
			}
			const elapsed = Date.now() - startedAt;
			if (
				dataSource.options.maxQueryExecutionTime &&
				elapsed > dataSource.options.maxQueryExecutionTime
			) {
				dataSource.logger.logQuerySlow(elapsed, sql, undefined, runner);
			}
			runner.broadcaster.broadcastAfterQueryEvent(
				afterEvents,
				sql,
				undefined,
				true,
				elapsed,
				result,
				undefined,
			);
			await afterEvents.wait();
			return result.rows;
		} finally {
			try {
				if (runner.isTransactionActive) await runner.rollbackTransaction();
			} finally {
				await runner.release();
			}
		}
	};
}

export function makeReadOnlyPGliteRowQueryFn(db: PGlite): RowQueryFn {
	return async (sql: string) => {
		assertReadOnlyStatement(sql);
		return db.transaction(async (tx) => {
			await tx.query('SET TRANSACTION READ ONLY');
			const result = await tx.query(sql);
			await tx.rollback();
			return result.rows as any[];
		});
	};
}

/**
 * Builds a {@link RowQueryFn} backed by a TypeORM {@link DataSource}.
 * Each invocation acquires a QueryRunner from the pool, executes the query,
 * and releases the runner before returning.
 */
export function makeRowQueryFn(dataSource: DataSource): RowQueryFn {
	return async (sql: string) => {
		const queryRunner = dataSource.createQueryRunner();
		try {
			return await queryRunner.query(sql);
		} finally {
			await queryRunner.release();
		}
	};
}

/**
 * Builds a {@link RowQueryFn} backed by a live in-process {@link PGlite}
 * instance.  Unwraps the `{ rows }` result envelope so the returned array has
 * the same shape as the TypeORM {@link makeRowQueryFn} path.
 *
 * IMPORTANT: PGlite instances are shared and long-lived (stored in
 * `pgliteInstances`).  This function never closes the instance — callers must
 * not destroy it after use.
 */
export function makePGliteRowQueryFn(db: PGlite): RowQueryFn {
	return async (sql: string) => {
		const result = await db.query(sql);
		return result.rows as any[];
	};
}

export function generateDatabaseKey(
	host: string,
	port: number,
	schema: string,
): string {
	return `${host}:${port}/${schema}`;
}

export function generatePGliteKey(databaseId: string): string {
	return `pglite:${databaseId}`;
}

export async function connectToDatabase(
	dataSource: DataSource,
): Promise<boolean> {
	let isConnected = false;
	await dataSource
		.initialize()
		.then(() => {
			console.log(`Data Source ${dataSource} has been initialized!`);
			isConnected = true;
		})
		.catch((err) => {
			console.error(
				`Error during Data Source ${dataSource} initialization`,
				err,
			);
			isConnected = false;
		});
	return isConnected;
}

export function createQueryRunner(
	dataSource: DataSource,
): QueryRunner | undefined {
	if (!dataSource) {
		console.log('Undefined datasource, please establish a database connection');
		return undefined;
	}
	return dataSource.createQueryRunner();
}

/**
 * Reconstructs an {@link IAliasMap} from the `alternativeName` fields that
 * were burned into `IParsedTable` / `IParsedColumn` records at analysis time.
 *
 * Only entries that actually have an `alternativeName` are included, so the
 * result is `undefined` when no alias data is present (no analysis with an
 * aliasMap was performed).
 */
export function buildAliasMapFromTables(
	tables: IParsedTable[],
): IAliasMap | undefined {
	const tableAliases: Record<string, string> = {};
	const columnAliases: Record<string, Record<string, string>> = {};

	for (const table of tables) {
		if (table.alternativeName) {
			tableAliases[table.name] = table.alternativeName;
		}

		for (const col of table.columns) {
			if (col.alternativeName) {
				if (!columnAliases[table.name]) {
					columnAliases[table.name] = {};
				}
				columnAliases[table.name][col.name] = col.alternativeName;
			}
		}
	}

	const hasTableAliases = Object.keys(tableAliases).length > 0;
	const hasColumnAliases = Object.keys(columnAliases).length > 0;

	if (!hasTableAliases && !hasColumnAliases) return undefined;

	return {
		...(hasTableAliases ? { tables: tableAliases } : {}),
		...(hasColumnAliases ? { columns: columnAliases } : {}),
	};
}
