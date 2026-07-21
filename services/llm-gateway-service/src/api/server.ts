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
	ContentPartSchema,
	EmbedRequestSchema,
	EmbedResponseSchema,
	GenerateRequestSchema,
	GenerateResponseSchema,
	MessageSchema,
	TokenUsageSchema,
	ToolCallSchema,
	ToolDefinitionSchema,
} from './schemas/generate.schema.js';
import {
	RegisterProviderRequestSchema,
	RegisterProviderResponseSchema,
} from './schemas/provider.schema.js';
import {
	CustomProviderOverrideSchema,
	ErrorResponseSchema,
} from './schemas/common.schema.js';

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
					ContentPart: ContentPartSchema,
					Message: MessageSchema,
					ToolDefinition: ToolDefinitionSchema,
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

	await fastify.register(healthRoutes);
	await fastify.register(generateRoutes(options.generate));
	await fastify.register(providerRoutes(options.providers));

	return fastify;
}
