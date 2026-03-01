import type { FastifyPluginAsync } from 'fastify';
// Import @fastify/swagger types to apply the FastifySchema augmentation
// (adds tags, summary, description, operationId, etc.)
import '@fastify/swagger';
import mapJson from '../../json-mapper.js';
import mapJsonAsync from '../../json-mapper-async.js';
import type { MappingTemplate } from '../../models/Template.js';
import {
	MapRequestSchema,
	MapResponseSchema,
	ErrorResponseSchema,
	type MapRequestType,
} from '../schemas/map.schema.js';

/**
 * Fastify plugin that registers the /map and /map/async route handlers.
 *
 * Both endpoints accept the same request body:
 *   { data: unknown, template: MappingTemplate (serializable subset) }
 *
 * The only difference is that /map/async uses the Promise-based code path
 * internally (useful when the consumer wants consistent async behaviour).
 */
const mapRoutes: FastifyPluginAsync = async (fastify) => {
	// -------------------------------------------------------------------------
	// POST /map  — synchronous mapping
	// -------------------------------------------------------------------------
	fastify.post<{ Body: MapRequestType }>(
		'/map',
		{
			schema: {
				tags: ['Mapping'],
				summary: 'Transform a JSON object synchronously',
				description:
					'Applies a declarative mapping template to the supplied input data ' +
					'and returns the transformed result. The template is evaluated ' +
					'synchronously using `mapJson`.\n\n' +
					'**Template values** can be:\n' +
					'- A JSONPath string (e.g. `"$.store.book[0].title"`)\n' +
					'- An array of JSONPath strings — first non-null match is used\n' +
					'- A `MapperFunctions` object with `$path` and optional `$default`\n' +
					'- A nested object whose values are any of the above\n\n' +
					'> **Note:** Template values that require JavaScript functions ' +
					'(`$formatting`, `$return`, `$disable`) cannot be expressed in a ' +
					'JSON request body. Use the npm library directly for those cases.',
				body: MapRequestSchema,
				response: {
					200: MapResponseSchema,
					400: ErrorResponseSchema,
					500: ErrorResponseSchema,
				},
			},
		},
		async (request, reply) => {
			const { data, template } = request.body;
			try {
				const result = mapJson(data, template as MappingTemplate<unknown>);
				return reply.status(200).send({ result });
			} catch (err) {
				const message = err instanceof Error ? err.message : String(err);
				return reply.status(500).send({
					statusCode: 500,
					error: 'Internal Server Error',
					message: `Mapping failed: ${message}`,
				});
			}
		}
	);

	// -------------------------------------------------------------------------
	// POST /map/async  — asynchronous mapping
	// -------------------------------------------------------------------------
	fastify.post<{ Body: MapRequestType }>(
		'/map/async',
		{
			schema: {
				tags: ['Mapping'],
				summary: 'Transform a JSON object asynchronously',
				description:
					'Applies a declarative mapping template to the supplied input data ' +
					'and returns the transformed result. The template is evaluated ' +
					'asynchronously using `mapJsonAsync`, which resolves sibling keys ' +
					'in parallel via `Promise.all`.\n\n' +
					'The request/response shape is identical to `POST /map`. ' +
					'For purely JSONPath-based templates the result will be the same; ' +
					'this endpoint exists to exercise the async code path.\n\n' +
					'**Template values** can be:\n' +
					'- A JSONPath string (e.g. `"$.store.book[0].title"`)\n' +
					'- An array of JSONPath strings — first non-null match is used\n' +
					'- A `MapperFunctions` object with `$path` and optional `$default`\n' +
					'- A nested object whose values are any of the above\n\n' +
					'> **Note:** Template values that require JavaScript functions ' +
					'(`$formatting`, `$return`, `$disable`) cannot be expressed in a ' +
					'JSON request body. Use the npm library directly for those cases.',
				body: MapRequestSchema,
				response: {
					200: MapResponseSchema,
					400: ErrorResponseSchema,
					500: ErrorResponseSchema,
				},
			},
		},
		async (request, reply) => {
			const { data, template } = request.body;
			try {
				const result = await mapJsonAsync(
					data,
					template as MappingTemplate<unknown>
				);
				return reply.status(200).send({ result });
			} catch (err) {
				const message = err instanceof Error ? err.message : String(err);
				return reply.status(500).send({
					statusCode: 500,
					error: 'Internal Server Error',
					message: `Mapping failed: ${message}`,
				});
			}
		}
	);
};

export default mapRoutes;
