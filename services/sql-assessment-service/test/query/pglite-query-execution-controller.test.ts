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
