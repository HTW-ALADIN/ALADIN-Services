import { TypeCompiler } from '@sinclair/typebox/compiler';
import type { GenerateRequest } from './schemas.js';
import {
	ConstituentNodeSchema,
	DependentNodeSchema,
	GenerateRequestSchema,
	JsonValueSchema,
	SurfaceRealizationRequestSchema,
	TemplateGenerationRequestSchema,
} from './schemas.js';
import { ServiceError } from './errors.js';

const generateRequestValidator = TypeCompiler.Compile(GenerateRequestSchema, [
	ConstituentNodeSchema,
	DependentNodeSchema,
	JsonValueSchema,
	SurfaceRealizationRequestSchema,
	TemplateGenerationRequestSchema,
]);

export function validateGenerateRequest(value: unknown): GenerateRequest {
	if (generateRequestValidator.Check(value)) return value as GenerateRequest;

	const details = [...generateRequestValidator.Errors(value)]
		.slice(0, 5)
		.map((error) => `${error.path || '/'} ${error.message}`)
		.join('; ');
	throw new ServiceError('invalid-request', 400, 'Invalid request', details);
}
