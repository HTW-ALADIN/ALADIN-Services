import type { FastifyPluginAsync } from 'fastify';
import '@fastify/swagger';
import { ProviderRegistry } from '../../core/provider-registry.js';
import { replyWithError } from '../reply-error.js';
import {
	RegisterProviderRequestSchema,
	RegisterProviderResponseSchema,
	type RegisterProviderRequestType,
} from '../schemas/provider.schema.js';
import { ErrorResponseSchema } from '../schemas/common.schema.js';
import { config } from '../../config.js';

export interface ProviderRoutesOptions {
	registry?: ProviderRegistry;
}

const providerRoutes = (
	options: ProviderRoutesOptions = {}
): FastifyPluginAsync => {
	const registry = options.registry ?? new ProviderRegistry(config.admin);

	return async (fastify) => {
		fastify.post<{ Body: RegisterProviderRequestType }>(
			'/providers',
			{
				schema: {
					tags: ['Providers'],
					summary:
						'Best-effort registration of a custom provider with LLM Gateway',
					description:
						"Attempts to register a custom OpenAI-compatible provider with the gateway's " +
						'admin API, when LLM_GATEWAY_ADMIN_BASE_URL/LLM_GATEWAY_ADMIN_TOKEN are ' +
						'configured. This is optional: prefer the `customProvider` override on ' +
						'`POST /generate` for one-shot workflow calls that do not require prior ' +
						'gateway-side registration.',
					body: RegisterProviderRequestSchema,
					response: {
						200: RegisterProviderResponseSchema,
						400: ErrorResponseSchema,
						502: ErrorResponseSchema,
					},
				},
			},
			async (request, reply) => {
				try {
					const result = await registry.register(request.body);
					return reply.status(200).send(result);
				} catch (err) {
					return replyWithError(reply, err);
				}
			}
		);
	};
};

export default providerRoutes;
