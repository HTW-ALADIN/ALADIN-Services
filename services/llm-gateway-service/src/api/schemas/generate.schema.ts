import { Type, Static } from '@sinclair/typebox';
import { CustomProviderOverrideSchema } from './common.schema.js';

export const ContentPartSchema = Type.Object(
	{
		type: Type.Union([Type.Literal('text'), Type.Literal('image')]),
		text: Type.Optional(Type.String()),
		image: Type.Optional(
			Type.String({ description: 'Data URL, http(s) URL, or base64 string.' })
		),
		mediaType: Type.Optional(Type.String()),
	},
	{ $id: 'ContentPart', title: 'ContentPart' }
);

export const MessageSchema = Type.Object(
	{
		role: Type.Union([
			Type.Literal('system'),
			Type.Literal('user'),
			Type.Literal('assistant'),
			Type.Literal('tool'),
		]),
		content: Type.Union([Type.String(), Type.Array(ContentPartSchema)]),
		toolCallId: Type.Optional(Type.String()),
		toolName: Type.Optional(Type.String()),
	},
	{
		$id: 'Message',
		title: 'Message',
		description: 'A Vercel AI SDK-style chat message.',
	}
);

export const ToolDefinitionSchema = Type.Object(
	{
		description: Type.Optional(Type.String()),
		inputSchema: Type.Record(Type.String(), Type.Unknown(), {
			description: "JSON Schema describing the tool's parameters.",
		}),
	},
	{ $id: 'ToolDefinition', title: 'ToolDefinition' }
);

export const GenerateRequestSchema = Type.Object(
	{
		provider: Type.String({
			description:
				'Provider id, e.g. "openai", "anthropic", or a custom provider name registered with the gateway.',
			examples: ['openai'],
		}),
		model: Type.String({
			description: 'Model id within the provider.',
			examples: ['gpt-4o'],
		}),
		messages: Type.Array(MessageSchema, { minItems: 1 }),
		system: Type.Optional(
			Type.String({ description: 'System / developer instructions.' })
		),
		tools: Type.Optional(Type.Record(Type.String(), ToolDefinitionSchema)),
		temperature: Type.Optional(Type.Number({ minimum: 0, maximum: 2 })),
		maxOutputTokens: Type.Optional(Type.Integer({ minimum: 1 })),
		topP: Type.Optional(Type.Number({ minimum: 0, maximum: 1 })),
		stopSequences: Type.Optional(Type.Array(Type.String())),
		metadata: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
		customProvider: Type.Optional(CustomProviderOverrideSchema),
	},
	{
		$id: 'GenerateRequest',
		title: 'GenerateRequest',
		description:
			'Non-streaming text generation request, in Vercel AI SDK message format.',
		additionalProperties: false,
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

export const GenerateResponseSchema = Type.Object(
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
	{ $id: 'GenerateResponse', title: 'GenerateResponse' }
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
