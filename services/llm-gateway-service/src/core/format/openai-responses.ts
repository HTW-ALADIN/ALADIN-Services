/**
 * OpenAI Responses API format adapter.
 *
 * Translates between the wire format used by OpenAI's newer
 * `POST /v1/responses` endpoint and this service's internal,
 * format-agnostic `GenerateRequest`/`GenerateResponse` types.
 *
 * As with `./openai-chat.ts`, the OpenAI Node SDK isn't a dependency of
 * this service, so these request/response shapes are hand-written against
 * OpenAI's public API reference rather than imported from an official
 * package.
 *
 * See `./index.ts` for the adapter registry and `./types.ts` for the
 * shared `FormatAdapter` interface.
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
import { generateId, validateCustomProviderOverride } from './shared.js';

export interface OpenAIResponseTextContent {
	type: 'input_text' | 'output_text';
	text: string;
}

export interface OpenAIResponseImageContent {
	type: 'input_image';
	image_url: string;
}

export type OpenAIResponseContent =
	| OpenAIResponseTextContent
	| OpenAIResponseImageContent;

export interface OpenAIResponseMessageInput {
	role: 'system' | 'user' | 'assistant';
	content: string | OpenAIResponseContent[];
}

export interface OpenAIFunctionCallOutputInput {
	type: 'function_call_output';
	call_id: string;
	output: string;
}

export type OpenAIResponseInput =
	| OpenAIResponseMessageInput
	| OpenAIFunctionCallOutputInput;

export interface OpenAIResponseTool {
	type: 'function';
	name: string;
	description?: string;
	parameters: Record<string, unknown>;
}

export interface OpenAIResponsesRequest {
	/** Selects this adapter; required to disambiguate from the default 'vercel' format. */
	format: 'openai-responses';
	/** Provider id (e.g. "openai", "anthropic") this gateway should route to. */
	provider: string;
	model: string;
	input: string | OpenAIResponseInput[];
	instructions?: string;
	tools?: OpenAIResponseTool[];
	temperature?: number;
	max_output_tokens?: number;
	top_p?: number;
	metadata?: Record<string, unknown>;
	customProvider?: CustomProviderOverride;
}

export interface OpenAIResponseFunctionCall {
	type: 'function_call';
	call_id: string;
	name: string;
	arguments: string;
}

export interface OpenAIResponseMessageOutput {
	type: 'message';
	role: 'assistant';
	content: OpenAIResponseTextContent[];
}

export type OpenAIResponseOutput =
	| OpenAIResponseMessageOutput
	| OpenAIResponseFunctionCall;

export interface OpenAIResponsesResponse {
	id: string;
	object: 'response';
	created_at: number;
	model: string;
	provider: string;
	status: string;
	output: OpenAIResponseOutput[];
	output_text: string;
	usage: {
		input_tokens?: number;
		output_tokens?: number;
		total_tokens?: number;
	};
	cost?: number;
	raw?: unknown;
	viaGatewayBypass?: boolean;
}

const FINISH_REASON_TO_STATUS: Record<string, string> = {
	stop: 'completed',
	length: 'incomplete',
	'content-filter': 'incomplete',
	'tool-calls': 'completed',
	error: 'failed',
	other: 'completed',
	unknown: 'completed',
};

export class OpenAIResponsesFormatAdapter implements FormatAdapter<
	OpenAIResponsesRequest,
	OpenAIResponsesResponse
> {
	parseRequest(input: OpenAIResponsesRequest): GenerateRequest {
		if (!input || typeof input !== 'object') {
			throw new Error('Request body must be a JSON object.');
		}
		if (!input.provider || typeof input.provider !== 'string') {
			throw new Error('"provider" is required and must be a string.');
		}
		if (!input.model || typeof input.model !== 'string') {
			throw new Error('"model" is required and must be a string.');
		}
		if (
			input.input === undefined ||
			input.input === null ||
			(typeof input.input !== 'string' && !Array.isArray(input.input))
		) {
			throw new Error('"input" is required and must be a string or array.');
		}
		if (Array.isArray(input.input) && input.input.length === 0) {
			throw new Error('"input" must not be an empty array.');
		}
		if (input.customProvider !== undefined) {
			validateCustomProviderOverride(input.customProvider);
		}

		const messages: ChatMessage[] =
			typeof input.input === 'string'
				? [{ role: 'user', content: input.input }]
				: input.input.map(toChatMessage);

		return {
			provider: input.provider,
			model: input.model,
			messages,
			system: input.instructions,
			tools: input.tools ? input.tools.map(toToolDefinition) : undefined,
			temperature: input.temperature,
			maxOutputTokens: input.max_output_tokens,
			topP: input.top_p,
			metadata: input.metadata,
			customProvider: input.customProvider,
		};
	}

	formatResponse(response: GenerateResponse): OpenAIResponsesResponse {
		const output: OpenAIResponseOutput[] = [];
		if (response.text.length > 0) {
			output.push({
				type: 'message',
				role: 'assistant',
				content: [{ type: 'output_text', text: response.text }],
			});
		}
		for (const call of response.toolCalls ?? []) {
			output.push({
				type: 'function_call',
				call_id: call.toolCallId,
				name: call.toolName,
				arguments: JSON.stringify(call.args),
			});
		}

		return {
			id: `resp_${generateId()}`,
			object: 'response',
			created_at: Math.floor(Date.now() / 1000),
			model: response.model,
			provider: response.provider,
			status: FINISH_REASON_TO_STATUS[response.finishReason] ?? 'completed',
			output,
			output_text: response.text,
			usage: {
				input_tokens: response.usage.inputTokens,
				output_tokens: response.usage.outputTokens,
				total_tokens: response.usage.totalTokens,
			},
			cost: response.cost,
			raw: response.raw,
			viaGatewayBypass: response.viaGatewayBypass,
		};
	}
}

function isFunctionCallOutput(
	input: OpenAIResponseInput
): input is OpenAIFunctionCallOutputInput {
	return 'type' in input && input.type === 'function_call_output';
}

function toChatMessage(input: OpenAIResponseInput): ChatMessage {
	if (isFunctionCallOutput(input)) {
		return {
			role: 'tool',
			content: input.output,
			toolCallId: input.call_id,
		};
	}
	return {
		role: input.role,
		content: Array.isArray(input.content)
			? input.content.map(toContentPart)
			: input.content,
	};
}

function toContentPart(part: OpenAIResponseContent): ContentPart {
	if (part.type === 'input_image') {
		return { type: 'image', image: part.image_url };
	}
	return { type: 'text', text: part.text };
}

function toToolDefinition(tool: OpenAIResponseTool): ToolDefinition {
	return {
		name: tool.name,
		description: tool.description,
		parameters: tool.parameters,
	};
}

export const openaiResponsesFormatAdapter = new OpenAIResponsesFormatAdapter();
