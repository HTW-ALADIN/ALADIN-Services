import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { Request, Response } from 'express';
import { PGlite } from '@electric-sql/pglite';
import { QueryExecutionController } from '../../src/query/query-execution-controller';
import { QueryExecutionService } from '../../src/query/query-execution-service';
import {
	databaseMetadata,
	pgliteInstances,
} from '../../src/database/internal-memory';
import { generatePGliteKey, makeReadOnlyPGliteRowQueryFn } from '../../src/shared/utils/database-utils';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SIMPLE_DDL = `
CREATE TABLE products (
  id    SERIAL PRIMARY KEY,
  name  TEXT          NOT NULL,
  price NUMERIC(10,2)
);
INSERT INTO products (name, price) VALUES ('Widget', 9.99), ('Gadget', 19.99);
`;

const DB_ID = 'test-pglite-db';
const DB_KEY = generatePGliteKey(DB_ID);

const VALID_PGLITE_CONN = { type: 'pglite' as const, databaseId: DB_ID };

// ---------------------------------------------------------------------------
// Express mock helpers
// ---------------------------------------------------------------------------

function mockReq(body: unknown): Request {
	return { body } as Request;
}

function mockRes() {
	const json = vi.fn().mockReturnThis();
	const status = vi.fn().mockReturnValue({ json });
	return { res: { status, json } as unknown as Response, status, json };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('QueryExecutionController — PGlite path', () => {
	let controller: QueryExecutionController;
	let pgliteDb: PGlite;

	beforeEach(async () => {
		pgliteDb = new PGlite();
		await pgliteDb.exec(SIMPLE_DDL);
		pgliteInstances.set(DB_ID, pgliteDb);
		// Register metadata key so isDatabaseRegistered() returns true
		databaseMetadata.set(DB_KEY, []);

		controller = new QueryExecutionController(new QueryExecutionService());
	});

	afterEach(async () => {
		await pgliteDb.close();
		pgliteInstances.clear();
		databaseMetadata.clear();
	});

	// -----------------------------------------------------------------------
	// Request validation
	// -----------------------------------------------------------------------

	describe('executeQuery — PGlite request validation', () => {
		it('returns 400 when databaseId is missing', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: { type: 'pglite' }, query: 'SELECT 1' }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when the PGlite database has not been registered', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: { type: 'pglite', databaseId: 'non-existent-db' },
					query: 'SELECT 1',
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when query is missing', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_PGLITE_CONN }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when query is an empty string', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_PGLITE_CONN, query: '' }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when query is whitespace only', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_PGLITE_CONN, query: '   ' }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});
	});

	// -----------------------------------------------------------------------
	// Integration (real PGlite instance)
	// -----------------------------------------------------------------------

	describe('executeQuery — PGlite integration', () => {
		it('rolls back temporary writes and session settings after successful SELECTs', async () => {
			await pgliteDb.exec(`
				CREATE TEMP TABLE scratch (value integer);
				INSERT INTO scratch VALUES (1);
				CREATE FUNCTION pg_temp.write_scratch() RETURNS integer AS $$
				BEGIN UPDATE scratch SET value = value + 1; RETURN (SELECT value FROM scratch); END;
				$$ LANGUAGE plpgsql;
			`);
			const service = new QueryExecutionService();
			const gradingQuery = makeReadOnlyPGliteRowQueryFn(pgliteDb);
			const originalSetting = (await pgliteDb.query("SELECT current_setting('application_name') AS value")).rows;

			expect((await service.executeQueryOnPGlite('SELECT pg_temp.write_scratch() AS value', pgliteDb)).rows)
				.toEqual([{ value: 2 }]);
			expect(await gradingQuery('SELECT pg_temp.write_scratch() AS value')).toEqual([{ value: 2 }]);
			expect(await Promise.all([
				gradingQuery('SELECT pg_temp.write_scratch() AS value'),
				gradingQuery('SELECT pg_temp.write_scratch() AS value'),
			])).toEqual([[{ value: 2 }], [{ value: 2 }]]);
			expect((await pgliteDb.query('SELECT value FROM scratch')).rows).toEqual([{ value: 1 }]);

			await service.executeQueryOnPGlite("SELECT set_config('application_name', 'assessment-test', false)", pgliteDb);
			expect((await pgliteDb.query("SELECT current_setting('application_name') AS value")).rows)
				.toEqual(originalSetting);
		});

		it('rolls back temporary writes when a SELECT function fails', async () => {
			await pgliteDb.exec(`
				CREATE TEMP TABLE scratch (value integer);
				INSERT INTO scratch VALUES (1);
				CREATE FUNCTION pg_temp.fail_after_write() RETURNS integer AS $$
				BEGIN UPDATE scratch SET value = 2; RAISE EXCEPTION 'failed'; END;
				$$ LANGUAGE plpgsql;
			`);
			const service = new QueryExecutionService();
			await expect(service.executeQueryOnPGlite('SELECT pg_temp.fail_after_write()', pgliteDb))
				.rejects.toMatchObject({ code: 'EXECUTION_FAILED' });
			expect((await pgliteDb.query('SELECT value FROM scratch')).rows).toEqual([{ value: 1 }]);
		});
		it('does not roll back temporary sequence increments', async () => {
			await pgliteDb.exec('CREATE TEMP SEQUENCE scratch_sequence');
			const runQuery = makeReadOnlyPGliteRowQueryFn(pgliteDb);
			expect(await runQuery("SELECT nextval('scratch_sequence')::int AS value"))
				.toEqual([{ value: 1 }]);
			expect(await runQuery("SELECT nextval('scratch_sequence')::int AS value"))
				.toEqual([{ value: 2 }]);
		});

		it('rejects parser-disagreement statements without committing or mutating', async () => {
			const query = "SELECT 'abc\\'; COMMIT; UPDATE products SET price = 0; --'";
			await expect(new QueryExecutionService().executeQueryOnPGlite(query, pgliteDb))
				.rejects.toMatchObject({ code: 'EXECUTION_FAILED' });
			await expect(makeReadOnlyPGliteRowQueryFn(pgliteDb)(query)).rejects.toThrow();
			expect((await pgliteDb.query('SELECT price FROM products ORDER BY id')).rows)
				.toEqual([{ price: '9.99' }, { price: '19.99' }]);
		});

		it('rejects SELECT INTO and database mutations through functions', async () => {
			await pgliteDb.exec(`CREATE FUNCTION mutate_products() RETURNS integer AS $$
			BEGIN UPDATE products SET price = 0; RETURN 1; END;
			$$ LANGUAGE plpgsql`);
			const service = new QueryExecutionService();
			await expect(service.executeQueryOnPGlite('SELECT * INTO copied_products FROM products', pgliteDb))
				.rejects.toMatchObject({ code: 'NON_SELECT' });
			await expect(service.executeQueryOnPGlite('SELECT mutate_products()', pgliteDb))
				.rejects.toMatchObject({ code: 'EXECUTION_FAILED' });
			const gradingQuery = makeReadOnlyPGliteRowQueryFn(pgliteDb);
			await expect(gradingQuery('SELECT mutate_products()')).rejects.toThrow();
			await expect(gradingQuery('SELECT * INTO copied_products FROM products')).rejects.toThrow();
			await expect(gradingQuery('SELECT * INTO TEMP TABLE copied_products FROM products'))
				.rejects.toThrow(/read.only/i);
			await expect(gradingQuery('EXPLAIN (FORMAT JSON) SELECT * INTO TEMP TABLE copied_products FROM products'))
				.rejects.toThrow();
			await expect(gradingQuery('SELECT 1 WHERE 1 IS DISTINCT FROM 2; DELETE FROM products'))
				.rejects.toThrow();
			await expect(gradingQuery('SELECT 1; DELETE FROM products')).rejects.toThrow();
			expect((await pgliteDb.query('SELECT price FROM products ORDER BY id')).rows)
				.toEqual([{ price: '9.99' }, { price: '19.99' }]);
			expect((await pgliteDb.query("SELECT to_regclass('copied_products') AS name")).rows)
				.toEqual([{ name: null }]);
		});
		it('returns 200 for a valid SELECT', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: 'SELECT * FROM products',
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(200);
		});

		it('returns the seeded rows with correct rowCount', async () => {
			const { res, json } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: 'SELECT * FROM products ORDER BY id',
				}),
				res,
			);
			const result = json.mock.calls[0][0] as {
				rows: unknown[];
				rowCount: number;
			};
			expect(result.rowCount).toBe(2);
			expect(result.rows).toHaveLength(2);
		});

		it('returns empty rows when WHERE matches nothing', async () => {
			const { res, json } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: "SELECT * FROM products WHERE name = 'NonExistent'",
				}),
				res,
			);
			const result = json.mock.calls[0][0] as {
				rows: unknown[];
				rowCount: number;
			};
			expect(result.rows).toHaveLength(0);
			expect(result.rowCount).toBe(0);
		});

		it('returns 400 for an INSERT statement', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: "INSERT INTO products (name, price) VALUES ('X', 1.0)",
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 for a DELETE statement', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: 'DELETE FROM products',
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 500 when query references a non-existent table', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: 'SELECT * FROM non_existent_table',
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(500);
		});
	});
});
