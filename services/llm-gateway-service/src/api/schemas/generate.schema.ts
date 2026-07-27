import { Type, Static } from '@sinclair/typebox';
import {
	CustomProviderOverrideSchema,
	customProviderOverrideFields,
} from './common.schema.js';

// --- Vercel AI SDK format (default when `format` is omitted) ---------

export const UIMessagePartSchema = Type.Record(Type.String(), Type.Unknown(), {
	description:
		'A single element of a UIMessage.parts array (text, file, reasoning, ' +
		'tool-*, dynamic-tool, source-url, source-document, data-*, or ' +
		'step-start), as defined by the Vercel AI SDK `UIMessagePart` union.',
});

export const UIMessageSchema = Type.Object(
	{
		id: Type.String(),
		role: Type.Union([
			Type.Literal('system'),
			Type.Literal('user'),
			Type.Literal('assistant'),
		]),
		metadata: Type.Optional(Type.Unknown()),
		parts: Type.Array(UIMessagePartSchema),
	},
	{
		$id: 'UIMessage',
		title: 'UIMessage',
		description: 'A Vercel AI SDK `UIMessage` (see the `ai` package).',
	}
);

export const VercelToolDefinitionSchema = Type.Object(
	{
		description: Type.Optional(Type.String()),
		inputSchema: Type.Record(Type.String(), Type.Unknown(), {
			description: "JSON Schema describing the tool's parameters.",
		}),
	},
	{ $id: 'VercelToolDefinition', title: 'VercelToolDefinition' }
);

export const VercelGenerateRequestSchema = Type.Object(
	{
		format: Type.Optional(Type.Literal('vercel')),
		provider: Type.String({
			description:
				'Provider id, e.g. "openai", "anthropic", or a custom provider name registered with the gateway.',
			examples: ['openai'],
		}),
		model: Type.String({
			description: 'Model id within the provider.',
			examples: ['gpt-4o'],
		}),
		messages: Type.Array(UIMessageSchema, { minItems: 1 }),
		system: Type.Optional(
			Type.String({ description: 'System / developer instructions.' })
		),
		tools: Type.Optional(
			Type.Record(Type.String(), VercelToolDefinitionSchema)
		),
		temperature: Type.Optional(Type.Number({ minimum: 0, maximum: 2 })),
		maxOutputTokens: Type.Optional(Type.Integer({ minimum: 1 })),
		topP: Type.Optional(Type.Number({ minimum: 0, maximum: 1 })),
		stopSequences: Type.Optional(Type.Array(Type.String())),
		metadata: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
		customProvider: Type.Optional(Type.Object(customProviderOverrideFields(), { title: 'CustomProviderOverride' })),
	},
	{
		$id: 'VercelGenerateRequest',
		title: 'VercelGenerateRequest',
		description:
			'Non-streaming text generation request using the Vercel AI SDK ' +
			'`UIMessage` format (this is the default when "format" is omitted).',
	}
);

// --- OpenAI Chat Completions format -----------------------------------

export const OpenAIChatContentPartSchema = Type.Object(
	{
		type: Type.Union([Type.Literal('text'), Type.Literal('image_url')]),
		text: Type.Optional(Type.String()),
		image_url: Type.Optional(Type.Object({ url: Type.String() })),
	},
	{ $id: 'OpenAIChatContentPart', title: 'OpenAIChatContentPart' }
);

export const OpenAIChatToolCallSchema = Type.Object(
	{
		id: Type.String(),
		type: Type.Literal('function'),
		function: Type.Object({
			name: Type.String(),
			arguments: Type.String(),
		}),
	},
	{ $id: 'OpenAIChatToolCall', title: 'OpenAIChatToolCall' }
);

export const OpenAIChatMessageSchema = Type.Object(
	{
		role: Type.Union([
			Type.Literal('system'),
			Type.Literal('user'),
			Type.Literal('assistant'),
			Type.Literal('tool'),
		]),
		content: Type.Union([
			Type.String(),
			Type.Array(OpenAIChatContentPartSchema),
			Type.Null(),
		]),
		tool_call_id: Type.Optional(Type.String()),
		tool_calls: Type.Optional(Type.Array(OpenAIChatToolCallSchema)),
	},
	{
		$id: 'OpenAIChatMessage',
		title: 'OpenAIChatMessage',
		description: 'An OpenAI Chat Completions-style message.',
	}
);

export const OpenAIChatToolSchema = Type.Object(
	{
		type: Type.Literal('function'),
		function: Type.Object({
			name: Type.String(),
			description: Type.Optional(Type.String()),
			parameters: Type.Record(Type.String(), Type.Unknown()),
		}),
	},
	{ $id: 'OpenAIChatTool', title: 'OpenAIChatTool' }
);

export const OpenAIChatRequestSchema = Type.Object(
	{
		format: Type.Literal('openai-chat'),
		provider: Type.String({
			description:
				'Provider id, e.g. "openai", "anthropic", or a custom provider name registered with the gateway.',
			examples: ['openai'],
		}),
		model: Type.String({ examples: ['gpt-4o'] }),
		messages: Type.Array(OpenAIChatMessageSchema, { minItems: 1 }),
		tools: Type.Optional(Type.Array(OpenAIChatToolSchema)),
		temperature: Type.Optional(Type.Number({ minimum: 0, maximum: 2 })),
		max_tokens: Type.Optional(Type.Integer({ minimum: 1 })),
		top_p: Type.Optional(Type.Number({ minimum: 0, maximum: 1 })),
		stop: Type.Optional(
			Type.Union([Type.String(), Type.Array(Type.String())])
		),
		metadata: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
		customProvider: Type.Optional(Type.Object(customProviderOverrideFields(), { title: 'CustomProviderOverride' })),
	},
	{
		$id: 'OpenAIChatRequest',
		title: 'OpenAIChatRequest',
		description:
			'Non-streaming text generation request using the OpenAI Chat ' +
			'Completions (`/v1/chat/completions`) wire format.',
	}
);

// --- OpenAI Responses format -------------------------------------------

export const OpenAIResponseContentSchema = Type.Object(
	{
		type: Type.Union([
			Type.Literal('input_text'),
			Type.Literal('output_text'),
			Type.Literal('input_image'),
		]),
		text: Type.Optional(Type.String()),
		image_url: Type.Optional(Type.String()),
	},
	{ $id: 'OpenAIResponseContent', title: 'OpenAIResponseContent' }
);

export const OpenAIResponseInputSchema = Type.Union([
	Type.Object({
		role: Type.Union([
			Type.Literal('system'),
			Type.Literal('user'),
			Type.Literal('assistant'),
		]),
		content: Type.Union([
			Type.String(),
			Type.Array(OpenAIResponseContentSchema),
		]),
	}),
	Type.Object({
		type: Type.Literal('function_call_output'),
		call_id: Type.String(),
		output: Type.String(),
	}),
]);

export const OpenAIResponseToolSchema = Type.Object(
	{
		type: Type.Literal('function'),
		name: Type.String(),
		description: Type.Optional(Type.String()),
		parameters: Type.Record(Type.String(), Type.Unknown()),
	},
	{ $id: 'OpenAIResponseTool', title: 'OpenAIResponseTool' }
);

export const OpenAIResponsesRequestSchema = Type.Object(
	{
		format: Type.Literal('openai-responses'),
		provider: Type.String({
			description:
				'Provider id, e.g. "openai", "anthropic", or a custom provider name registered with the gateway.',
			examples: ['openai'],
		}),
		model: Type.String({ examples: ['gpt-4o'] }),
		input: Type.Union([
			Type.String(),
			Type.Array(OpenAIResponseInputSchema, { minItems: 1 }),
		]),
		instructions: Type.Optional(Type.String()),
		tools: Type.Optional(Type.Array(OpenAIResponseToolSchema)),
		temperature: Type.Optional(Type.Number({ minimum: 0, maximum: 2 })),
		max_output_tokens: Type.Optional(Type.Integer({ minimum: 1 })),
		top_p: Type.Optional(Type.Number({ minimum: 0, maximum: 1 })),
		metadata: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
		customProvider: Type.Optional(Type.Object(customProviderOverrideFields(), { title: 'CustomProviderOverride' })),
	},
	{
		$id: 'OpenAIResponsesRequest',
		title: 'OpenAIResponsesRequest',
		description:
			'Non-streaming text generation request using the OpenAI Responses ' +
			'(`/v1/responses`) wire format.',
	}
);

// --- Combined request (selected via the `format` field) ---------------

export const GenerateRequestSchema = Type.Union(
	[
		VercelGenerateRequestSchema,
		OpenAIChatRequestSchema,
		OpenAIResponsesRequestSchema,
	],
	{
		$id: 'GenerateRequest',
		title: 'GenerateRequest',
		description:
			'Non-streaming text generation request. Defaults to the Vercel AI ' +
			'SDK `UIMessage` format when "format" is omitted; set "format" to ' +
			'"openai-chat" or "openai-responses" to use an OpenAI wire format ' +
			'instead.',
	}
);

export type GenerateRequestType = Static<typeof GenerateRequestSchema>;

export const ToolCallSchema = Type.Object(
	{
		toolCallId: Type.String(),
		toolName: Type.String(),
		input: Type.Unknown(),
	},
	{ $id: 'ToolCall', title: 'ToolCall' }
);

export const TokenUsageSchema = Type.Object(
	{
		inputTokens: Type.Optional(Type.Number()),
		outputTokens: Type.Optional(Type.Number()),
		totalTokens: Type.Optional(Type.Number()),
	},
	{ $id: 'TokenUsage', title: 'TokenUsage' }
);

export const VercelGenerateResponseSchema = Type.Object(
	{
		text: Type.String(),
		finishReason: Type.String(),
		usage: TokenUsageSchema,
		cost: Type.Optional(
			Type.Number({
				description: 'USD cost reported by LLM Gateway, when available.',
			})
		),
		provider: Type.String(),
		model: Type.String(),
		toolCalls: Type.Optional(Type.Array(ToolCallSchema)),
		raw: Type.Optional(
			Type.Unknown({
				description: 'Raw gateway/provider response, for debugging.',
			})
		),
		viaGatewayBypass: Type.Optional(
			Type.Boolean({
				description:
					'True when this request bypassed the gateway via `customProvider`.',
			})
		),
	},
	{ $id: 'VercelGenerateResponse', title: 'VercelGenerateResponse' }
);

export const OpenAIChatResponseSchema = Type.Object(
	{
		id: Type.String(),
		object: Type.Literal('chat.completion'),
		created: Type.Number(),
		model: Type.String(),
		provider: Type.String(),
		choices: Type.Array(
			Type.Object({
				index: Type.Number(),
				message: Type.Object({
					role: Type.Literal('assistant'),
					content: Type.Union([Type.String(), Type.Null()]),
					tool_calls: Type.Optional(Type.Array(OpenAIChatToolCallSchema)),
				}),
				finish_reason: Type.String(),
			})
		),
		usage: Type.Object({
			prompt_tokens: Type.Optional(Type.Number()),
			completion_tokens: Type.Optional(Type.Number()),
			total_tokens: Type.Optional(Type.Number()),
		}),
		cost: Type.Optional(Type.Number()),
		raw: Type.Optional(Type.Unknown()),
		viaGatewayBypass: Type.Optional(Type.Boolean()),
	},
	{ $id: 'OpenAIChatResponse', title: 'OpenAIChatResponse' }
);

export const OpenAIResponsesResponseSchema = Type.Object(
	{
		id: Type.String(),
		object: Type.Literal('response'),
		created_at: Type.Number(),
		model: Type.String(),
		provider: Type.String(),
		status: Type.String(),
		output: Type.Array(Type.Unknown()),
		output_text: Type.String(),
		usage: Type.Object({
			input_tokens: Type.Optional(Type.Number()),
			output_tokens: Type.Optional(Type.Number()),
			total_tokens: Type.Optional(Type.Number()),
		}),
		cost: Type.Optional(Type.Number()),
		raw: Type.Optional(Type.Unknown()),
		viaGatewayBypass: Type.Optional(Type.Boolean()),
	},
	{ $id: 'OpenAIResponsesResponse', title: 'OpenAIResponsesResponse' }
);

export const GenerateResponseSchema = Type.Union(
	[
		VercelGenerateResponseSchema,
		OpenAIChatResponseSchema,
		OpenAIResponsesResponseSchema,
	],
	{
		$id: 'GenerateResponse',
		title: 'GenerateResponse',
		description:
			'Response shape matches the request\'s "format" (Vercel, OpenAI ' +
			'Chat Completions, or OpenAI Responses).',
	}
);

export const EmbedRequestSchema = Type.Object(
	{
		provider: Type.String(),
		model: Type.String(),
		input: Type.Union([Type.String(), Type.Array(Type.String())]),
		customProvider: Type.Optional(CustomProviderOverrideSchema),
	},
	{ $id: 'EmbedRequest', title: 'EmbedRequest', additionalProperties: false }
);

export type EmbedRequestType = Static<typeof EmbedRequestSchema>;

export const EmbedResponseSchema = Type.Object(
	{
		embeddings: Type.Array(Type.Array(Type.Number())),
		usage: TokenUsageSchema,
		provider: Type.String(),
		model: Type.String(),
		raw: Type.Optional(Type.Unknown()),
	},
	{ $id: 'EmbedResponse', title: 'EmbedResponse' }
);
