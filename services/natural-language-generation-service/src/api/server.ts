import Fastify, { type FastifyError } from 'fastify';
import fastifySwagger from '@fastify/swagger';
import fastifySwaggerUi from '@fastify/swagger-ui';
import type { ServiceLimits } from '../config.js';
import { DEFAULT_LIMITS } from '../config.js';
import { ServiceError, toProblem } from '../errors.js';
import { capabilities, inspectRequestStructure, realize } from '../realizer.js';
import {
	CapabilitiesSchema,
	ConstituentNodeSchema,
	DependentNodeSchema,
	GenerateRequestSchema,
	GenerateResponseSchema,
	HealthSchema,
	JsonValueSchema,
	ProblemSchema,
	SurfaceRealizationRequestSchema,
	SurfaceRealizationResponseSchema,
	TemplateGenerationRequestSchema,
	TemplateGenerationResponseSchema,
	type GenerateRequest,
} from '../schemas.js';

export interface BuildServerOptions {
	limits?: ServiceLimits;
	logger?: boolean;
}

export async function buildServer(options: BuildServerOptions = {}) {
	const limits = options.limits ?? DEFAULT_LIMITS;
	const server = Fastify({
		logger: options.logger ?? false,
		bodyLimit: limits.maxBodyBytes,
	});

	await server.register(fastifySwagger, {
		refResolver: {
			buildLocalReference: (schema) => schema.$id as string,
		},
		openapi: {
			openapi: '3.1.0',
			info: {
				title: 'Natural Language Generation Service',
				version: '0.1.0',
				description:
					'Deterministic rule-based NLG with jsRealB surface realisation and trusted RosaeNLG template generation.',
				license: { name: 'MIT' },
			},
			tags: [
				{
					name: 'Generation',
					description:
						'Deterministic surface realisation and trusted template generation.',
				},
				{ name: 'Discovery', description: 'Engine capabilities and limits.' },
				{ name: 'Operations', description: 'Operational probes.' },
			],
		},
		transformObject: (documentObject) => {
			const { openapiObject } = documentObject as Extract<
				typeof documentObject,
				{ openapiObject: unknown }
			>;
			const generateOperation = openapiObject.paths?.['/v1/generate']?.post;
			const requestBody = generateOperation?.requestBody as {
				content: {
					'application/json': { schema: Record<string, unknown> };
				};
			};
			requestBody.content['application/json'].schema.discriminator = {
				propertyName: 'mode',
				mapping: {
					surface_realization: '#/components/schemas/SurfaceRealizationRequest',
					template_generation: '#/components/schemas/TemplateGenerationRequest',
				},
			};
			const response = generateOperation?.responses?.['200'];
			if (
				response !== undefined &&
				'content' in response &&
				response.content?.['application/json']?.schema !== undefined
			) {
				const documentedSchema = response.content['application/json'].schema;
				if (
					'oneOf' in documentedSchema &&
					Array.isArray(documentedSchema.oneOf) &&
					documentedSchema.oneOf.length === 2
				) {
					const jsonSchema = documentedSchema.oneOf[0] as Record<
						string,
						unknown
					>;
					jsonSchema.discriminator = { propertyName: 'mode' };
					response.content = {
						'application/json': { schema: jsonSchema },
						'text/plain': { schema: documentedSchema.oneOf[1] },
					};
				}
			}
			for (const status of ['400', '413', '422', '500']) {
				const problemResponse = generateOperation?.responses?.[status] as {
					content: Record<string, unknown>;
				};
				problemResponse.content = {
					'application/problem+json':
						problemResponse.content['application/json'],
				};
			}
			return openapiObject;
		},
	});
	await server.register(fastifySwaggerUi, { routePrefix: '/api-docs' });
	for (const schema of [
		ConstituentNodeSchema,
		DependentNodeSchema,
		JsonValueSchema,
		SurfaceRealizationRequestSchema,
		TemplateGenerationRequestSchema,
		SurfaceRealizationResponseSchema,
		TemplateGenerationResponseSchema,
	]) {
		server.addSchema(schema);
	}

	server.get(
		'/healthz',
		{
			schema: {
				tags: ['Operations'],
				operationId: 'getHealth',
				summary: 'Liveness probe',
				response: { 200: HealthSchema },
			},
		},
		async () => ({ status: 'ok' as const })
	);

	server.get(
		'/v1/capabilities',
		{
			schema: {
				tags: ['Discovery'],
				operationId: 'getCapabilities',
				summary: 'Describe available NLG modes, representations, and limits',
				response: { 200: CapabilitiesSchema },
			},
		},
		async () => capabilities(limits)
	);

	server.post<{ Body: GenerateRequest }>(
		'/v1/generate',
		{
			preValidation: async (request) => {
				inspectRequestStructure(request.body, limits);
			},
			schema: {
				tags: ['Generation'],
				operationId: 'generateText',
				summary: 'Generate text from a structure or trusted NLG template',
				body: GenerateRequestSchema,
				response: {
					200: {
						oneOf: [GenerateResponseSchema, { type: 'string' }],
					},
					400: ProblemSchema,
					413: ProblemSchema,
					422: ProblemSchema,
					500: ProblemSchema,
				},
			},
		},
		async (request, reply) => {
			const result = await realize(request.body, limits);
			if (request.headers.accept?.includes('text/plain')) {
				return reply.type('text/plain; charset=utf-8').send(result.text);
			}
			return reply.send(result);
		}
	);

	server.get(
		'/api-docs/openapi.json',
		{ schema: { hide: true } },
		async (_request, reply) => reply.send(server.swagger())
	);

	server.setErrorHandler((error: FastifyError, request, reply) => {
		let serviceError: ServiceError;
		if (error instanceof ServiceError) {
			serviceError = error;
		} else if (error.code === 'FST_ERR_CTP_BODY_TOO_LARGE') {
			serviceError = new ServiceError(
				'payload-too-large',
				413,
				'Payload too large',
				`request body exceeds ${limits.maxBodyBytes} bytes`
			);
		} else if (
			error.validation !== undefined ||
			error.code === 'FST_ERR_CTP_INVALID_JSON_BODY'
		) {
			serviceError = new ServiceError(
				'invalid-request',
				400,
				'Invalid request',
				error.message
			);
		} else {
			request.log.error(error);
			serviceError = new ServiceError(
				'internal-error',
				500,
				'Internal server error',
				'the request could not be processed'
			);
		}
		return reply
			.status(serviceError.status)
			.type('application/problem+json')
			.send(toProblem(serviceError, request.url));
	});

	return server;
}
