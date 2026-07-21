import type { FastifyPluginAsync } from 'fastify';
import '@fastify/swagger';
import { GatewayClient } from '../../core/gateway-client.js';
import { vercelFormatAdapter } from '../../core/format/vercel.js';
import { replyWithError } from '../reply-error.js';
import {
	EmbedRequestSchema,
	EmbedResponseSchema,
	GenerateRequestSchema,
	GenerateResponseSchema,
	type EmbedRequestType,
	type GenerateRequestType,
} from '../schemas/generate.schema.js';
import { ErrorResponseSchema } from '../schemas/common.schema.js';
import { config } from '../../config.js';

export interface GenerateRoutesOptions {
	client?: GatewayClient;
}

const generateRoutes = (
	options: GenerateRoutesOptions = {}
): FastifyPluginAsync => {
	const client = options.client ?? new GatewayClient(config.gateway);

	return async (fastify) => {
		fastify.post<{ Body: GenerateRequestType }>(
			'/generate',
			{
				schema: {
					tags: ['Generation'],
					summary: 'Generate text (non-streaming) via LLM Gateway',
					description:
						'Accepts a Vercel AI SDK-style chat request and returns the full generated ' +
						'response, including usage, cost, and finish reason. Supports an inline ' +
						'`customProvider` override to call an OpenAI-compatible endpoint directly, ' +
						'bypassing the gateway, without requiring prior provider registration.',
					body: GenerateRequestSchema,
					response: {
						200: GenerateResponseSchema,
						400: ErrorResponseSchema,
						401: ErrorResponseSchema,
						403: ErrorResponseSchema,
						429: ErrorResponseSchema,
						502: ErrorResponseSchema,
					},
				},
			},
			async (request, reply) => {
				try {
					const generateRequest = vercelFormatAdapter.parseRequest(
						request.body
					);
					const result = await client.generate(generateRequest);
					return reply
						.status(200)
						.send(vercelFormatAdapter.formatResponse(result));
				} catch (err) {
					return replyWithError(reply, err);
				}
			}
		);

		fastify.post<{ Body: EmbedRequestType }>(
			'/embeddings',
			{
				schema: {
					tags: ['Generation'],
					summary: 'Create embeddings via LLM Gateway',
					body: EmbedRequestSchema,
					response: {
						200: EmbedResponseSchema,
						400: ErrorResponseSchema,
						401: ErrorResponseSchema,
						403: ErrorResponseSchema,
						429: ErrorResponseSchema,
						502: ErrorResponseSchema,
					},
				},
			},
			async (request, reply) => {
				try {
					const result = await client.embedText(request.body);
					return reply.status(200).send(result);
				} catch (err) {
					return replyWithError(reply, err);
				}
			}
		);
	};
};

export default generateRoutes;
