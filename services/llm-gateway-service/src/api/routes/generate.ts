import type { FastifyPluginAsync } from 'fastify';
import '@fastify/swagger';
import { GatewayClient } from '../../core/gateway-client.js';
import { getFormatAdapter } from '../../core/format/index.js';
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
						'Accepts a chat request and returns the full generated response, ' +
						'including usage, cost, and finish reason. The wire format defaults to ' +
						'the Vercel AI SDK `UIMessage` format; set "format" to "openai-chat" or ' +
						'"openai-responses" to use an OpenAI-compatible wire format instead. ' +
						'Supports an inline `customProvider` override to call an ' +
						'OpenAI-compatible endpoint directly, bypassing the gateway, without ' +
						'requiring prior provider registration.',
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
					const format = (request.body as { format?: string }).format;
					const adapter = getFormatAdapter(format);
					const generateRequest = adapter.parseRequest(request.body);
					const result = await client.generate(generateRequest);
					return reply.status(200).send(adapter.formatResponse(result));
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
