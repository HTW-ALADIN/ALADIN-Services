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

/**
 * Field definitions for `CustomProviderOverride`, exposed as a factory so
 * callers that need to embed this shape multiple times *within a single
 * compiled schema* (e.g. a `Type.Union` of several request variants) can
 * get a fresh, `$id`-free copy each time. AJV rejects a schema document
 * that contains the same `$id` more than once, which is exactly what
 * happens if `CustomProviderOverrideSchema` below is reused as-is inside
 * more than one branch of the same union.
 */
export const customProviderOverrideFields = () => ({
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
});

export const CustomProviderOverrideSchema = Type.Object(
	customProviderOverrideFields(),
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
