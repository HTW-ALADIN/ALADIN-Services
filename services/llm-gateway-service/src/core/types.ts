/**
 * Internal, format-agnostic request/response model.
 *
 * Wire formats (Vercel AI SDK today, potentially OpenAI/Anthropic later) are
 * translated into and out of these types by adapters under `core/format/`.
 * This keeps the gateway client and provider registry decoupled from any
 * single request/response shape.
 */

export type ChatRole = 'system' | 'user' | 'assistant' | 'tool';

export interface TextPart {
	type: 'text';
	text: string;
}

export interface ImagePart {
	type: 'image';
	/** Data URL, http(s) URL, or base64 string. */
	image: string;
	mediaType?: string;
}

/**
 * A non-image file attachment (PDF, etc.), mirroring the Vercel AI SDK's
 * `FilePart`/`FileUIPart` shape. `ImagePart` is kept as a separate variant
 * for backward compatibility even though the AI SDK has deprecated it in
 * favor of `FilePart` with an `image/*` `mediaType`.
 */
export interface FilePart {
	type: 'file';
	/** Data URL, http(s) URL, or base64 string. */
	data: string;
	/** IANA media type, e.g. "application/pdf". */
	mediaType: string;
	filename?: string;
}

export type ContentPart = TextPart | ImagePart | FilePart;

export interface ChatMessage {
	role: ChatRole;
	content: string | ContentPart[];
	/** Present on tool result messages. */
	toolCallId?: string;
	toolName?: string;
}

export interface ToolDefinition {
	name: string;
	description?: string;
	/** JSON Schema describing the tool's parameters. */
	parameters: Record<string, unknown>;
}

/**
 * Inline connection details for an OpenAI-compatible endpoint that has *not*
 * been pre-registered with the gateway. When present, the gateway client
 * bypasses gateway routing for this single request and calls the endpoint
 * directly (see core/provider-registry.ts for the rationale).
 */
export interface CustomProviderOverride {
	baseUrl: string;
	apiKey: string;
}

export interface GenerateRequest {
	/** Provider id (e.g. "openai", "anthropic", or a registered custom provider name). */
	provider: string;
	/** Model id within the provider (e.g. "gpt-4o"). */
	model: string;
	messages: ChatMessage[];
	system?: string;
	tools?: ToolDefinition[];
	temperature?: number;
	maxOutputTokens?: number;
	topP?: number;
	stopSequences?: string[];
	metadata?: Record<string, unknown>;
	/** Ad-hoc custom provider connection info; see CustomProviderOverride. */
	customProvider?: CustomProviderOverride;
}

export interface ToolCall {
	toolCallId: string;
	toolName: string;
	args: unknown;
}

export interface TokenUsage {
	inputTokens?: number;
	outputTokens?: number;
	totalTokens?: number;
}

export type FinishReason =
	| 'stop'
	| 'length'
	| 'content-filter'
	| 'tool-calls'
	| 'error'
	| 'other'
	| 'unknown';

export interface GenerateResponse {
	text: string;
	finishReason: FinishReason;
	usage: TokenUsage;
	/** USD cost reported by the gateway, when available. */
	cost?: number;
	provider: string;
	model: string;
	toolCalls?: ToolCall[];
	/** Raw gateway/provider response, passed through for debugging. */
	raw?: unknown;
	/** True when this request bypassed the gateway via customProvider. */
	viaGatewayBypass?: boolean;
}

export interface EmbedRequest {
	provider: string;
	model: string;
	input: string | string[];
	customProvider?: CustomProviderOverride;
}

export interface EmbedResponse {
	embeddings: number[][];
	usage: TokenUsage;
	provider: string;
	model: string;
	raw?: unknown;
}

/**
 * Structured error carrying the upstream HTTP status so it can be mapped
 * through to the service's own HTTP responses instead of collapsing
 * everything to a single status code.
 */
export class GatewayRequestError extends Error {
	readonly status: number;
	readonly code?: string;
	readonly raw?: unknown;

	constructor(message: string, status: number, code?: string, raw?: unknown) {
		super(message);
		this.name = 'GatewayRequestError';
		this.status = status;
		this.code = code;
		this.raw = raw;
	}
}
