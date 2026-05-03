import { Router } from 'express';

export interface CLIRoute {
	command: string;
	method: string;
	path: string;
	handler: (req: any, res: any) => any;
}

export interface CLIResponse {
	statusCode: number;
	data: unknown;
}

/**
 * Walk an Express Router's internal layer stack and extract every registered
 * route.  The command name is derived from the full path by stripping the
 * leading `/api/` prefix and replacing `/` with `:`.
 *
 * Example: `/api/grading/compare/result-set` → `grading:compare:result-set`
 */
export function extractRoutes(router: Router, basePath: string): CLIRoute[] {
	const routes: CLIRoute[] = [];
	for (const layer of (router as any).stack ?? []) {
		if (!layer.route) continue;
		for (const method of Object.keys(layer.route.methods)) {
			const fullPath: string = basePath + layer.route.path;
			routes.push({
				command: fullPath.replace(/^\/api\//, '').replace(/\//g, ':'),
				method: method.toUpperCase(),
				path: fullPath,
				handler: layer.route.stack[layer.route.stack.length - 1].handle,
			});
		}
	}
	return routes;
}

/**
 * Invoke an Express route handler in-process with a mock req / res,
 * capturing the JSON response it produces.
 *
 * Handles three failure modes:
 *  1. The handler returns a rejected promise (normal async throw).
 *  2. The handler throws synchronously.
 *  3. The route's arrow wrapper does not `return` the inner async result,
 *     causing an unhandledRejection (common Express pattern).
 */
export function invokeHandler(
	handler: CLIRoute['handler'],
	body: unknown,
): Promise<CLIResponse> {
	return new Promise<CLIResponse>((resolve) => {
		let settled = false;
		const settle = (statusCode: number, data: unknown) => {
			if (!settled) {
				settled = true;
				process.removeListener('unhandledRejection', onUnhandled);
				resolve({ statusCode, data });
			}
		};

		// Catch fire-and-forget async handlers whose promise is not returned
		// by the wrapping arrow function (e.g. `(req, res) => { this.handle(req, res); }`).
		const onUnhandled = (err: unknown) => {
			const message = err instanceof Error ? err.message : String(err);
			settle(500, { message });
		};
		process.on('unhandledRejection', onUnhandled);

		const req = { body };
		let statusCode = 200;
		const res = {
			status(code: number) {
				statusCode = code;
				return res;
			},
			json(data: unknown) {
				settle(statusCode, data);
				return res;
			},
			send(data: unknown) {
				settle(statusCode, data);
				return res;
			},
		};

		try {
			const result = handler(req, res);
			if (result && typeof result.then === 'function') {
				result
					.then(() => {
						// Handler resolved without calling res.json/send —
						// clean up the listener (tests that never reply will
						// hang, which is the expected vitest behaviour).
						process.removeListener('unhandledRejection', onUnhandled);
					})
					.catch((err: Error) => {
						settle(500, { message: err.message });
					});
			}
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			settle(500, { message });
		}
	});
}
