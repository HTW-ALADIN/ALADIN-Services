import Fastify from 'fastify';
import fastifySwagger from '@fastify/swagger';
import fastifySwaggerUi from '@fastify/swagger-ui';
import mapRoutes from './routes/map.js';
import {
	MapperFunctionsSchema,
	MappingElementSchema,
	MappingTemplateSchema,
	MapRequestSchema,
	MapResponseSchema,
	ErrorResponseSchema,
} from './schemas/map.schema.js';

// Read version from package.json — tsx supports JSON imports
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const pkg = require('../../package.json') as {
	version: string;
	description: string;
};

/**
 * Creates and configures the Fastify server instance.
 *
 * Plugins registered:
 *  - @fastify/swagger   → generates OpenAPI 3.0 spec at GET /openapi.json
 *  - @fastify/swagger-ui → serves Swagger UI at GET /docs
 *  - mapRoutes          → POST /map and POST /map/async
 */
export async function buildServer() {
	const fastify = Fastify({
		logger: true,
	});

	// ---------------------------------------------------------------------------
	// Register OpenAPI spec generation (@fastify/swagger)
	// ---------------------------------------------------------------------------
	await fastify.register(fastifySwagger, {
		openapi: {
			openapi: '3.0.3',
			info: {
				title: 'jsonpath-mapper API',
				description:
					pkg.description +
					'\n\n' +
					'This REST API wraps the `jsonpath-mapper` library, exposing its ' +
					'JSON-to-JSON transformation capabilities over HTTP.\n\n' +
					'**Limitations:** Template values that require JavaScript functions ' +
					'(`$formatting`, `$return`, `$disable`) cannot be expressed in a ' +
					'JSON request body. Use the npm library directly for those cases.',
				version: pkg.version,
				contact: {
					url: 'https://github.com/neilflatley/jsonpath-mapper',
				},
				license: {
					name: 'ISC',
				},
			},
			tags: [
				{
					name: 'Mapping',
					description:
						'Endpoints for JSON-to-JSON transformation using declarative mapping templates.',
				},
			],
			components: {
				schemas: {
					// Register shared schemas so they appear in the OpenAPI components
					// section and can be referenced via $ref throughout the spec.
					MapperFunctions: MapperFunctionsSchema,
					MappingElement: MappingElementSchema,
					MappingTemplate: MappingTemplateSchema,
					MapRequest: MapRequestSchema,
					MapResponse: MapResponseSchema,
					ErrorResponse: ErrorResponseSchema,
				},
			},
		},
	});

	// ---------------------------------------------------------------------------
	// Register Swagger UI (@fastify/swagger-ui)
	// ---------------------------------------------------------------------------
	await fastify.register(fastifySwaggerUi, {
		routePrefix: '/docs',
		uiConfig: {
			docExpansion: 'full',
			deepLinking: true,
		},
	});

	// ---------------------------------------------------------------------------
	// Register route handlers
	// ---------------------------------------------------------------------------
	await fastify.register(mapRoutes);

	return fastify;
}
