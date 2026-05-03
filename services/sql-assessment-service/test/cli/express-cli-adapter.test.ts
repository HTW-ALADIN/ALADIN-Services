import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Router } from 'express';
import {
	extractRoutes,
	invokeHandler,
	CLIRoute,
} from '../../src/cli/express-cli-adapter';

// ---------------------------------------------------------------------------
// extractRoutes
// ---------------------------------------------------------------------------

describe('extractRoutes', () => {
	it('discovers a single POST route', () => {
		const router = Router();
		router.post('/do-stuff', (_req, res) => res.json({ ok: true }));

		const routes = extractRoutes(router, '/api/test');
		expect(routes).toHaveLength(1);
		expect(routes[0]).toMatchObject({
			command: 'test:do-stuff',
			method: 'POST',
			path: '/api/test/do-stuff',
		});
		expect(typeof routes[0].handler).toBe('function');
	});

	it('discovers multiple routes on the same router', () => {
		const router = Router();
		router.get('/alpha', (_req, res) => res.json({}));
		router.post('/beta', (_req, res) => res.json({}));
		router.post('/gamma/delta', (_req, res) => res.json({}));

		const routes = extractRoutes(router, '/api/ns');
		const cmds = routes.map((r) => r.command);
		expect(cmds).toEqual(['ns:alpha', 'ns:beta', 'ns:gamma:delta']);
	});

	it('returns an empty array for a router with no routes', () => {
		const router = Router();
		expect(extractRoutes(router, '/api/empty')).toEqual([]);
	});

	it('derives the command from the full path, stripping /api/ prefix', () => {
		const router = Router();
		router.post('/compare/result-set', (_req, res) => res.json({}));

		const [route] = extractRoutes(router, '/api/grading');
		expect(route.command).toBe('grading:compare:result-set');
	});

	it('handles root path /', () => {
		const router = Router();
		router.get('/', (_req, res) => res.json({}));

		const [route] = extractRoutes(router, '/api/health');
		expect(route.path).toBe('/api/health/');
	});
});

// ---------------------------------------------------------------------------
// invokeHandler
// ---------------------------------------------------------------------------

describe('invokeHandler', () => {
	it('captures a 200 JSON response', async () => {
		const handler = (_req: any, res: any) => res.json({ answer: 42 });
		const result = await invokeHandler(handler, {});
		expect(result).toEqual({ statusCode: 200, data: { answer: 42 } });
	});

	it('captures a non-200 status code', async () => {
		const handler = (_req: any, res: any) =>
			res.status(400).json({ message: 'bad request' });
		const result = await invokeHandler(handler, {});
		expect(result.statusCode).toBe(400);
		expect(result.data).toEqual({ message: 'bad request' });
	});

	it('passes the body to the handler as req.body', async () => {
		const body = { connectionInfo: { host: 'localhost' } };
		const handler = (req: any, res: any) => res.json(req.body);
		const result = await invokeHandler(handler, body);
		expect(result.data).toEqual(body);
	});

	it('captures res.send() calls', async () => {
		const handler = (_req: any, res: any) => res.send('plain text');
		const result = await invokeHandler(handler, {});
		expect(result).toEqual({ statusCode: 200, data: 'plain text' });
	});

	it('captures async handler responses', async () => {
		const handler = async (_req: any, res: any) => {
			await new Promise((r) => setTimeout(r, 10));
			return res.status(201).json({ created: true });
		};
		const result = await invokeHandler(handler, {});
		expect(result.statusCode).toBe(201);
		expect(result.data).toEqual({ created: true });
	});

	it('returns 500 when an async handler rejects', async () => {
		const handler = async () => {
			throw new Error('boom');
		};
		const result = await invokeHandler(handler, {});
		expect(result.statusCode).toBe(500);
		expect(result.data).toEqual({ message: 'boom' });
	});

	it('preserves the last status code when status() is called multiple times', async () => {
		const handler = (_req: any, res: any) =>
			res.status(201).status(409).json({ conflict: true });
		const result = await invokeHandler(handler, {});
		expect(result.statusCode).toBe(409);
	});
});

// ---------------------------------------------------------------------------
// Integration: extractRoutes + invokeHandler round-trip
// ---------------------------------------------------------------------------

describe('extractRoutes + invokeHandler round-trip', () => {
	it('can invoke a discovered route handler and get a response', async () => {
		const router = Router();
		router.post('/echo', (req, res) => res.json({ echo: req.body }));

		const [route] = extractRoutes(router, '/api/test');
		const result = await invokeHandler(route.handler, { ping: 'pong' });
		expect(result.statusCode).toBe(200);
		expect(result.data).toEqual({ echo: { ping: 'pong' } });
	});

	it('works with handlers that validate input and return 400', async () => {
		const router = Router();
		router.post('/strict', (req, res) => {
			if (!req.body?.name)
				return res.status(400).json({ message: 'name required' });
			return res.json({ hello: req.body.name });
		});

		const [route] = extractRoutes(router, '/api/v');

		const bad = await invokeHandler(route.handler, {});
		expect(bad.statusCode).toBe(400);

		const good = await invokeHandler(route.handler, { name: 'world' });
		expect(good.statusCode).toBe(200);
		expect(good.data).toEqual({ hello: 'world' });
	});
});
