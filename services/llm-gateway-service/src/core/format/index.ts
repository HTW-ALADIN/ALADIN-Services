/**
 * Format adapter registry.
 *
 * Callers (the HTTP API and CLI) select a wire format via an optional
 * `format` field on the request body. When omitted, requests are treated
 * as the Vercel AI SDK format for backward compatibility.
 */
import type { FormatAdapter } from './types.js';
import { vercelFormatAdapter } from './vercel.js';
import { openaiChatFormatAdapter } from './openai-chat.js';
import { openaiResponsesFormatAdapter } from './openai-responses.js';

export const FORMAT_TYPES = ['vercel', 'openai-chat', 'openai-responses'] as const;

export type FormatType = (typeof FORMAT_TYPES)[number];

export const DEFAULT_FORMAT: FormatType = 'vercel';

/**
 * Resolves the `FormatAdapter` for a given `format` value, defaulting to
 * the Vercel adapter when `format` is omitted.
 */
export function getFormatAdapter(format?: string): FormatAdapter {
	const formatType = format ?? DEFAULT_FORMAT;

	switch (formatType) {
		case 'vercel':
			return vercelFormatAdapter;
		case 'openai-chat':
			return openaiChatFormatAdapter;
		case 'openai-responses':
			return openaiResponsesFormatAdapter;
		default:
			throw new Error(
				`Unknown "format": "${formatType}". Supported formats: ${FORMAT_TYPES.join(', ')}.`
			);
	}
}

export { vercelFormatAdapter } from './vercel.js';
export type {
	VercelGenerateRequest,
	VercelGenerateResponse,
	VercelToolCall,
	VercelToolDefinition,
} from './vercel.js';
export { openaiChatFormatAdapter } from './openai-chat.js';
export type {
	OpenAIChatRequest,
	OpenAIChatResponse,
} from './openai-chat.js';
export { openaiResponsesFormatAdapter } from './openai-responses.js';
export type {
	OpenAIResponsesRequest,
	OpenAIResponsesResponse,
} from './openai-responses.js';
export type { FormatAdapter } from './types.js';
