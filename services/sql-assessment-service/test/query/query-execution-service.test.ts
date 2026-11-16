import { describe, it, expect, beforeAll, beforeEach, afterAll, vi } from 'vitest';
import { IMemoryDb, IBackup } from 'pg-mem';
import { DataSource } from 'typeorm';
import { createTestDb } from '../helpers/pg-mem-factory';
import { QueryExecutionService, QueryExecutionError } from '../../src/query/query-execution-service';
import { makeReadOnlyRowQueryFn } from '../../src/shared/utils/database-utils';

// ---------------------------------------------------------------------------
// Shared pg-mem database
// ---------------------------------------------------------------------------

let db: IMemoryDb;
let backup: IBackup;
let dataSource: DataSource;
let service: QueryExecutionService;

beforeAll(async () => {
    ({ db, backup, dataSource } = await createTestDb());
    db.public.interceptQueries((sql) => sql === 'SET TRANSACTION READ ONLY' ? [] : null);
});

beforeEach(() => {
    backup.restore();
    service = new QueryExecutionService();
});

afterAll(async () => {
    await dataSource.destroy();
});

// ---------------------------------------------------------------------------
// Happy-path execution
// ---------------------------------------------------------------------------

describe('QueryExecutionService', () => {
    it('uses a read-only transaction on the same Postgres runner and rolls back on failure', async () => {
        const error = new Error('read only');
        const execute = vi.fn().mockRejectedValueOnce(error);
        const broadcastBeforeQueryEvent = vi.fn();
        const broadcastAfterQueryEvent = vi.fn();
        const logger = { logQuery: vi.fn(), logQueryError: vi.fn(), logQuerySlow: vi.fn() };
        const runner = {
            startTransaction: vi.fn().mockResolvedValue(undefined),
            query: vi.fn().mockResolvedValue(undefined),
            connect: vi.fn().mockResolvedValue({ query: execute }),
            broadcaster: { broadcastBeforeQueryEvent, broadcastAfterQueryEvent },
            rollbackTransaction: vi.fn().mockResolvedValue(undefined),
            release: vi.fn().mockResolvedValue(undefined),
            isTransactionActive: true,
        };
        const source = { createQueryRunner: () => runner, logger, options: {} } as unknown as DataSource;
        await expect(service.executeQuery('SELECT mutate_products()', source)).rejects.toMatchObject({ code: 'EXECUTION_FAILED' });
        expect(runner.query.mock.calls).toEqual([['SET TRANSACTION READ ONLY']]);
        expect(execute).toHaveBeenCalledWith({ text: 'SELECT mutate_products()', queryMode: 'extended' });
        expect(logger.logQuery).toHaveBeenCalledWith('SELECT mutate_products()', undefined, runner);
        expect(logger.logQueryError).toHaveBeenCalledWith(error, 'SELECT mutate_products()', undefined, runner);
        expect(broadcastBeforeQueryEvent).toHaveBeenCalledWith(expect.anything(), 'SELECT mutate_products()', undefined);
        expect(broadcastAfterQueryEvent).toHaveBeenCalledWith(expect.anything(), 'SELECT mutate_products()', undefined, false, undefined, undefined, error);
        expect(runner.startTransaction).toHaveBeenCalledOnce();
        expect(runner.rollbackTransaction).toHaveBeenCalledOnce();
        expect(runner.release).toHaveBeenCalledOnce();
    });

    it('preserves TypeORM query logging and subscriber events', async () => {
        const query = 'SELECT * FROM northwind.categories';
        const logQuery = vi.spyOn(dataSource.logger, 'logQuery');
        const subscriber = { beforeQuery: vi.fn(), afterQuery: vi.fn() };
        dataSource.subscribers.push(subscriber);
        try {
            await service.executeQuery(query, dataSource);
            expect(logQuery).toHaveBeenCalledWith(query, undefined, expect.anything());
            expect(subscriber.beforeQuery).toHaveBeenCalledWith(expect.objectContaining({ query }));
            expect(subscriber.afterQuery).toHaveBeenCalledWith(expect.objectContaining({ query, success: true }));
        } finally {
            dataSource.subscribers.splice(dataSource.subscribers.indexOf(subscriber), 1);
            logQuery.mockRestore();
        }
    });

    it('does not execute the SELECT if read-only mode cannot be enabled', async () => {
        const runner = {
            startTransaction: vi.fn().mockResolvedValue(undefined),
            query: vi.fn().mockRejectedValue(new Error('read-only mode unavailable')),
            rollbackTransaction: vi.fn().mockResolvedValue(undefined),
            release: vi.fn().mockResolvedValue(undefined),
            isTransactionActive: true,
        };
        const source = { createQueryRunner: () => runner } as unknown as DataSource;
        await expect(service.executeQuery('SELECT 1', source)).rejects.toMatchObject({ code: 'EXECUTION_FAILED' });
        expect(runner.query).toHaveBeenCalledTimes(1);
        expect(runner.query).toHaveBeenCalledWith('SET TRANSACTION READ ONLY');
        expect(runner.rollbackTransaction).toHaveBeenCalledOnce();
        expect(runner.release).toHaveBeenCalledOnce();
    });

    it('rejects SELECT INTO before acquiring a connection', async () => {
        const createQueryRunner = vi.fn();
        await expect(service.executeQuery('SELECT 1 INTO copied', { createQueryRunner } as unknown as DataSource))
            .rejects.toMatchObject({ code: 'NON_SELECT' });
        expect(createQueryRunner).not.toHaveBeenCalled();
    });
    describe('executeQuery — happy path', () => {

        it('returns rows and correct rowCount for a simple SELECT *', async () => {
            const result = await service.executeQuery(
                'SELECT * FROM northwind.categories',
                dataSource
            );
            expect(result.rowCount).toBe(3);
            expect(result.rows).toHaveLength(3);
            expect(result.rows[0]).toHaveProperty('category_name');
        });

        it('returns an empty rows array when no rows match the WHERE clause', async () => {
            const result = await service.executeQuery(
                "SELECT * FROM northwind.products WHERE product_name = 'no such product'",
                dataSource
            );
            expect(result.rowCount).toBe(0);
            expect(result.rows).toEqual([]);
        });

        it('executes a query with a JOIN and returns combined rows', async () => {
            const result = await service.executeQuery(
                'SELECT o.order_id, c.company_name' +
                ' FROM northwind.orders o' +
                ' INNER JOIN northwind.customers c ON o.customer_id = c.customer_id',
                dataSource
            );
            expect(result.rowCount).toBe(3);
            expect(result.rows[0]).toHaveProperty('order_id');
            expect(result.rows[0]).toHaveProperty('company_name');
        });

        it('executes a query with GROUP BY and aggregate functions', async () => {
            const result = await service.executeQuery(
                'SELECT category_id, COUNT(*) AS product_count' +
                ' FROM northwind.products' +
                ' GROUP BY category_id' +
                ' ORDER BY category_id',
                dataSource
            );
            // categories 1 and 2 have products in the seed data
            expect(result.rowCount).toBeGreaterThan(0);
            expect(result.rows[0]).toHaveProperty('product_count');
        });

        it('handles leading/trailing whitespace in the query string', async () => {
            const result = await service.executeQuery(
                '   SELECT * FROM northwind.suppliers   ',
                dataSource
            );
            expect(result.rowCount).toBe(3);
        });

    });

    // -------------------------------------------------------------------------
    // Input-validation faults (no DB needed for most of these)
    // -------------------------------------------------------------------------

    describe('executeQuery — faulty input', () => {

        it('throws EMPTY_QUERY for an empty string', async () => {
            await expect(service.executeQuery('', dataSource))
                .rejects.toThrow(QueryExecutionError);
            await expect(service.executeQuery('', dataSource))
                .rejects.toMatchObject({ code: 'EMPTY_QUERY' });
        });

        it('throws EMPTY_QUERY for a whitespace-only string', async () => {
            await expect(service.executeQuery('   \t\n  ', dataSource))
                .rejects.toMatchObject({ code: 'EMPTY_QUERY' });
        });

        it('throws PARSE_ERROR for arbitrary non-SQL text', async () => {
            await expect(service.executeQuery('hello world this is not sql', dataSource))
                .rejects.toMatchObject({ code: 'PARSE_ERROR' });
        });

        it('throws PARSE_ERROR for a number-only input', async () => {
            await expect(service.executeQuery('42', dataSource))
                .rejects.toMatchObject({ code: 'PARSE_ERROR' });
        });

        it('throws PARSE_ERROR for JSON-like input', async () => {
            await expect(service.executeQuery('{"query":"SELECT 1"}', dataSource))
                .rejects.toMatchObject({ code: 'PARSE_ERROR' });
        });

        it('throws PARSE_ERROR for a SQL fragment without a keyword', async () => {
            await expect(service.executeQuery('products WHERE id = 1', dataSource))
                .rejects.toMatchObject({ code: 'PARSE_ERROR' });
        });

        it('throws NON_SELECT for an INSERT statement', async () => {
            await expect(service.executeQuery(
                "INSERT INTO northwind.categories (category_name) VALUES ('X')",
                dataSource
            )).rejects.toMatchObject({ code: 'NON_SELECT' });
        });

        it('throws NON_SELECT for an UPDATE statement', async () => {
            await expect(service.executeQuery(
                "UPDATE northwind.products SET unit_price = 99 WHERE product_id = 1",
                dataSource
            )).rejects.toMatchObject({ code: 'NON_SELECT' });
        });

        it('throws NON_SELECT for a DELETE statement', async () => {
            await expect(service.executeQuery(
                "DELETE FROM northwind.products WHERE product_id = 1",
                dataSource
            )).rejects.toMatchObject({ code: 'NON_SELECT' });
        });

        it('throws NON_SELECT for a CREATE TABLE statement', async () => {
            await expect(service.executeQuery(
                'CREATE TABLE northwind.test_table (id SERIAL PRIMARY KEY)',
                dataSource
            )).rejects.toMatchObject({ code: 'NON_SELECT' });
        });

        it('throws NON_SELECT for a DROP TABLE statement', async () => {
            await expect(service.executeQuery(
                'DROP TABLE northwind.products',
                dataSource
            )).rejects.toMatchObject({ code: 'NON_SELECT' });
        });

        it('throws MULTIPLE_STATEMENTS for two statements separated by a semicolon', async () => {
            await expect(service.executeQuery(
                'SELECT * FROM northwind.products; SELECT * FROM northwind.orders',
                dataSource
            )).rejects.toMatchObject({ code: 'MULTIPLE_STATEMENTS' });
        });

        it('throws EXECUTION_FAILED for a SELECT referencing a non-existent table', async () => {
            await expect(service.executeQuery(
                'SELECT * FROM northwind.does_not_exist',
                dataSource
            )).rejects.toMatchObject({ code: 'EXECUTION_FAILED' });
        });

        it('throws EXECUTION_FAILED for a SELECT referencing a non-existent column', async () => {
            await expect(service.executeQuery(
                'SELECT no_such_column FROM northwind.products',
                dataSource
            )).rejects.toMatchObject({ code: 'EXECUTION_FAILED' });
        });

        it('throws EXECUTION_FAILED for a syntactically malformed SQL that the parser accepts but the DB rejects', async () => {
            // pg-mem will accept this as a SELECT but reject the invalid cast at runtime
            await expect(service.executeQuery(
                "SELECT * FROM northwind.products WHERE unit_price = 'not-a-number'::numeric",
                dataSource
            )).rejects.toMatchObject({ code: 'EXECUTION_FAILED' });
        });

        it('QueryExecutionError carries the correct name and message', async () => {
            let caught: QueryExecutionError | undefined;
            try {
                await service.executeQuery('', dataSource);
            } catch (e) {
                caught = e as QueryExecutionError;
            }
            expect(caught).toBeDefined();
            expect(caught!.name).toBe('QueryExecutionError');
            expect(caught!.message).toMatch(/empty/i);
        });

    });
});

const testPostgresUrl = process.env.SQL_ASSESSMENT_TEST_POSTGRES_URL;

describe.skipIf(!testPostgresUrl)('read-only execution against PostgreSQL', () => {
    let postgres: DataSource;
    const table = `assessment_readonly_${process.pid}_${Date.now()}`;
    const persistentTable = `public."${table}"`;

    beforeAll(async () => {
        postgres = new DataSource({
            type: 'postgres',
            url: testPostgresUrl,
            extra: { max: 1 },
        });
        await postgres.initialize();
        await postgres.query(`CREATE TABLE ${persistentTable} (value integer)`);
        await postgres.query(`INSERT INTO ${persistentTable} VALUES (1)`);
        await postgres.query('CREATE TEMP TABLE scratch (value integer)');
        await postgres.query('INSERT INTO scratch VALUES (1)');
        await postgres.query('CREATE TEMP SEQUENCE scratch_sequence');
        await postgres.query(`
            CREATE FUNCTION pg_temp.write_persistent() RETURNS integer AS $$
            BEGIN UPDATE ${persistentTable} SET value = 2; RETURN 2; END;
            $$ LANGUAGE plpgsql
        `);
        await postgres.query(`
            CREATE FUNCTION pg_temp.write_scratch() RETURNS integer AS $$
            BEGIN UPDATE scratch SET value = value + 1; RETURN (SELECT value FROM scratch); END;
            $$ LANGUAGE plpgsql
        `);
    });

    afterAll(async () => {
        if (postgres?.isInitialized) {
            await postgres.query(`DROP TABLE IF EXISTS ${persistentTable}`);
            await postgres.destroy();
        }
    });

    it('preserves ordinary SELECT, CTE and literal-semicolon results', async () => {
        expect(await service.executeQuery("SELECT ';' AS value", postgres))
            .toEqual({ rows: [{ value: ';' }], rowCount: 1 });
        expect(await makeReadOnlyRowQueryFn(postgres)('WITH x AS (SELECT 42 AS value) SELECT value FROM x'))
            .toEqual([{ value: 42 }]);
        expect(await makeReadOnlyRowQueryFn(postgres)("SELECT 'a;b' AS value WHERE 1 IS DISTINCT FROM 2;"))
            .toEqual([{ value: 'a;b' }]);
        const plan = await makeReadOnlyRowQueryFn(postgres)('EXPLAIN (FORMAT JSON) SELECT 42 AS value');
        expect(plan[0]).toHaveProperty('QUERY PLAN');
    });

    it('rejects persistent writes through functions and leaves the connection usable', async () => {
        await expect(service.executeQuery('SELECT pg_temp.write_persistent()', postgres))
            .rejects.toMatchObject({ code: 'EXECUTION_FAILED' });
        await expect(makeReadOnlyRowQueryFn(postgres)('SELECT pg_temp.write_persistent()'))
            .rejects.toThrow(/read.only/i);
        expect(await postgres.query(`SELECT value FROM ${persistentTable}`)).toEqual([{ value: 1 }]);
        expect(await makeReadOnlyRowQueryFn(postgres)('SELECT 1 AS value')).toEqual([{ value: 1 }]);
    });

    it('rolls back temporary-table writes and session settings on success', async () => {
        const runQuery = makeReadOnlyRowQueryFn(postgres);
        const originalSetting = await postgres.query("SELECT current_setting('application_name') AS value");
        expect((await service.executeQuery('SELECT pg_temp.write_scratch() AS value', postgres)).rows)
            .toEqual([{ value: 2 }]);
        expect(await runQuery('SELECT pg_temp.write_scratch() AS value')).toEqual([{ value: 2 }]);
        expect(await postgres.query('SELECT value FROM scratch')).toEqual([{ value: 1 }]);
        await runQuery("SELECT set_config('application_name', 'assessment-test', false)");
        expect(await postgres.query("SELECT current_setting('application_name') AS value"))
            .toEqual(originalSetting);
    });

    it('rejects SELECT INTO and multiple statements', async () => {
        const runQuery = makeReadOnlyRowQueryFn(postgres);
        await expect(service.executeQuery('SELECT 1 INTO scratch_created', postgres))
            .rejects.toMatchObject({ code: 'NON_SELECT' });
        await expect(runQuery('SELECT 1 INTO scratch_created')).rejects.toThrow();
        await expect(runQuery('SELECT 1 INTO TEMP TABLE scratch_created')).rejects.toThrow(/read.only/i);
        await expect(runQuery('EXPLAIN (FORMAT JSON) SELECT 1 INTO TEMP TABLE scratch_created')).rejects.toThrow();
        await expect(runQuery('SELECT 1 WHERE 1 IS DISTINCT FROM 2; UPDATE scratch SET value = 99')).rejects.toThrow();
        await expect(runQuery('SELECT 1; UPDATE scratch SET value = 99')).rejects.toThrow();
        expect(await postgres.query("SELECT to_regclass('scratch_created') AS value"))
            .toEqual([{ value: null }]);
        expect(await postgres.query('SELECT value FROM scratch')).toEqual([{ value: 1 }]);
    });

    it('rejects parser-disagreement statements without committing or mutating', async () => {
        const query = `SELECT 'abc\\'; COMMIT; UPDATE ${persistentTable} SET value = 99; --'`;
        try {
            await expect(service.executeQuery(query, postgres))
                .rejects.toMatchObject({ code: 'EXECUTION_FAILED' });
            expect(await postgres.query(`SELECT value FROM ${persistentTable}`)).toEqual([{ value: 1 }]);
            await expect(makeReadOnlyRowQueryFn(postgres)(query)).rejects.toThrow();
            expect(await postgres.query(`SELECT value FROM ${persistentTable}`)).toEqual([{ value: 1 }]);
        } finally {
            await postgres.query(`UPDATE ${persistentTable} SET value = 1`);
        }
    });

    it('does not roll back temporary-sequence increments', async () => {
        const runQuery = makeReadOnlyRowQueryFn(postgres);
        expect(await runQuery("SELECT nextval('scratch_sequence')::int AS value"))
            .toEqual([{ value: 1 }]);
        expect(await runQuery("SELECT nextval('scratch_sequence')::int AS value"))
            .toEqual([{ value: 2 }]);
    });

    it('does not release session-level advisory locks on rollback', async () => {
        const lockKey = 40000000 + process.pid;
        try {
            await makeReadOnlyRowQueryFn(postgres)(`SELECT pg_advisory_lock(${lockKey})`);
            const locks = await postgres.query(
                "SELECT count(*)::int AS value FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid() AND objid = $1",
                [lockKey],
            );
            expect(locks).toEqual([{ value: 1 }]);
        } finally {
            await postgres.query('SELECT pg_advisory_unlock_all()');
        }
    });
});
