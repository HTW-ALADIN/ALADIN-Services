/**
 * Vercel AI SDK format adapter.
 *
 * Translates between the wire format used by Vercel AI SDK frontends
 * (`useChat`/`generateText`-style messages and results) and this service's
 * internal, format-agnostic `GenerateRequest`/`GenerateResponse` types.
 *
 * This is the only format implemented today; the adapter interface in
 * `./types.ts` exists so OpenAI- or Anthropic-shaped adapters can be added
 * later without touching the gateway client or provider registry.
 */
import type {
	ChatMessage,
	ContentPart,
	CustomProviderOverride,
	GenerateRequest,
	GenerateResponse,
	ToolDefinition,
} from '../types.js';
import type { FormatAdapter } from './types.js';
import { assertSafeCustomProviderBaseUrl } from '../url-safety.js';

export interface VercelContentPart {
	type: 'text' | 'image';
	text?: string;
	image?: string;
	mediaType?: string;
}

export interface VercelMessage {
	role: 'system' | 'user' | 'assistant' | 'tool';
	content: string | VercelContentPart[];
	toolCallId?: string;
	toolName?: string;
}

export interface VercelToolDefinition {
	description?: string;
	/** JSON Schema for the tool's parameters, matching the AI SDK's `inputSchema`. */
	inputSchema: Record<string, unknown>;
}

export interface VercelGenerateRequest {
	provider: string;
	model: string;
	messages: VercelMessage[];
	system?: string;
	tools?: Record<string, VercelToolDefinition>;
	temperature?: number;
	maxOutputTokens?: number;
	topP?: number;
	stopSequences?: string[];
	metadata?: Record<string, unknown>;
	/**
	 * Inline connection details for an OpenAI-compatible endpoint that has not
	 * been pre-registered with the gateway. Enables "deploy, configure, and
	 * call a custom provider" in a single request.
	 */
	customProvider?: CustomProviderOverride;
}

export interface VercelToolCall {
	toolCallId: string;
	toolName: string;
	input: unknown;
}

export interface VercelGenerateResponse {
	text: string;
	finishReason: string;
	usage: {
		inputTokens?: number;
		outputTokens?: number;
		totalTokens?: number;
	};
	cost?: number;
	provider: string;
	model: string;
	toolCalls?: VercelToolCall[];
	raw?: unknown;
	viaGatewayBypass?: boolean;
}

export class VercelFormatAdapter implements FormatAdapter<
	VercelGenerateRequest,
	VercelGenerateResponse
> {
	parseRequest(input: VercelGenerateRequest): GenerateRequest {
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
			system: input.system,
			tools: input.tools ? toToolDefinitions(input.tools) : undefined,
			temperature: input.temperature,
			maxOutputTokens: input.maxOutputTokens,
			topP: input.topP,
			stopSequences: input.stopSequences,
			metadata: input.metadata,
			customProvider: input.customProvider,
		};
	}

	formatResponse(response: GenerateResponse): VercelGenerateResponse {
		return {
			text: response.text,
			finishReason: response.finishReason,
			usage: response.usage,
			cost: response.cost,
			provider: response.provider,
			model: response.model,
			toolCalls: response.toolCalls?.map((call) => ({
				toolCallId: call.toolCallId,
				toolName: call.toolName,
				input: call.args,
			})),
			raw: response.raw,
			viaGatewayBypass: response.viaGatewayBypass,
		};
	}
}

function validateCustomProviderOverride(
	customProvider: CustomProviderOverride
): void {
	if (!customProvider || typeof customProvider !== 'object') {
		throw new Error(
			'"customProvider" must be an object with "baseUrl" and "apiKey".'
		);
	}
	if (!customProvider.baseUrl || typeof customProvider.baseUrl !== 'string') {
		throw new Error(
			'"customProvider.baseUrl" is required and must be a non-empty string.'
		);
	}
	if (!customProvider.apiKey || typeof customProvider.apiKey !== 'string') {
		throw new Error(
			'"customProvider.apiKey" is required and must be a non-empty string.'
		);
	}
	assertSafeCustomProviderBaseUrl(customProvider.baseUrl);
}

function toChatMessage(message: VercelMessage): ChatMessage {
	return {
		role: message.role,
		content: Array.isArray(message.content)
			? message.content.map(toContentPart)
			: message.content,
		toolCallId: message.toolCallId,
		toolName: message.toolName,
	};
}

function toContentPart(part: VercelContentPart): ContentPart {
	if (part.type === 'image') {
		return {
			type: 'image',
			image: part.image ?? '',
			mediaType: part.mediaType,
		};
	}
	return { type: 'text', text: part.text ?? '' };
}

function toToolDefinitions(
	tools: Record<string, VercelToolDefinition>
): ToolDefinition[] {
	return Object.entries(tools).map(([name, definition]) => ({
		name,
		description: definition.description,
		parameters: definition.inputSchema,
	}));
}

export const vercelFormatAdapter = new VercelFormatAdapter();
