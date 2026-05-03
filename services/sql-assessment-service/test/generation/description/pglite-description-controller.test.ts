/**
 * Tests for DescriptionController with PGlite + auto-analyze.
 *
 * When `sqlContent` is included in a PGlite `connectionInfo`, each description
 * endpoint must automatically analyse the in-process database and proceed
 * without a prior `/api/database/analyze-database` call.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { Request, Response } from 'express';
import { DescriptionController } from '../../../src/generation/description/description-controller';
import { TaskDescriptionGenerationService } from '../../../src/generation/description/task-description-generation-service';
import { TemplateTaskDescriptionGenerationEngine } from '../../../src/generation/description/template-task-description-generation-engine';
import { DatabaseService } from '../../../src/database/database-service';
import { DatabaseAnalyzer } from '../../../src/database/database-analyzer';
import {
	databaseMetadata,
	pgliteInstances,
} from '../../../src/database/internal-memory';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** Minimal schema — one table so the template engine has something to work with. */
const SIMPLE_DDL = `
CREATE TABLE employees (
  id         SERIAL PRIMARY KEY,
  first_name TEXT NOT NULL,
  salary     NUMERIC(10,2)
);
INSERT INTO employees (first_name, salary) VALUES ('Alice', 50000), ('Bob', 60000);
`;

const DB_ID = 'auto-analyze-desc-db';

// A simple SELECT that the template engine can process.
const SIMPLE_QUERY = 'SELECT first_name, salary FROM employees';

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

describe('DescriptionController — PGlite auto-analyze', () => {
	let controller: DescriptionController;

	beforeEach(() => {
		const databaseService = new DatabaseService(new DatabaseAnalyzer());
		const templateEngine = new TemplateTaskDescriptionGenerationEngine();
		const generationService = new TaskDescriptionGenerationService(
			undefined,
			templateEngine,
		);
		controller = new DescriptionController(generationService, databaseService);
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

	// ── Template endpoint ────────────────────────────────────────────────────

	describe('POST /api/description/template', () => {
		it('returns 200 when sqlContent is provided in PGlite connectionInfo (no prior analyze)', async () => {
			const { res, status } = mockRes();
			await controller.generateTemplateDescription(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: DB_ID,
						sqlContent: SIMPLE_DDL,
					},
					query: SIMPLE_QUERY,
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(200);
		});

		it('auto-registers PGlite instance after a successful template description', async () => {
			const { res } = mockRes();
			await controller.generateTemplateDescription(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: DB_ID,
						sqlContent: SIMPLE_DDL,
					},
					query: SIMPLE_QUERY,
				}),
				res,
			);
			expect(pgliteInstances.has(DB_ID)).toBe(true);
		});

		it('returns 400 when PGlite databaseId is missing', async () => {
			const { res, status } = mockRes();
			await controller.generateTemplateDescription(
				mockReq({
					connectionInfo: { type: 'pglite', sqlContent: SIMPLE_DDL },
					query: SIMPLE_QUERY,
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when query is missing', async () => {
			const { res, status } = mockRes();
			await controller.generateTemplateDescription(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: DB_ID,
						sqlContent: SIMPLE_DDL,
					},
					// no query field
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when PGlite DB is not registered and sqlContent is absent', async () => {
			const { res, status } = mockRes();
			await controller.generateTemplateDescription(
				mockReq({
					connectionInfo: { type: 'pglite', databaseId: DB_ID },
					query: SIMPLE_QUERY,
				}),
				res,
			);
			// ensureAnalyzed skips (no sqlContent), then isDatabaseRegistered → false → 400
			expect(status).toHaveBeenCalledWith(400);
		});
	});

	// ── Hybrid endpoint ──────────────────────────────────────────────────────

	describe('POST /api/description/hybrid', () => {
		it('returns 200 with PGlite + sqlContent', async () => {
			const { res, status } = mockRes();
			await controller.generateHybridDescription(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: DB_ID,
						sqlContent: SIMPLE_DDL,
					},
					query: SIMPLE_QUERY,
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(200);
		});
	});
});
