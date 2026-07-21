import { Type } from '@sinclair/typebox';

export const ErrorResponseSchema = Type.Object(
	{
		statusCode: Type.Number({ description: 'HTTP status code.' }),
		error: Type.String({ description: 'HTTP error name.' }),
		message: Type.String({ description: 'Human-readable error message.' }),
		code: Type.Optional(
			Type.String({ description: 'Upstream error code, when available.' })
		),
	},
	{
		$id: 'ErrorResponse',
		title: 'ErrorResponse',
		description:
			'Error response returned when a request is invalid or the LLM Gateway request fails.',
	}
);

export const CustomProviderOverrideSchema = Type.Object(
	{
		baseUrl: Type.String({
			minLength: 1,
			description:
				'OpenAI-compatible base URL (including any version path, e.g. ' +
				'"https://api.mycompany.com/v1") to call directly, bypassing LLM Gateway ' +
				'routing for this request. "/chat/completions" or "/embeddings" is appended ' +
				'automatically. Must not resolve to a loopback, link-local, or private address.',
		}),
		apiKey: Type.String({
			minLength: 1,
			description: 'API key/token for the custom provider endpoint.',
		}),
	},
	{
		$id: 'CustomProviderOverride',
		title: 'CustomProviderOverride',
		description:
			'Inline connection details for an OpenAI-compatible endpoint that has not been ' +
			'pre-registered with the gateway. When present, this single request is sent directly ' +
			'to the given endpoint instead of being routed through LLM Gateway, so a workflow can ' +
			'deploy, configure, and call a brand-new custom provider in one step.',
	}
);
