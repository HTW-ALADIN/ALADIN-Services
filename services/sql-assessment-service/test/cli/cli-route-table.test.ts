import { describe, it, expect } from 'vitest';
import { createControllers } from '../../src/bootstrap';
import {
	extractRoutes,
	invokeHandler,
} from '../../src/cli/express-cli-adapter';

/**
 * Build the full route table identical to the CLI entry point.
 */
function buildRouteTable() {
	const c = createControllers();
	return [
		...extractRoutes(c.connectionController.router, '/api/database'),
		...extractRoutes(c.taskGenerationController.router, '/api/generation'),
		...extractRoutes(c.gradingController.router, '/api/grading'),
		...extractRoutes(c.descriptionController.router, '/api/description'),
		...extractRoutes(c.queryExecutionController.router, '/api/query'),
	];
}

// The expected commands in the order defined by registerControllers' mount
// prefixes and each controller's initializeRoutes() order.
const EXPECTED_COMMANDS = [
	'database:analyze-database',
	'generation:generate',
	'grading:grade',
	'grading:compare:result-set',
	'grading:compare:ast',
	'grading:compare:execution-plan',
	'description:template',
	'description:llm:default',
	'description:llm:creative',
	'description:llm:multi-step',
	'description:hybrid',
	'query:execute',
];

describe('CLI route table (integration)', () => {
	const routes = buildRouteTable();

	it('discovers all expected commands', () => {
		const commands = routes.map((r) => r.command);
		expect(commands).toEqual(EXPECTED_COMMANDS);
	});

	it('every route has a callable handler', () => {
		for (const route of routes) {
			expect(typeof route.handler).toBe('function');
		}
	});

	it('every route has a non-empty method and path', () => {
		for (const route of routes) {
			expect(route.method).toMatch(/^(GET|POST|PUT|PATCH|DELETE)$/);
			expect(route.path).toMatch(/^\/api\//);
		}
	});

	it('commands are unique', () => {
		const commands = routes.map((r) => r.command);
		expect(new Set(commands).size).toBe(commands.length);
	});

	// Verify that invoking a real controller handler (query:execute) with
	// an invalid body returns a 400 from the controller's validation logic.
	it('query:execute returns 400 for a body missing connectionInfo', async () => {
		const route = routes.find((r) => r.command === 'query:execute')!;
		const result = await invokeHandler(route.handler, { query: 'SELECT 1' });
		expect(result.statusCode).toBe(400);
		expect(result.data).toHaveProperty('message');
	});

	it('database:analyze-database returns 400 for incomplete connectionInfo', async () => {
		const route = routes.find(
			(r) => r.command === 'database:analyze-database',
		)!;
		const result = await invokeHandler(route.handler, { connectionInfo: {} });
		expect(result.statusCode).toBe(400);
		expect(result.data).toHaveProperty('message');
	});

	it('grading:grade returns 400 for incomplete connectionInfo', async () => {
		const route = routes.find((r) => r.command === 'grading:grade')!;
		const result = await invokeHandler(route.handler, {
			connectionInfo: {},
			gradingRequest: {},
		});
		expect(result.statusCode).toBe(400);
		expect(result.data).toHaveProperty('message');
	});

	it('database:analyze-database returns 400 for completely missing body', async () => {
		const route = routes.find(
			(r) => r.command === 'database:analyze-database',
		)!;
		const result = await invokeHandler(route.handler, {});
		// Controller validates connectionInfo → returns 400 for missing connection info
		expect(result.statusCode).toBe(400);
		expect(result.data).toHaveProperty('message');
	});

	it('description:template returns 400 for missing fields', async () => {
		const route = routes.find((r) => r.command === 'description:template')!;
		const result = await invokeHandler(route.handler, {});
		expect(result.statusCode).toBe(400);
		expect(result.data).toHaveProperty('message');
	});
});
