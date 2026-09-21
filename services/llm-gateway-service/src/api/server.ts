import Fastify from 'fastify';
import fastifySwagger from '@fastify/swagger';
import fastifySwaggerUi from '@fastify/swagger-ui';
import healthRoutes from './routes/health.js';
import generateRoutes, {
	type GenerateRoutesOptions,
} from './routes/generate.js';
import providerRoutes, {
	type ProviderRoutesOptions,
} from './routes/providers.js';
import {
	EmbedRequestSchema,
	EmbedResponseSchema,
	GenerateRequestSchema,
	GenerateResponseSchema,
	OpenAIChatMessageSchema,
	OpenAIChatRequestSchema,
	OpenAIChatResponseSchema,
	OpenAIChatToolSchema,
	OpenAIResponseInputSchema,
	OpenAIResponseToolSchema,
	OpenAIResponsesRequestSchema,
	OpenAIResponsesResponseSchema,
	TokenUsageSchema,
	ToolCallSchema,
	UIMessagePartSchema,
	UIMessageSchema,
	VercelGenerateRequestSchema,
	VercelGenerateResponseSchema,
	VercelToolDefinitionSchema,
} from './schemas/generate.schema.js';
import {
	RegisterProviderRequestSchema,
	RegisterProviderResponseSchema,
} from './schemas/provider.schema.js';
import {
	CustomProviderOverrideSchema,
	ErrorResponseSchema,
} from './schemas/common.schema.js';
import { config } from '../config.js';

// Read version from package.json — tsx supports JSON imports
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const pkg = require('../../package.json') as {
	version: string;
	description: string;
};

export interface BuildServerOptions {
	generate?: GenerateRoutesOptions;
	providers?: ProviderRoutesOptions;
}

/**
 * Creates and configures the Fastify server instance.
 *
 * Plugins registered:
 *  - @fastify/swagger    → generates OpenAPI 3.0 spec at GET /docs/json
 *  - @fastify/swagger-ui → serves Swagger UI at GET /docs
 *  - healthRoutes        → GET /health
 *  - generateRoutes      → POST /generate, POST /embeddings
 *  - providerRoutes      → POST /providers
 */
export async function buildServer(options: BuildServerOptions = {}) {
	const fastify = Fastify({ logger: true });

	await fastify.register(fastifySwagger, {
		openapi: {
			openapi: '3.0.3',
			info: {
				title: 'LLM Gateway Service',
				description:
					pkg.description +
					'\n\n' +
					'This service wraps a self-hosted [LLM Gateway](https://docs.llmgateway.io/) ' +
					'instance using the Vercel AI SDK, exposing non-streaming text generation, ' +
					'embeddings, and best-effort custom provider registration.',
				version: pkg.version,
				license: { name: 'MIT' },
			},
			tags: [
				{
					name: 'Generation',
					description: 'Text generation and embeddings via LLM Gateway.',
				},
				{ name: 'Providers', description: 'Custom provider registration.' },
				{ name: 'Health', description: 'Liveness probe.' },
			],
			components: {
				schemas: {
					UIMessagePart: UIMessagePartSchema,
					UIMessage: UIMessageSchema,
					VercelToolDefinition: VercelToolDefinitionSchema,
					VercelGenerateRequest: VercelGenerateRequestSchema,
					VercelGenerateResponse: VercelGenerateResponseSchema,
					OpenAIChatMessage: OpenAIChatMessageSchema,
					OpenAIChatTool: OpenAIChatToolSchema,
					OpenAIChatRequest: OpenAIChatRequestSchema,
					OpenAIChatResponse: OpenAIChatResponseSchema,
					OpenAIResponseInput: OpenAIResponseInputSchema,
					OpenAIResponseTool: OpenAIResponseToolSchema,
					OpenAIResponsesRequest: OpenAIResponsesRequestSchema,
					OpenAIResponsesResponse: OpenAIResponsesResponseSchema,
					ToolCall: ToolCallSchema,
					TokenUsage: TokenUsageSchema,
					CustomProviderOverride: CustomProviderOverrideSchema,
					GenerateRequest: GenerateRequestSchema,
					GenerateResponse: GenerateResponseSchema,
					EmbedRequest: EmbedRequestSchema,
					EmbedResponse: EmbedResponseSchema,
					RegisterProviderRequest: RegisterProviderRequestSchema,
					RegisterProviderResponse: RegisterProviderResponseSchema,
					ErrorResponse: ErrorResponseSchema,
				},
			},
		},
	});

	await fastify.register(fastifySwaggerUi, {
		routePrefix: '/docs',
		uiConfig: { docExpansion: 'full', deepLinking: true },
	});

	// Optional bearer-token protection for the inference API. Enforced only when
	// LLM_GATEWAY_HTTP_TOKEN is configured, so existing deployments without auth
	// keep working unchanged; /health (liveness for orchestrators) and /docs are
	// exempt. Without this token, any client that can reach the port can spend
	// the configured LLM_GATEWAY_API_KEY and trigger server-side fetches to
	// customProvider URLs.
	if (config.httpToken) {
		fastify.addHook('onRequest', async (request, reply) => {
			const url = request.url.split('?')[0];
			if (url === '/health' || url.startsWith('/docs')) {
				return;
			}
			const header = request.headers.authorization ?? '';
			if (
				!header.startsWith('Bearer ') ||
				header.slice('Bearer '.length).trim() !== config.httpToken
			) {
				return reply
					.code(401)
					.send({ message: 'unauthorized', detail: 'Missing or invalid bearer token.' });
			}
		});
	}

	await fastify.register(healthRoutes);
	await fastify.register(generateRoutes(options.generate));
	await fastify.register(providerRoutes(options.providers));

	return fastify;
}
