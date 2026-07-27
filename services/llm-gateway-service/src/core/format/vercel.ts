/**
 * Vercel AI SDK format adapter.
 *
 * Translates between the wire format used by Vercel AI SDK frontends
 * (`useChat`-style UI messages) and this service's internal,
 * format-agnostic `GenerateRequest`/`GenerateResponse` types.
 *
 * Messages use the official `UIMessage` shape from the `ai` package
 * (a `parts` array of typed elements — text, file, reasoning, tool
 * invocations, etc.) rather than a hand-rolled `content` string/array, so
 * this adapter stays compatible with whatever `useChat()` actually sends.
 *
 * This is one of several format adapters; see `./index.ts` for the
 * adapter registry and `./types.ts` for the shared `FormatAdapter`
 * interface that lets the HTTP/CLI layers stay agnostic of the wire
 * format in use.
 */
import {
	getToolName,
	isFileUIPart,
	isTextUIPart,
	isToolUIPart,
	type FileUIPart,
	type UIMessage,
} from 'ai';
import type {
	ChatMessage,
	CustomProviderOverride,
	FilePart,
	GenerateRequest,
	GenerateResponse,
	ImagePart,
	ToolDefinition,
} from '../types.js';
import type { FormatAdapter } from './types.js';
import { validateCustomProviderOverride } from './shared.js';

export interface VercelToolDefinition {
	description?: string;
	/** JSON Schema for the tool's parameters, matching the AI SDK's `inputSchema`. */
	inputSchema: Record<string, unknown>;
}

export interface VercelGenerateRequest {
	/** Selects this adapter; optional, defaults to `'vercel'`. */
	format?: 'vercel';
	provider: string;
	model: string;
	/** Official Vercel AI SDK `UIMessage[]` shape (see the `ai` package). */
	messages: UIMessage[];
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
		input.messages.forEach(validateUIMessage);
		if (input.customProvider !== undefined) {
			validateCustomProviderOverride(input.customProvider);
		}

		return {
			provider: input.provider,
			model: input.model,
			messages: input.messages.flatMap(toChatMessages),
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

function validateUIMessage(message: UIMessage): void {
	if (!message || typeof message !== 'object') {
		throw new Error('Each message must be an object.');
	}
	if (typeof message.id !== 'string' || message.id.length === 0) {
		throw new Error('Each message must have a non-empty string "id".');
	}
	if (
		message.role !== 'system' &&
		message.role !== 'user' &&
		message.role !== 'assistant'
	) {
		throw new Error(
			`Message "role" must be one of "system", "user", or "assistant", got "${String(message.role)}".`
		);
	}
	if (!Array.isArray(message.parts)) {
		throw new Error('Each message must have a "parts" array.');
	}
}

/**
 * Converts a single `UIMessage` into one or more internal `ChatMessage`s.
 *
 * A `UIMessage` bundles everything about one turn - text, files, reasoning,
 * and tool call/result lifecycles - into a single `parts` array (there is no
 * separate "tool" role in `UIMessage`, unlike the internal `ChatMessage`
 * type). Completed tool invocations are therefore split out into their own
 * `role: 'tool'` `ChatMessage`s, mirroring how the AI SDK's own
 * `convertToModelMessages` splits a `UIMessage` into multiple
 * `ModelMessage`s.
 *
 * Notes on fidelity vs. the internal `ChatMessage` type:
 * - Reasoning parts are intentionally dropped: they represent the model's
 *   own prior "thinking" and the internal `ChatMessage`/`ContentPart` shape
 *   has no dedicated slot for resending it.
 * - Tool calls that haven't produced output yet (e.g. `input-streaming`,
 *   `input-available`, `approval-requested`) aren't representable on the
 *   internal assistant `ChatMessage` (it has no tool-call content part), so
 *   only completed (`output-available`) invocations are carried through.
 * - File parts are carried through for any `mediaType`, matching the AI
 *   SDK's own `convertToModelMessages`: `image/*` becomes an `ImagePart`,
 *   everything else (PDFs, etc.) becomes a `FilePart`. What a given
 *   provider actually accepts is out of scope here.
 */
function toChatMessages(message: UIMessage): ChatMessage[] {
	const text = message.parts
		.filter(isTextUIPart)
		.map((part) => part.text)
		.join('');
	const files = message.parts.filter(isFileUIPart).map(toFileContentPart);

	const messages: ChatMessage[] = [];

	if (text.length > 0 || files.length > 0) {
		messages.push({
			role: message.role,
			content:
				files.length > 0
					? [...(text.length > 0 ? [{ type: 'text' as const, text }] : []), ...files]
					: text,
		});
	}

	for (const part of message.parts) {
		if (!isToolUIPart(part)) continue;
		if (part.state !== 'output-available') continue;
		messages.push({
			role: 'tool',
			content: JSON.stringify(part.output),
			toolCallId: part.toolCallId,
			toolName: getToolName(part),
		});
	}

	return messages;
}

function toFileContentPart(part: FileUIPart): ImagePart | FilePart {
	if (part.mediaType.startsWith('image/')) {
		return { type: 'image', image: part.url, mediaType: part.mediaType };
	}
	return {
		type: 'file',
		data: part.url,
		mediaType: part.mediaType,
		filename: part.filename,
	};
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
