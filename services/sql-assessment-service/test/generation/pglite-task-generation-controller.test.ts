/**
 * Tests for TaskGenerationController with PGlite + auto-analyze.
 *
 * Regression tests for the validation-ordering bug reported in code review:
 * `validateConnectionInfo` was called BEFORE the auto-analyze block, so any
 * `{ type: 'pglite', ... }` request was rejected as INVALID_CONNECTION_INFO
 * before it could be analyzed/registered.
 *
 * After the fix the controller:
 *   1. Runs auto-analyze first (so PGlite is registered if sqlContent is given)
 *   2. Branches on `type === 'pglite'` vs Postgres
 *   3. Calls `validateConnectionInfo` only in the Postgres branch
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { Request, Response } from 'express';
import { TaskGenerationController } from '../../src/generation/task-generation-controller';
import { SQLQueryGenerationService } from '../../src/generation/query/sql-query-generation-service';
import { TaskDescriptionGenerationService } from '../../src/generation/description/task-description-generation-service';
import { DatabaseService } from '../../src/database/database-service';
import { DatabaseAnalyzer } from '../../src/database/database-analyzer';
import {
	databaseMetadata,
	pgliteInstances,
} from '../../src/database/internal-memory';
import type { ITaskConfiguration } from '../../src/shared/interfaces/domain';

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

const DB_ID = 'pglite-gen-test-db';

/** Minimal valid task config — no joins, no predicates, just columns. */
const SIMPLE_TASK_CONFIG: ITaskConfiguration = {
	aggregation: false,
	orderby: false,
	joinDepth: 0,
	joinTypes: [],
	predicateCount: 0,
	groupby: false,
	having: false,
	columnCount: 1,
	operationTypes: [],
};

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

describe('TaskGenerationController — PGlite auto-analyze', () => {
	let controller: TaskGenerationController;
	let mockQueryService: SQLQueryGenerationService;
	let mockDescService: TaskDescriptionGenerationService;

	beforeEach(() => {
		// Stub the generation services so unit tests don't need real DB queries
		mockQueryService = {
			validateConfiguration: vi.fn().mockReturnValue([true, '']),
			generateContextBasedQuery: vi
				.fn()
				.mockResolvedValue(['SELECT name FROM products', {}]),
		} as unknown as SQLQueryGenerationService;

		mockDescService = {
			generateTaskFromQuery: vi
				.fn()
				.mockResolvedValue('Retrieve all product names.'),
		} as unknown as TaskDescriptionGenerationService;

		const databaseService = new DatabaseService(new DatabaseAnalyzer());
		controller = new TaskGenerationController(
			mockQueryService,
			mockDescService,
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

	// ── Regression: validation ordering ──────────────────────────────────────

	it('does NOT reject PGlite request as INVALID_CONNECTION_INFO', async () => {
		const { res, status } = mockRes();
		await controller.generateTaskForRequest(
			mockReq({
				connectionInfo: {
					type: 'pglite',
					databaseId: DB_ID,
					sqlContent: SIMPLE_DDL,
				},
				taskConfiguration: SIMPLE_TASK_CONFIG,
			}),
			res,
		);
		// The fix: must not return 400 with INVALID_CONNECTION_INFO
		// (previously `validateConnectionInfo` ran first and rejected PGlite)
		if (status.mock.calls[0]?.[0] === 400) {
			const message: string =
				(status.mock.results[0].value.json.mock.calls[0]?.[0] as any)
					?.message ?? '';
			expect(message).not.toMatch(/invalid.*connection/i);
		}
	});

	it('auto-registers PGlite DB and reaches query generation', async () => {
		const { res, status } = mockRes();
		await controller.generateTaskForRequest(
			mockReq({
				connectionInfo: {
					type: 'pglite',
					databaseId: DB_ID,
					sqlContent: SIMPLE_DDL,
				},
				taskConfiguration: SIMPLE_TASK_CONFIG,
			}),
			res,
		);
		expect(mockQueryService.generateContextBasedQuery).toHaveBeenCalled();
		expect(status).toHaveBeenCalledWith(200);
	});

	it('returns 200 with all description fields populated for PGlite', async () => {
		const { res, status, json } = mockRes();
		await controller.generateTaskForRequest(
			mockReq({
				connectionInfo: {
					type: 'pglite',
					databaseId: DB_ID,
					sqlContent: SIMPLE_DDL,
				},
				taskConfiguration: SIMPLE_TASK_CONFIG,
			}),
			res,
		);
		expect(status).toHaveBeenCalledWith(200);
		const body = json.mock.calls[0]?.[0] as any;
		expect(body).toHaveProperty('query');
		expect(body).toHaveProperty('templateBasedDescription');
		expect(body).toHaveProperty('gptEntityRelationshipDescription');
	});

	it('returns 400 when PGlite databaseId is missing', async () => {
		const { res, status } = mockRes();
		await controller.generateTaskForRequest(
			mockReq({
				connectionInfo: { type: 'pglite', sqlContent: SIMPLE_DDL },
				taskConfiguration: SIMPLE_TASK_CONFIG,
			}),
			res,
		);
		expect(status).toHaveBeenCalledWith(400);
	});

	it('returns 400 when PGlite DB is not registered and sqlContent is absent', async () => {
		const { res, status } = mockRes();
		await controller.generateTaskForRequest(
			mockReq({
				connectionInfo: { type: 'pglite', databaseId: DB_ID },
				taskConfiguration: SIMPLE_TASK_CONFIG,
			}),
			res,
		);
		// ensureAnalyzed skips (no sqlContent), then isDatabaseRegistered → false
		expect(status).toHaveBeenCalledWith(400);
	});
});
