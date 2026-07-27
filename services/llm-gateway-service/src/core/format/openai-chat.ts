/**
 * OpenAI Chat Completions format adapter.
 *
 * Translates between the wire format used by OpenAI's
 * `POST /v1/chat/completions` endpoint and this service's internal,
 * format-agnostic `GenerateRequest`/`GenerateResponse` types.
 *
 * The OpenAI Node SDK is not a dependency of this service (it only ever
 * talks to providers through the gateway/AI SDK), so the request/response
 * shapes below are hand-written to match OpenAI's public API reference
 * rather than imported from an official package.
 *
 * See `./index.ts` for the adapter registry and `./types.ts` for the
 * shared `FormatAdapter` interface.
 */
import type {
	ChatMessage,
	ChatRole,
	ContentPart,
	CustomProviderOverride,
	GenerateRequest,
	GenerateResponse,
	ToolDefinition,
} from '../types.js';
import type { FormatAdapter } from './types.js';
import { generateId, validateCustomProviderOverride } from './shared.js';

export interface OpenAIChatContentPart {
	type: 'text' | 'image_url';
	text?: string;
	image_url?: { url: string };
}

export interface OpenAIChatMessage {
	role: 'system' | 'user' | 'assistant' | 'tool';
	content: string | OpenAIChatContentPart[] | null;
	tool_call_id?: string;
	tool_calls?: OpenAIChatToolCall[];
}

export interface OpenAIChatToolCall {
	id: string;
	type: 'function';
	function: {
		name: string;
		arguments: string;
	};
}

export interface OpenAIChatTool {
	type: 'function';
	function: {
		name: string;
		description?: string;
		parameters: Record<string, unknown>;
	};
}

export interface OpenAIChatRequest {
	/** Selects this adapter; required to disambiguate from the default 'vercel' format. */
	format: 'openai-chat';
	/** Provider id (e.g. "openai", "anthropic") this gateway should route to. */
	provider: string;
	model: string;
	messages: OpenAIChatMessage[];
	tools?: OpenAIChatTool[];
	temperature?: number;
	max_tokens?: number;
	top_p?: number;
	stop?: string | string[];
	metadata?: Record<string, unknown>;
	customProvider?: CustomProviderOverride;
}

export interface OpenAIChatChoice {
	index: 0;
	message: {
		role: 'assistant';
		content: string | null;
		tool_calls?: OpenAIChatToolCall[];
	};
	finish_reason: string;
}

export interface OpenAIChatResponse {
	id: string;
	object: 'chat.completion';
	created: number;
	model: string;
	provider: string;
	choices: OpenAIChatChoice[];
	usage: {
		prompt_tokens?: number;
		completion_tokens?: number;
		total_tokens?: number;
	};
	cost?: number;
	raw?: unknown;
	viaGatewayBypass?: boolean;
}

const FINISH_REASON_TO_OPENAI: Record<string, string> = {
	stop: 'stop',
	length: 'length',
	'content-filter': 'content_filter',
	'tool-calls': 'tool_calls',
	error: 'stop',
	other: 'stop',
	unknown: 'stop',
};

export class OpenAIChatFormatAdapter implements FormatAdapter<
	OpenAIChatRequest,
	OpenAIChatResponse
> {
	parseRequest(input: OpenAIChatRequest): GenerateRequest {
		if (!input || typeof input !== 'object') {
			throw new Error('Request body must be a JSON object.');
		}
		if (!input.provider || typeof input.provider !== 'string') {
			throw new Error('"provider" is required and must be a string.');
		}
		if (!input.model || typeof input.model !== 'string') {
			throw new Error('"model" is required and must be a string.');
		}
		if (!Array.isArray(input.messages) || input.messages.length === 0) {
			throw new Error('"messages" is required and must be a non-empty array.');
		}
		if (input.customProvider !== undefined) {
			validateCustomProviderOverride(input.customProvider);
		}

		return {
			provider: input.provider,
			model: input.model,
			messages: input.messages.map(toChatMessage),
			tools: input.tools ? input.tools.map(toToolDefinition) : undefined,
			temperature: input.temperature,
			maxOutputTokens: input.max_tokens,
			topP: input.top_p,
			stopSequences: normalizeStop(input.stop),
			metadata: input.metadata,
			customProvider: input.customProvider,
		};
	}

	formatResponse(response: GenerateResponse): OpenAIChatResponse {
		return {
			id: `chatcmpl-${generateId()}`,
			object: 'chat.completion',
			created: Math.floor(Date.now() / 1000),
			model: response.model,
			provider: response.provider,
			choices: [
				{
					index: 0,
					message: {
						role: 'assistant',
						content: response.text.length > 0 ? response.text : null,
						tool_calls: response.toolCalls?.map((call) => ({
							id: call.toolCallId,
							type: 'function',
							function: {
								name: call.toolName,
								arguments: JSON.stringify(call.args),
							},
						})),
					},
					finish_reason:
						FINISH_REASON_TO_OPENAI[response.finishReason] ?? 'stop',
				},
			],
			usage: {
				prompt_tokens: response.usage.inputTokens,
				completion_tokens: response.usage.outputTokens,
				total_tokens: response.usage.totalTokens,
			},
			cost: response.cost,
			raw: response.raw,
			viaGatewayBypass: response.viaGatewayBypass,
		};
	}
}

function toChatMessage(message: OpenAIChatMessage): ChatMessage {
	const role: ChatRole = message.role;
	return {
		role,
		content:
			message.content === null
				? ''
				: Array.isArray(message.content)
					? message.content.map(toContentPart)
					: message.content,
		// OpenAI's `tool_call_id` matches a tool result back to the assistant
		// message that requested it; there's no accompanying tool *name* on
		// the result message itself (the internal `ChatMessage.toolName` is
		// only ever populated when the wire format already carries it, e.g.
		// Vercel's `UIMessage` tool parts).
		toolCallId: role === 'tool' ? message.tool_call_id : undefined,
	};
}

function toContentPart(part: OpenAIChatContentPart): ContentPart {
	if (part.type === 'image_url') {
		return { type: 'image', image: part.image_url?.url ?? '' };
	}
	return { type: 'text', text: part.text ?? '' };
}

function toToolDefinition(tool: OpenAIChatTool): ToolDefinition {
	return {
		name: tool.function.name,
		description: tool.function.description,
		parameters: tool.function.parameters,
	};
}

function normalizeStop(
	stop: string | string[] | undefined
): string[] | undefined {
	if (stop === undefined) return undefined;
	return Array.isArray(stop) ? stop : [stop];
}

export const openaiChatFormatAdapter = new OpenAIChatFormatAdapter();
