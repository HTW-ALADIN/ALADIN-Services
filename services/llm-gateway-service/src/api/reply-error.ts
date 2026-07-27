import type { FastifyReply } from 'fastify';
import { GatewayRequestError } from '../core/types.js';

/**
 * Maps errors onto HTTP responses, propagating the upstream LLM Gateway
 * status (400/401/403/429/5xx) via GatewayRequestError instead of collapsing
 * every failure into a single generic status code.
 */
export function replyWithError(
	reply: FastifyReply,
	err: unknown
): FastifyReply {
	if (err instanceof GatewayRequestError) {
		return reply.status(err.status).send({
			statusCode: err.status,
			error: httpErrorName(err.status),
			message: err.message,
			code: err.code,
		});
	}

	const message = err instanceof Error ? err.message : String(err);
	return reply.status(400).send({
		statusCode: 400,
		error: 'Bad Request',
		message,
	});
}

function httpErrorName(status: number): string {
	switch (status) {
		case 400:
			return 'Bad Request';
		case 401:
			return 'Unauthorized';
		case 403:
			return 'Forbidden';
		case 404:
			return 'Not Found';
		case 429:
			return 'Too Many Requests';
		case 502:
			return 'Bad Gateway';
		case 503:
			return 'Service Unavailable';
		case 504:
			return 'Gateway Timeout';
		default:
			return status >= 500 ? 'Internal Server Error' : 'Bad Request';
	}
}
