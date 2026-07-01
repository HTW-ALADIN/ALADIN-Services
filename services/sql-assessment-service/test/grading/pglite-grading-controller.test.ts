/**
 * Integration tests for GradingController running against an in-process PGlite
 * database.
 *
 * Previously the controller rejected any PGlite connection with
 * GRADING_PGLITE_NOT_SUPPORTED (400).  Grading now routes PGlite connections
 * through the shared `pgliteInstances` registry via a backend-agnostic
 * `RowQueryFn`, so all four grading endpoints work end-to-end without an
 * external PostgreSQL server.
 *
 * These tests exercise the real grading pipeline (executability, result-set,
 * AST and EXPLAIN-based execution-plan comparison) against a real PGlite
 * instance seeded from DDL.
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
INSERT INTO products (name, price) VALUES
  ('Widget', 9.99),
  ('Gadget', 19.99),
  ('Gizmo', 29.99);
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

const REF_QUERY = 'SELECT name FROM products WHERE price > 15 ORDER BY name';
const CORRECT_STUDENT_QUERY =
	'SELECT name FROM products WHERE price > 15 ORDER BY name';
const WRONG_STUDENT_QUERY = 'SELECT name FROM products ORDER BY name';
const NON_EXECUTABLE_QUERY = 'SELECT name FROM no_such_table';

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

/** Reads the JSON payload of the first `res.json(...)` call. */
function firstJson(json: ReturnType<typeof mockRes>['json']): any {
	return json.mock.calls[0]?.[0];
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('GradingController — PGlite backend', () => {
	let controller: GradingController;

	beforeEach(() => {
		const joinComparator = new JoinComparator();
		const resultSetComparator = new ResultSetComparator();
		const astComparator = new ASTComparator(joinComparator);
		const executionPlanComparator = new ExecutionPlanComparator(
			new ExecutionPlanParser(),
			joinComparator,
		);
		const queryGradingService = new SQLQueryGradingService(
			resultSetComparator,
			astComparator,
			executionPlanComparator,
			new GradeCalculator(),
			new FeedbackAssembler(),
		);

		controller = new GradingController(
			queryGradingService,
			// Task-description generation is a no-op stub (no OPENAI key in tests):
			// gradeQuery only calls it for non-equivalent queries, and the stub
			// returns undefined so no description is appended.
			{
				generateTaskFromQuery: vi.fn().mockResolvedValue(undefined),
			} as unknown as TaskDescriptionGenerationService,
			resultSetComparator,
			astComparator,
			executionPlanComparator,
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
		it('grades an identical student query as fully equivalent (grade 7)', async () => {
			const { res, status, json } = mockRes();
			await controller.gradeQuery(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					gradingRequest: {
						referenceQuery: REF_QUERY,
						studentQuery: CORRECT_STUDENT_QUERY,
					},
				}),
				res,
			);

			expect(status).toHaveBeenCalledWith(200);
			const body = firstJson(json);
			expect(body.comparisonResult.grade).toBe(7);
			expect(body.comparisonResult.equivalent).toBe(true);
		});

		it('penalises a student query with a missing WHERE clause', async () => {
			const { res, status, json } = mockRes();
			await controller.gradeQuery(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					gradingRequest: {
						referenceQuery: REF_QUERY,
						studentQuery: WRONG_STUDENT_QUERY,
					},
				}),
				res,
			);

			expect(status).toHaveBeenCalledWith(200);
			const body = firstJson(json);
			expect(body.comparisonResult.equivalent).toBe(false);
			expect(body.comparisonResult.grade).toBeLessThan(7);
		});

		it('returns grade 0 with executability feedback for a non-executable query', async () => {
			const { res, status, json } = mockRes();
			await controller.gradeQuery(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					gradingRequest: {
						referenceQuery: REF_QUERY,
						studentQuery: NON_EXECUTABLE_QUERY,
					},
				}),
				res,
			);

			expect(status).toHaveBeenCalledWith(200);
			const body = firstJson(json);
			expect(body.comparisonResult.grade).toBe(0);
			// executability feedback must be populated (regression: PGlite errors
			// are plain Error objects, not TypeORM QueryFailedError)
			expect(
				body.comparisonResult.feedbackDetails.general.executability,
			).toBeDefined();
		});

		it('does not close the shared PGlite instance after grading', async () => {
			const { res } = mockRes();
			await controller.gradeQuery(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					gradingRequest: {
						referenceQuery: REF_QUERY,
						studentQuery: CORRECT_STUDENT_QUERY,
					},
				}),
				res,
			);

			// Instance must still be registered and usable after the request.
			const db = pgliteInstances.get(DB_ID);
			expect(db).toBeDefined();
			const result = await db!.query('SELECT COUNT(*)::int AS c FROM products');
			expect((result.rows[0] as any).c).toBe(3);
		});

		it('returns 400 DATABASE_NOT_REGISTERED when no sqlContent and DB is unknown', async () => {
			const { res, status, json } = mockRes();
			await controller.gradeQuery(
				mockReq({
					connectionInfo: PGLITE_CONN_NO_SQL,
					gradingRequest: {
						referenceQuery: REF_QUERY,
						studentQuery: CORRECT_STUDENT_QUERY,
					},
				}),
				res,
			);

			expect(status).toHaveBeenCalledWith(400);
			const message: string = firstJson(json)?.message ?? '';
			// No longer a "PGlite not supported" rejection.
			expect(message).not.toMatch(/pglite.*not supported/i);
		});
	});

	// ── POST /api/grading/compare/result-set ─────────────────────────────────

	describe('compareResultSet', () => {
		it('reports match=true for equivalent result sets', async () => {
			const { res, status, json } = mockRes();
			await controller.compareResultSet(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					referenceQuery: REF_QUERY,
					studentQuery: CORRECT_STUDENT_QUERY,
				}),
				res,
			);

			expect(status).toHaveBeenCalledWith(200);
			expect(firstJson(json).match).toBe(true);
		});

		it('reports match=false for differing result sets', async () => {
			const { res, status, json } = mockRes();
			await controller.compareResultSet(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					referenceQuery: REF_QUERY,
					studentQuery: WRONG_STUDENT_QUERY,
				}),
				res,
			);

			expect(status).toHaveBeenCalledWith(200);
			expect(firstJson(json).match).toBe(false);
		});
	});

	// ── POST /api/grading/compare/ast ────────────────────────────────────────

	describe('compareAST', () => {
		it('compares ASTs without needing a live query', async () => {
			const { res, status, json } = mockRes();
			await controller.compareAST(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					referenceQuery: REF_QUERY,
					studentQuery: CORRECT_STUDENT_QUERY,
				}),
				res,
			);

			expect(status).toHaveBeenCalledWith(200);
			expect(firstJson(json).columnsMatch).toBe(true);
		});
	});

	// ── POST /api/grading/compare/execution-plan ─────────────────────────────

	describe('compareExecutionPlan', () => {
		it('runs EXPLAIN on PGlite and reports plansMatch=true for identical plans', async () => {
			const { res, status, json } = mockRes();
			await controller.compareExecutionPlan(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					referenceQuery: REF_QUERY,
					studentQuery: CORRECT_STUDENT_QUERY,
				}),
				res,
			);

			expect(status).toHaveBeenCalledWith(200);
			const body = firstJson(json);
			expect(body.plansMatch).toBe(true);
			expect(body.penaltyPoints).toBe(0);
		});

		it('detects a differing WHERE clause via EXPLAIN and adds penalty points', async () => {
			const { res, status, json } = mockRes();
			await controller.compareExecutionPlan(
				mockReq({
					connectionInfo: PGLITE_CONN_WITH_SQL,
					referenceQuery: REF_QUERY,
					studentQuery: WRONG_STUDENT_QUERY,
				}),
				res,
			);

			expect(status).toHaveBeenCalledWith(200);
			const body = firstJson(json);
			expect(body.plansMatch).toBe(false);
			expect(body.penaltyPoints).toBeGreaterThan(0);
		});
	});
});
