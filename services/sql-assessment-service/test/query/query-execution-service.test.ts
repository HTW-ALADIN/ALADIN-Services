import { describe, it, expect, beforeAll, beforeEach, afterAll, vi } from 'vitest';
import { IMemoryDb, IBackup } from 'pg-mem';
import { DataSource } from 'typeorm';
import { createTestDb } from '../helpers/pg-mem-factory';
import { QueryExecutionService, QueryExecutionError } from '../../src/query/query-execution-service';

// ---------------------------------------------------------------------------
// Shared pg-mem database
// ---------------------------------------------------------------------------

let db: IMemoryDb;
let backup: IBackup;
let dataSource: DataSource;
let service: QueryExecutionService;

beforeAll(async () => {
    ({ db, backup, dataSource } = await createTestDb());
});

beforeEach(() => {
    backup.restore();
    service = new QueryExecutionService();
});

afterAll(async () => {
    await dataSource.destroy();
});

// ---------------------------------------------------------------------------
// Shared execution harness
// ---------------------------------------------------------------------------

function createExecution(backend: string) {
    const rows = [{ answer: 42 }];
    const query = vi.fn().mockResolvedValue(backend === 'PGlite' ? { rows } : rows);
    const release = vi.fn().mockResolvedValue(undefined);
    const createQueryRunner = vi.fn().mockReturnValue({ query, release });
    const execute = (sql: string) => backend === 'PGlite'
        ? service.executeQueryOnPGlite(sql, { query })
        : service.executeQuery(sql, { createQueryRunner } as unknown as DataSource);
    return { execute, query, createQueryRunner, release };
}

// ---------------------------------------------------------------------------
// Happy-path execution
// ---------------------------------------------------------------------------

describe('QueryExecutionService', () => {
    describe.each(['PostgreSQL', 'PGlite'])('%s SELECT terminator handling', (backend) => {
        it.each([
            'SELECT 42 AS answer',
            'SELECT 6 * 7 AS answer;',
            ' \n SELECT 42 AS answer; \t ',
            '/* leading ; */ SELECT 42 AS answer /* before ; */; -- trailing ;',
            'SELECT 42 AS answer; /* trailing ; SELECT 1; */',
            'SELECT 42 AS answer -- comment ;\n;',
            "SELECT 'semi;colon' AS answer;",
            "SELECT 'it''s; safe' AS answer;",
            'SELECT $$semi;colon$$ AS answer;',
            'SELECT 42 AS "semi;colon";',
            'WITH c AS (SELECT 42 AS answer) SELECT * FROM c;',
            'SELECT 42 AS answer UNION ALL SELECT 1 AS answer;',
            'SELECT 42 AS answer;;',
        ])('accepts one SELECT without rewriting SQL: %s', async (sql) => {
            const { execute, query, release } = createExecution(backend);
            await expect(execute(sql)).resolves.toEqual({ rows: [{ answer: 42 }], rowCount: 1 });
            expect(query).toHaveBeenCalledExactlyOnceWith(sql.trim());
            if (backend === 'PostgreSQL') expect(release).toHaveBeenCalledOnce();
        });

        it.each([';', ';;', '-- comment only;', '/* comment only; */'])(
            'rejects a query with no statement: %s',
            async (sql) => {
                const { execute, query } = createExecution(backend);
                await expect(execute(sql)).rejects.toMatchObject({ code: 'NON_SELECT' });
                expect(query).not.toHaveBeenCalled();
            },
        );
    });

    describe.each(['PostgreSQL', 'PGlite'])('%s mutation rejection', (backend) => {
        it.each([
            ['SELECT 42; SELECT 1', 'MULTIPLE_STATEMENTS'],
            ['SELECT 42; /* comment ; */ SELECT 1;', 'MULTIPLE_STATEMENTS'],
            ['SELECT 42; -- comment ;\nSELECT 1;', 'MULTIPLE_STATEMENTS'],
            ["SELECT 'semi;colon'; DROP TABLE products;", 'MULTIPLE_STATEMENTS'],
            ['SELECT 42; DELETE FROM products;', 'MULTIPLE_STATEMENTS'],
            ['SELECT42; SELECT1', 'PARSE_ERROR'],
            ['SELECT 42 INTO created_table;', 'NON_SELECT'],
            ['WITH c AS (UPDATE products SET id = 1 RETURNING *) SELECT * FROM c;', 'NON_SELECT'],
            ['WITH c AS (INSERT INTO products (name) VALUES (\'x\') RETURNING *) SELECT * FROM c;', 'NON_SELECT'],
            ['WITH c AS (DELETE FROM products WHERE id = 1 RETURNING id) SELECT * FROM c;', 'NON_SELECT'],
            ['SELECT * FROM (WITH c AS (UPDATE products SET id = 1 RETURNING *) SELECT * FROM c) AS nested;', 'NON_SELECT'],
        ])('rejects before touching the database: %s', async (sql, code) => {
            const { execute, query, createQueryRunner, release } = createExecution(backend);
            await expect(execute(sql)).rejects.toMatchObject({ code });
            expect(query).not.toHaveBeenCalled();
            if (backend === 'PostgreSQL') {
                expect(createQueryRunner).not.toHaveBeenCalled();
                expect(release).not.toHaveBeenCalled();
            }
        });

        it.each([
            'SELECT "insert" FROM products',
            'SELECT 1 AS "into"',
            'SELECT * FROM products AS "update"',
            "SELECT 'delete' AS \"update\"",
        ])('does not treat quoted identifiers as mutations: %s', async (sql) => {
            const { execute, query } = createExecution(backend);
            await expect(execute(sql)).resolves.toBeDefined();
            expect(query).toHaveBeenCalledOnce();
        });
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
