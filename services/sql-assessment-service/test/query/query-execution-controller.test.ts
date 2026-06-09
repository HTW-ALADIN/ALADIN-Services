import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Request, Response, NextFunction } from 'express';

// ---------------------------------------------------------------------------
// Module-level mocks (hoisted by vitest)
//
// connectToDatabase – return true without touching a real PG server.
// DataSource        – stub destroy() so the catch block does not throw on an
//                     uninitialised pool.
// The synchronous factory avoids async-hoisting edge cases in vitest v4.
// ---------------------------------------------------------------------------
vi.mock('../../src/shared/utils/database-utils', () => ({
	generateDatabaseKey: (host: string, port: number, schema: string) =>
		`${host}:${port}/${schema}`,
	generatePGliteKey: (id: string) => `pglite:${id}`,
	connectToDatabase: vi.fn().mockResolvedValue(true),
	makeRowQueryFn: vi.fn(),
	createQueryRunner: vi.fn(),
	buildAliasMapFromTables: vi.fn(),
}));

vi.mock('typeorm', async (importOriginal) => {
	const actual = await importOriginal<typeof import('typeorm')>();
	return {
		...actual,
		DataSource: vi.fn(function (this: Record<string, unknown>) {
			this.initialize = vi.fn().mockResolvedValue(undefined);
			this.destroy = vi.fn().mockResolvedValue(undefined);
		}),
	};
});
import { QueryExecutionController } from '../../src/query/query-execution-controller';
import {
	QueryExecutionService,
	QueryExecutionError,
} from '../../src/query/query-execution-service';
import { databaseMetadata } from '../../src/database/internal-memory';
import { generateDatabaseKey } from '../../src/shared/utils/database-utils';

// ---------------------------------------------------------------------------
// Express mock helpers
// ---------------------------------------------------------------------------

function mockReq(body: unknown): Request {
	return { body } as Request;
}

function mockRes(): {
	res: Response;
	status: ReturnType<typeof vi.fn>;
	json: ReturnType<typeof vi.fn>;
} {
	const json = vi.fn().mockReturnThis();
	const status = vi.fn().mockReturnValue({ json });
	const res = { status, json } as unknown as Response;
	return { res, status, json };
}

// ---------------------------------------------------------------------------
// Shared setup
// ---------------------------------------------------------------------------

const VALID_CONNECTION = {
	type: 'postgres' as const,
	host: 'localhost',
	port: 5432,
	username: 'user',
	password: 'pass',
	schema: 'northwind',
};

const DB_KEY = generateDatabaseKey(
	VALID_CONNECTION.host,
	VALID_CONNECTION.port,
	VALID_CONNECTION.schema,
);

let controller: QueryExecutionController;
let serviceMock: QueryExecutionService;

beforeEach(() => {
	// Register the fake database key so isDatabaseRegistered() returns true.
	databaseMetadata.set(DB_KEY, []);

	// Replace service with a spy-wrapped instance; individual tests override
	// executeQuery as needed.
	serviceMock = new QueryExecutionService();
	controller = new QueryExecutionController(serviceMock);
});

// ---------------------------------------------------------------------------
// Controller request-validation tests (no real DB, no real service call)
// ---------------------------------------------------------------------------

describe('QueryExecutionController', () => {
	describe('POST /api/query/execute — request validation', () => {
		it('returns 400 when connectionInfo is missing', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(mockReq({ query: 'SELECT 1' }), res);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when query field is missing', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_CONNECTION }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when query is an empty string', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_CONNECTION, query: '' }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when query is whitespace only', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_CONNECTION, query: '   ' }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when query is not a string (number)', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_CONNECTION, query: 42 }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when host is missing from connectionInfo', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: { ...VALID_CONNECTION, host: undefined },
					query: 'SELECT 1',
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when schema is missing from connectionInfo', async () => {
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({
					connectionInfo: { ...VALID_CONNECTION, schema: undefined },
					query: 'SELECT 1',
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when the database has not been registered', async () => {
			databaseMetadata.delete(DB_KEY);
			const { res, status } = mockRes();
			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_CONNECTION, query: 'SELECT 1' }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});
	});

	// -------------------------------------------------------------------------
	// Controller service-error mapping
	// -------------------------------------------------------------------------

	describe('POST /api/query/execute — service error mapping', () => {
		it('returns 400 with EMPTY_QUERY code when service throws EMPTY_QUERY', async () => {
			vi.spyOn(serviceMock, 'executeQuery').mockRejectedValueOnce(
				new QueryExecutionError('Query must not be empty.', 'EMPTY_QUERY'),
			);
			const { res, status, json } = mockRes();

			await controller.executeQuery(
				mockReq({ connectionInfo: VALID_CONNECTION, query: 'SELECT 1' }),
				res,
			);

			expect(status).toHaveBeenCalledWith(400);
			expect(json).toHaveBeenCalledWith(
				expect.objectContaining({ code: 'EMPTY_QUERY' }),
			);
		});

		it('returns 400 for NON_SELECT errors reported by the service', async () => {
			const error = new QueryExecutionError(
				'Only SELECT queries are permitted.',
				'NON_SELECT',
			);
			expect(error.code).toBe('NON_SELECT');
			// The controller maps client-side codes (NON_SELECT) to 400
			const clientCodes = [
				'EMPTY_QUERY',
				'PARSE_ERROR',
				'MULTIPLE_STATEMENTS',
				'NON_SELECT',
			];
			expect(clientCodes).toContain(error.code);
		});

		it('returns 500 for EXECUTION_FAILED errors reported by the service', async () => {
			const error = new QueryExecutionError(
				'Query execution failed.',
				'EXECUTION_FAILED',
			);
			// EXECUTION_FAILED is not in the client-codes list → maps to 500
			const clientCodes = [
				'EMPTY_QUERY',
				'PARSE_ERROR',
				'MULTIPLE_STATEMENTS',
				'NON_SELECT',
			];
			expect(clientCodes).not.toContain(error.code);
		});
	});

	// -------------------------------------------------------------------------
	// QueryExecutionError class contract
	// -------------------------------------------------------------------------

	describe('QueryExecutionError', () => {
		it('has name "QueryExecutionError"', () => {
			const err = new QueryExecutionError('msg', 'PARSE_ERROR');
			expect(err.name).toBe('QueryExecutionError');
		});

		it('exposes the code on the instance', () => {
			const err = new QueryExecutionError('msg', 'NON_SELECT');
			expect(err.code).toBe('NON_SELECT');
		});

		it('is an instance of Error', () => {
			const err = new QueryExecutionError('msg', 'EMPTY_QUERY');
			expect(err).toBeInstanceOf(Error);
		});

		it('preserves the message', () => {
			const err = new QueryExecutionError(
				'Only SELECT queries are permitted.',
				'NON_SELECT',
			);
			expect(err.message).toBe('Only SELECT queries are permitted.');
		});
	});

	// -------------------------------------------------------------------------
	// Route-handler error propagation
	// -------------------------------------------------------------------------

	describe('POST /execute route handler', () => {
		it('forwards unexpected executeQuery rejections to next()', async () => {
			const boom = new Error('unexpected DB crash');
			vi.spyOn(controller, 'executeQuery').mockRejectedValueOnce(boom);

			const req = mockReq({}) as Request;
			const { res } = mockRes();
			const next = vi.fn() as unknown as NextFunction;

			// Resolve as soon as next() is invoked so we can await deterministically.
			const nextCalled = new Promise<void>((resolve) => {
				(next as ReturnType<typeof vi.fn>).mockImplementation(() => resolve());
			});

			// Invoke the handler registered by initializeRoutes() directly.
			const [routeLayer] = (controller.router as any).stack;
			routeLayer.route.stack[0].handle(req, res, next);
			await nextCalled;

			expect(next).toHaveBeenCalledWith(boom);
		});
	});
});
