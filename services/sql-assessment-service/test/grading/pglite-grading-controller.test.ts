/**
 * Regression tests for the validation-ordering bug in GradingController.
 *
 * Before the fix, `validateConnectionInfo` was called BEFORE the auto-analyze
 * block in both `gradeQuery` and `validateAndConnect`.  Any PGlite connection
 * was therefore rejected with INVALID_CONNECTION_INFO before auto-analyze
 * could run.
 *
 * After the fix the controller:
 *   1. Runs auto-analyze first (so PGlite can be registered if sqlContent is provided)
 *   2. Branches on `type === 'pglite'` and returns 400 with GRADING_PGLITE_NOT_SUPPORTED
 *   3. Calls `validateConnectionInfo` only in the Postgres branch
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import type { Request, Response } from 'express';
import { vi } from 'vitest';
import { GradingController } from '../../src/grading/grading-controller';
import { SQLQueryGradingService } from '../../src/grading/query-grading-service';
import { TaskDescriptionGenerationService } from '../../src/generation/description/task-description-generation-service';
import { ResultSetComparator } from '../../src/grading/result-set-comparator';
import { ASTComparator } from '../../src/grading/comparators/ast-comparator';
import { ExecutionPlanComparator } from '../../src/grading/comparators/execution-plan-comparator';
import { QueryProximityService } from '../../src/grading/query-proximity-service';
import { DatabaseService } from '../../src/database/database-service';
import { DatabaseAnalyzer } from '../../src/database/database-analyzer';
import {
	databaseMetadata,
	pgliteInstances,
} from '../../src/database/internal-memory';
import { JoinComparator } from '../../src/grading/join-comparator';
import { ExecutionPlanParser } from '../../src/grading/execution-plan-parser';
import { FeedbackAssembler } from '../../src/grading/feedback/feedback-assembler';
import { GradeCalculator } from '../../src/grading/grading/grade-calculator';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SIMPLE_DDL = `
CREATE TABLE products (
  id    SERIAL PRIMARY KEY,
  name  TEXT          NOT NULL,
  price NUMERIC(10,2)
);
INSERT INTO products (name, price) VALUES ('Widget', 9.99);
`;

const DB_ID = 'pglite-grading-test-db';

const PGLITE_CONN_WITH_SQL = {
	type: 'pglite' as const,
	databaseId: DB_ID,
	sqlContent: SIMPLE_DDL,
};

const PGLITE_CONN_NO_SQL = {
	type: 'pglite' as const,
	databaseId: DB_ID,
};

const REF_QUERY = 'SELECT name FROM products';
const STUDENT_QUERY = 'SELECT name FROM products';

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

describe('GradingController — PGlite validation ordering', () => {
	let controller: GradingController;

	beforeEach(() => {
		const joinComparator = new JoinComparator();
		controller = new GradingController(
			{} as SQLQueryGradingService,
			{} as TaskDescriptionGenerationService,
			new ResultSetComparator(),
			new ASTComparator(joinComparator),
			new ExecutionPlanComparator(new ExecutionPlanParser(), joinComparator),
			new QueryProximityService(),
			new DatabaseService(new DatabaseAnalyzer()),
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

	// ── POST /api/grading/grade ──────────────────────────────────────────────

	describe('gradeQuery', () => {
		it('returns 400 GRADING_PGLITE_NOT_SUPPORTED, not INVALID_CONNECTION_INFO', async () => {
			const { res, status, json } = mockRes();
			await controller.gradeQuery(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					gradingRequest: {
						referenceQuery: REF_QUERY,
						studentQuery: STUDENT_QUERY,
					},
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
			const message: string = json.mock.calls[0]?.[0]?.message ?? '';
			expect(message).not.toMatch(/invalid.*connection/i);
			expect(message).toMatch(/pglite/i);
		});

		it('runs auto-analyze before rejecting (PGlite DB is registered after the call)', async () => {
			const { res } = mockRes();
			await controller.gradeQuery(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					gradingRequest: {
						referenceQuery: REF_QUERY,
						studentQuery: STUDENT_QUERY,
					},
				}),
				res,
			);
			// auto-analyze ran → PGlite instance was registered
			expect(pgliteInstances.has(DB_ID)).toBe(true);
		});

		it('returns 400 GRADING_PGLITE_NOT_SUPPORTED even without sqlContent', async () => {
			const { res, status, json } = mockRes();
			await controller.gradeQuery(
				mockReq({
					connectionInfo: PGLITE_CONN_NO_SQL,
					gradingRequest: {
						referenceQuery: REF_QUERY,
						studentQuery: STUDENT_QUERY,
					},
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
			const message: string = json.mock.calls[0]?.[0]?.message ?? '';
			expect(message).toMatch(/pglite/i);
		});
	});

	// ── POST /api/grading/compare/result-set (via validateAndConnect) ─────────

	describe('compareResultSet', () => {
		it('returns 400 GRADING_PGLITE_NOT_SUPPORTED, not INVALID_CONNECTION_INFO', async () => {
			const { res, status, json } = mockRes();
			await controller.compareResultSet(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					referenceQuery: REF_QUERY,
					studentQuery: STUDENT_QUERY,
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
			const message: string = json.mock.calls[0]?.[0]?.message ?? '';
			expect(message).not.toMatch(/invalid.*connection/i);
			expect(message).toMatch(/pglite/i);
		});

		it('runs auto-analyze before rejecting (PGlite DB is registered after the call)', async () => {
			const { res } = mockRes();
			await controller.compareResultSet(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					referenceQuery: REF_QUERY,
					studentQuery: STUDENT_QUERY,
				}),
				res,
			);
			expect(pgliteInstances.has(DB_ID)).toBe(true);
		});
	});

	// ── POST /api/grading/compare/ast (via validateAndConnect) ───────────────

	describe('compareAST', () => {
		it('returns 400 GRADING_PGLITE_NOT_SUPPORTED, not INVALID_CONNECTION_INFO', async () => {
			const { res, status, json } = mockRes();
			await controller.compareAST(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					referenceQuery: REF_QUERY,
					studentQuery: STUDENT_QUERY,
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
			const message: string = json.mock.calls[0]?.[0]?.message ?? '';
			expect(message).not.toMatch(/invalid.*connection/i);
			expect(message).toMatch(/pglite/i);
		});
	});

	// ── POST /api/grading/compare/execution-plan (via validateAndConnect) ────

	describe('compareExecutionPlan', () => {
		it('returns 400 GRADING_PGLITE_NOT_SUPPORTED, not INVALID_CONNECTION_INFO', async () => {
			const { res, status, json } = mockRes();
			await controller.compareExecutionPlan(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					referenceQuery: REF_QUERY,
					studentQuery: STUDENT_QUERY,
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
			const message: string = json.mock.calls[0]?.[0]?.message ?? '';
			expect(message).not.toMatch(/invalid.*connection/i);
			expect(message).toMatch(/pglite/i);
		});
	});
});
