/**
 * Tests for the auto-analyze feature in QueryExecutionController.
 *
 * When `sqlContent` is included in a PGlite `connectionInfo`, the controller
 * must automatically create/replace the PGlite instance and register its
 * schema — without the caller having to invoke `/api/database/analyze-database`
 * first.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { Request, Response } from 'express';
import { QueryExecutionController } from '../../src/query/query-execution-controller';
import { QueryExecutionService } from '../../src/query/query-execution-service';
import { DatabaseService } from '../../src/database/database-service';
import { DatabaseAnalyzer } from '../../src/database/database-analyzer';
import {
	databaseMetadata,
	pgliteInstances,
} from '../../src/database/internal-memory';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SIMPLE_DDL = `
CREATE TABLE products (
  id    SERIAL PRIMARY KEY,
  name  TEXT NOT NULL,
  price NUMERIC(10,2)
);
INSERT INTO products (name, price) VALUES ('Widget', 9.99), ('Gadget', 19.99);
`;

const DB_ID = 'auto-analyze-query-db';

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

describe('QueryExecutionController — PGlite auto-analyze', () => {
	let controller: QueryExecutionController;

	beforeEach(() => {
		const databaseService = new DatabaseService(new DatabaseAnalyzer());
		controller = new QueryExecutionController(
			new QueryExecutionService(),
			databaseService,
		);
		databaseMetadata.clear();
		pgliteInstances.clear();
	});

	afterEach(async () => {
		for (const db of pgliteInstances.values()) {
			await db?.close?.();
		}
		pgliteInstances.clear();
		databaseMetadata.clear();
	});

	it('executes a query successfully when sqlContent is provided (no prior analyze-database call)', async () => {
		const { res, status, json } = mockRes();
		await controller.executeQuery(
			mockReq({
				connectionInfo: {
					type: 'pglite',
					databaseId: DB_ID,
					sqlContent: SIMPLE_DDL,
				},
				query: 'SELECT * FROM products ORDER BY id',
			}),
			res,
		);

		expect(status).toHaveBeenCalledWith(200);
		const jsonArg = json.mock.calls[0][0];
		expect(jsonArg).toHaveProperty('rows');
		expect(jsonArg.rows).toHaveLength(2);
		expect(jsonArg.rows[0]).toHaveProperty('name', 'Widget');
	});

	it('auto-registers the database in internal-memory after execute with sqlContent', async () => {
		const { res } = mockRes();
		await controller.executeQuery(
			mockReq({
				connectionInfo: {
					type: 'pglite',
					databaseId: DB_ID,
					sqlContent: SIMPLE_DDL,
				},
				query: 'SELECT 1 AS n',
			}),
			res,
		);

		expect(pgliteInstances.has(DB_ID)).toBe(true);
	});

	it('returns 400 when PGlite databaseId is absent and no prior registration', async () => {
		const { res, status } = mockRes();
		await controller.executeQuery(
			mockReq({
				connectionInfo: { type: 'pglite' },
				query: 'SELECT 1',
			}),
			res,
		);
		expect(status).toHaveBeenCalledWith(400);
	});

	it('returns 500 when sqlContent is syntactically invalid SQL', async () => {
		const { res, status } = mockRes();
		await controller.executeQuery(
			mockReq({
				connectionInfo: {
					type: 'pglite',
					databaseId: DB_ID,
					sqlContent: 'INVALID SQL @@##',
				},
				query: 'SELECT 1',
			}),
			res,
		);
		expect(status).toHaveBeenCalledWith(500);
	});
});
