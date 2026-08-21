/**
 * Tests for on-demand description-strategy generation in
 * TaskGenerationController.
 *
 * The generate endpoint historically produces all five description variants
 * on every request. Callers may now pass `descriptionStrategy` (single) or
 * `descriptionStrategies` (multiple) to generate only the requested variants;
 * unrequested `TaskResponse` description fields are omitted. When no
 * strategies are supplied the historical all-variants behaviour is preserved.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { Request, Response } from 'express';
import {
	TaskGenerationController,
	ALL_DESCRIPTION_STRATEGIES,
	resolveRequestedDescriptionStrategies,
} from '../../src/generation/task-generation-controller';
import { SQLQueryGenerationService } from '../../src/generation/query/sql-query-generation-service';
import { TaskDescriptionGenerationService } from '../../src/generation/description/task-description-generation-service';
import { DatabaseService } from '../../src/database/database-service';
import { DatabaseAnalyzer } from '../../src/database/database-analyzer';
import {
	databaseMetadata,
	pgliteInstances,
} from '../../src/database/internal-memory';
import {
	GenerationOptions,
	GptOptions,
	type ITaskConfiguration,
} from '../../src/shared/interfaces/domain';

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

const DB_ID = 'pglite-strategy-test-db';

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

function mockReq(body: unknown): Request {
	return { body } as Request;
}

function mockRes() {
	const json = vi.fn().mockReturnThis();
	const status = vi.fn().mockReturnValue({ json });
	return { res: { status, json } as unknown as Response, status, json };
}

function baseRequest(extra: Record<string, unknown> = {}) {
	return {
		connectionInfo: {
			type: 'pglite',
			databaseId: DB_ID,
			sqlContent: SIMPLE_DDL,
		},
		taskConfiguration: SIMPLE_TASK_CONFIG,
		...extra,
	};
}

/** Collect the (generationType, option) pairs the description service saw. */
function descriptionCalls(mockDescService: TaskDescriptionGenerationService) {
	const calls = (
		mockDescService.generateTaskFromQuery as unknown as ReturnType<
			typeof vi.fn
		>
	).mock.calls as Array<[{ generationType: string; option?: string }]>;
	return calls.map(([config]) => ({
		generationType: config.generationType,
		option: config.option,
	}));
}

// ---------------------------------------------------------------------------
// resolveRequestedDescriptionStrategies (pure function)
// ---------------------------------------------------------------------------

describe('resolveRequestedDescriptionStrategies', () => {
	it('defaults to all strategies when nothing is supplied', () => {
		const result = resolveRequestedDescriptionStrategies({});
		expect(result).toEqual(new Set(ALL_DESCRIPTION_STRATEGIES));
	});

	it('defaults to all strategies for empty/invalid input', () => {
		expect(
			resolveRequestedDescriptionStrategies({ descriptionStrategies: [] }),
		).toEqual(new Set(ALL_DESCRIPTION_STRATEGIES));
		expect(
			resolveRequestedDescriptionStrategies({
				descriptionStrategies: ['bogus' as any],
			}),
		).toEqual(new Set(ALL_DESCRIPTION_STRATEGIES));
	});

	it('respects a single descriptionStrategy', () => {
		expect(
			resolveRequestedDescriptionStrategies({ descriptionStrategy: 'template' }),
		).toEqual(new Set(['template']));
	});

	it('respects multiple descriptionStrategies', () => {
		expect(
			resolveRequestedDescriptionStrategies({
				descriptionStrategies: ['template', 'creative'],
			}),
		).toEqual(new Set(['template', 'creative']));
	});

	it('unions single and multiple, ignoring invalid values', () => {
		expect(
			resolveRequestedDescriptionStrategies({
				descriptionStrategy: 'hybrid',
				descriptionStrategies: ['template', 'nope' as any],
			}),
		).toEqual(new Set(['hybrid', 'template']));
	});
});

// ---------------------------------------------------------------------------
// Controller — on-demand generation
// ---------------------------------------------------------------------------

describe('TaskGenerationController — description strategy filtering', () => {
	let controller: TaskGenerationController;
	let mockQueryService: SQLQueryGenerationService;
	let mockDescService: TaskDescriptionGenerationService;

	beforeEach(() => {
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

	it('generates all five variants when no strategies are supplied', async () => {
		const { res, status, json } = mockRes();
		await controller.generateTaskForRequest(mockReq(baseRequest()), res);
		expect(status).toHaveBeenCalledWith(200);
		expect(mockDescService.generateTaskFromQuery).toHaveBeenCalledTimes(5);
		const body = json.mock.calls[0]?.[0] as any;
		for (const field of [
			'templateBasedDescription',
			'gptEntityRelationshipDescription',
			'gptSchemaBasedDescription',
			'gptCreativeDescription',
			'hybridDescription',
		]) {
			expect(body).toHaveProperty(field);
		}
	});

	it('generates only the template variant when requested', async () => {
		const { res, status, json } = mockRes();
		await controller.generateTaskForRequest(
			mockReq(baseRequest({ descriptionStrategies: ['template'] })),
			res,
		);
		expect(status).toHaveBeenCalledWith(200);
		expect(mockDescService.generateTaskFromQuery).toHaveBeenCalledTimes(1);
		expect(descriptionCalls(mockDescService)).toEqual([
			{ generationType: GenerationOptions.Template, option: undefined },
		]);
		const body = json.mock.calls[0]?.[0] as any;
		expect(body).toHaveProperty('query');
		expect(body).toHaveProperty('templateBasedDescription');
		expect(body).not.toHaveProperty('gptEntityRelationshipDescription');
		expect(body).not.toHaveProperty('gptSchemaBasedDescription');
		expect(body).not.toHaveProperty('gptCreativeDescription');
		expect(body).not.toHaveProperty('hybridDescription');
	});

	it('accepts the singular descriptionStrategy form', async () => {
		const { res, status } = mockRes();
		await controller.generateTaskForRequest(
			mockReq(baseRequest({ descriptionStrategy: 'hybrid' })),
			res,
		);
		expect(status).toHaveBeenCalledWith(200);
		expect(mockDescService.generateTaskFromQuery).toHaveBeenCalledTimes(1);
		expect(descriptionCalls(mockDescService)).toEqual([
			{ generationType: GenerationOptions.Hybrid, option: undefined },
		]);
	});

	it('generates multiple requested variants with correct engine options', async () => {
		const { res, status, json } = mockRes();
		await controller.generateTaskForRequest(
			mockReq(
				baseRequest({
					descriptionStrategies: ['entityRelationship', 'schemaBased', 'creative'],
				}),
			),
			res,
		);
		expect(status).toHaveBeenCalledWith(200);
		expect(mockDescService.generateTaskFromQuery).toHaveBeenCalledTimes(3);
		expect(descriptionCalls(mockDescService)).toEqual([
			{ generationType: GenerationOptions.LLM, option: GptOptions.MultiStep },
			{ generationType: GenerationOptions.LLM, option: GptOptions.Creative },
			{ generationType: GenerationOptions.LLM, option: GptOptions.Default },
		]);
		const body = json.mock.calls[0]?.[0] as any;
		expect(body).toHaveProperty('gptEntityRelationshipDescription');
		expect(body).toHaveProperty('gptSchemaBasedDescription');
		expect(body).toHaveProperty('gptCreativeDescription');
		expect(body).not.toHaveProperty('templateBasedDescription');
		expect(body).not.toHaveProperty('hybridDescription');
	});

	it('ignores unrecognised strategies and generates the valid ones', async () => {
		const { res, status } = mockRes();
		await controller.generateTaskForRequest(
			mockReq(
				baseRequest({ descriptionStrategies: ['template', 'bogus' as any] }),
			),
			res,
		);
		expect(status).toHaveBeenCalledWith(200);
		expect(mockDescService.generateTaskFromQuery).toHaveBeenCalledTimes(1);
		expect(descriptionCalls(mockDescService)).toEqual([
			{ generationType: GenerationOptions.Template, option: undefined },
		]);
	});
});
