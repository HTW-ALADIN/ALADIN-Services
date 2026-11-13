import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { Request, Response } from 'express';
import { PGlite } from '@electric-sql/pglite';
import { QueryExecutionController } from '../../src/query/query-execution-controller';
import { QueryExecutionService } from '../../src/query/query-execution-service';
import {
	databaseMetadata,
	pgliteInstances,
} from '../../src/database/internal-memory';
import { generatePGliteKey } from '../../src/shared/utils/database-utils';

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
		it.each([
			['SELECT 42 AS answer;', { answer: 42 }],
			['SELECT 6 * 7 AS answer; -- trailing ;', { answer: 42 }],
			['/* leading ; */ SELECT 42 AS answer; /* trailing ; */', { answer: 42 }],
			["SELECT 'it''s; safe' AS answer;", { answer: "it's; safe" }],
			['SELECT $$semi;colon$$ AS answer;', { answer: 'semi;colon' }],
			['SELECT 42 AS "semi;colon";', { 'semi;colon': 42 }],
			['SELECT 42 AS answer;;', { answer: 42 }],
		])('executes a terminated SELECT: %s', async (query, row) => {
			const { res, status, json } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_PGLITE_CONN, query }),
				res,
			);
			expect(status).toHaveBeenCalledWith(200);
			expect(json).toHaveBeenCalledWith({ rows: [row], rowCount: 1 });
		});

		it.each([
			['SELECT 42; SELECT 1;', 'MULTIPLE_STATEMENTS'],
			['SELECT42; SELECT1', 'PARSE_ERROR'],
			['SELECT 42; DELETE FROM products;', 'MULTIPLE_STATEMENTS'],
			['WITH c AS (UPDATE products SET price = 0 RETURNING *) SELECT * FROM c;', 'NON_SELECT'],
			["WITH c AS (INSERT INTO products (name, price) VALUES ('x', 1) RETURNING *) SELECT * FROM c;", 'NON_SELECT'],
			['WITH c AS (DELETE FROM products WHERE id = 1 RETURNING *) SELECT * FROM c;', 'NON_SELECT'],
			['SELECT 42 INTO created_table;', 'NON_SELECT'],
		])('returns 400 without mutating data: %s', async (query, code) => {
			const before = await pgliteDb.query('SELECT * FROM products ORDER BY id');
			const { res, status, json } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_PGLITE_CONN, query }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
			expect(json).toHaveBeenCalledWith(expect.objectContaining({ code }));
			expect((await pgliteDb.query('SELECT * FROM products ORDER BY id')).rows).toEqual(before.rows);
			expect(
				(await pgliteDb.query(
					"SELECT tablename FROM pg_tables WHERE tablename = 'created_table'",
				)).rows,
			).toEqual([]);
		});

		it('enforces read-only at the database level for volatile functions', async () => {
			const { res, status, json } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: 'SELECT lo_create(0) AS value;',
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(500);
			expect(json).toHaveBeenCalledWith(
				expect.objectContaining({
					code: 'EXECUTION_FAILED',
					message: expect.stringContaining('read-only'),
				}),
			);
		});

		it('rolls back session settings so they do not leak to later requests', async () => {
			const first = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: "SELECT set_config('search_path', 'pg_catalog', false) AS path;",
				}),
				first.res,
			);
			expect(first.status).toHaveBeenCalledWith(200);

			const second = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: 'SELECT id, name FROM products ORDER BY id;',
				}),
				second.res,
			);
			expect(second.status).toHaveBeenCalledWith(200);
			expect(second.json).toHaveBeenCalledWith({
				rows: [
					{ id: 1, name: 'Widget' },
					{ id: 2, name: 'Gadget' },
				],
				rowCount: 2,
			});
		});

		it('rolls back temporary-table writes performed by functions', async () => {
			await pgliteDb.exec(`
				CREATE TEMP TABLE scratch (id integer);
				CREATE FUNCTION write_scratch() RETURNS integer LANGUAGE SQL AS $$
					INSERT INTO scratch VALUES (1);
					SELECT count(*)::integer FROM scratch;
				$$;
			`);
			const { res, status, json } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: 'SELECT write_scratch() AS n;',
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(200);
			expect(json).toHaveBeenCalledWith({ rows: [{ n: 1 }], rowCount: 1 });
			expect(
				(await pgliteDb.query('SELECT count(*)::integer AS n FROM scratch')).rows,
			).toEqual([{ n: 0 }]);
		});

		it('rejects multi-command SQL smuggled through a string literal', async () => {
			const before = await pgliteDb.query('SELECT * FROM products ORDER BY id');
			const { res, status, json } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: "SELECT 'x\\'; COMMIT; DELETE FROM products; --'",
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
			expect(json).toHaveBeenCalledWith(
				expect.objectContaining({ code: 'PARSE_ERROR' }),
			);
			expect(
				(await pgliteDb.query('SELECT * FROM products ORDER BY id')).rows,
			).toEqual(before.rows);
		});

		it.each([
			"SELECT nextval('readonly_probe_temp_seq') AS value;",
			"SELECT setval('readonly_probe_temp_seq', 10) AS value;",
			"SELECT pg_catalog.nextval('readonly_probe_temp_seq') AS value;",
		])('rejects sequence-mutating functions before execution: %s', async (query) => {
			await pgliteDb.exec('CREATE TEMP SEQUENCE readonly_probe_temp_seq');
			const { res, status, json } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_PGLITE_CONN, query }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
			expect(json).toHaveBeenCalledWith(
				expect.objectContaining({ code: 'NON_SELECT' }),
			);
			expect(
				(await pgliteDb.query(
					'SELECT last_value, is_called FROM readonly_probe_temp_seq',
				)).rows,
			).toEqual([{ last_value: 1, is_called: false }]);
		});

		it('rejects backslash-escaped quotes that hide sequence calls', async () => {
			await pgliteDb.exec('CREATE TEMP SEQUENCE hidden_probe_seq');
			const { res, status, json } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: "SELECT 'x\\', nextval($$hidden_probe_seq$$) --'",
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
			expect(json).toHaveBeenCalledWith(
				expect.objectContaining({ code: 'PARSE_ERROR' }),
			);
			expect(
				(await pgliteDb.query(
					'SELECT last_value, is_called FROM hidden_probe_seq',
				)).rows,
			).toEqual([{ last_value: 1, is_called: false }]);
		});

		it('restores temporary-sequence increments caused by functions', async () => {
			await pgliteDb.exec(`
				CREATE TEMP TABLE scratch_ids (id serial);
				CREATE FUNCTION bump_scratch() RETURNS integer LANGUAGE SQL AS $$
					INSERT INTO scratch_ids DEFAULT VALUES;
					SELECT last_value::integer FROM scratch_ids_id_seq;
				$$;
			`);
			const before = await pgliteDb.query(
				'SELECT last_value, is_called FROM scratch_ids_id_seq',
			);
			const { res, status, json } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: VALID_PGLITE_CONN,
					query: 'SELECT bump_scratch() AS n;',
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(200);
			expect(json).toHaveBeenCalledWith({ rows: [{ n: 1 }], rowCount: 1 });
			expect(
				(await pgliteDb.query(
					'SELECT last_value, is_called FROM scratch_ids_id_seq',
				)).rows,
			).toEqual(before.rows);
			expect(
				(await pgliteDb.query(
					'SELECT count(*)::integer AS n FROM scratch_ids',
				)).rows,
			).toEqual([{ n: 0 }]);
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
