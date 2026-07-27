import {
	createLLMGateway,
	type LLMGatewayProvider,
} from '@llmgateway/ai-sdk-provider';
import { generateText, tool, jsonSchema, type ModelMessage } from 'ai';
import type { GatewayConfig } from '../config.js';
import {
	GatewayRequestError,
	type ChatMessage,
	type ContentPart,
	type EmbedRequest,
	type EmbedResponse,
	type FinishReason,
	type GenerateRequest,
	type GenerateResponse,
	type TokenUsage,
	type ToolCall,
	type ToolDefinition,
} from './types.js';

/**
 * Talks to a self-hosted LLM Gateway instance via the Vercel AI SDK +
 * `@llmgateway/ai-sdk-provider` for the normal (gateway-routed) path.
 *
 * Custom provider handling: LLM Gateway custom providers are normally
 * registered ahead of time via the dashboard/admin API (see
 * `provider-registry.ts`). Since a general-purpose, bearer-token
 * authenticated admin endpoint for *creating* custom provider keys is not
 * reliably available (it is dashboard/session-auth gated, and LLM Gateway's
 * programmatic "Master Keys" API — Enterprise only — does not cover provider
 * key management either), this client also supports an inline
 * `customProvider` override on a per-request basis: when present, the
 * request bypasses the gateway entirely and is sent directly to the given
 * OpenAI-compatible endpoint (`/chat/completions` or `/embeddings`), via a
 * plain `fetch` call so the bypass path doesn't depend on an AI SDK provider
 * package version tied to the gateway's own AI SDK major version. This is
 * what allows a workflow to deploy, configure, and call a brand-new custom
 * provider in a single step without any prior gateway registration.
 *
 * `customProvider.baseUrl` is expected to have already been validated by the
 * caller (see `core/url-safety.ts` and `core/format/vercel.ts::parseRequest`,
 * which run at the untrusted HTTP/CLI input boundary) — this class itself
 * does not re-validate it, so it remains usable in trusted/internal contexts
 * (tests, programmatic callers) that intentionally target loopback or
 * private addresses.
 */
export class GatewayClient {
	private readonly gateway: LLMGatewayProvider;

	constructor(private readonly gatewayConfig: GatewayConfig) {
		this.gateway = createLLMGateway({
			baseURL: gatewayConfig.baseUrl,
			apiKey: gatewayConfig.apiKey,
		});
	}

	async generate(request: GenerateRequest): Promise<GenerateResponse> {
		if (request.customProvider) {
			return this.generateViaCustomProvider(request);
		}
		return this.generateViaGateway(request);
	}

	async embedText(request: EmbedRequest): Promise<EmbedResponse> {
		if (request.customProvider) {
			return this.embedViaCustomProvider(request);
		}
		return this.embedViaGateway(request);
	}

	private async generateViaGateway(
		request: GenerateRequest
	): Promise<GenerateResponse> {
		this.requireGatewayApiKey();

		try {
			const result = await generateText({
				// `usage.include` asks LLM Gateway to attach cost/usage-accounting
				// details under `providerMetadata.llmgateway.usage`, which we
				// surface on the response as `cost` (see extractCost below).
				model: this.gateway(`${request.provider}/${request.model}`, {
					usage: { include: true },
				}),
				system: request.system,
				messages: toModelMessages(request.messages),
				tools: toToolSet(request.tools),
				temperature: request.temperature,
				maxOutputTokens: request.maxOutputTokens,
				topP: request.topP,
				stopSequences: request.stopSequences,
				maxRetries: 1,
				abortSignal: AbortSignal.timeout(this.gatewayConfig.timeoutMs),
			});

			return {
				text: result.text,
				finishReason: normalizeFinishReason(result.finishReason),
				usage: {
					inputTokens: result.usage?.inputTokens ?? undefined,
					outputTokens: result.usage?.outputTokens ?? undefined,
					totalTokens: result.usage?.totalTokens ?? undefined,
				},
				cost: extractCost(result.providerMetadata),
				provider: request.provider,
				model: request.model,
				toolCalls: toToolCalls(result.toolCalls),
				raw: result,
				viaGatewayBypass: false,
			};
		} catch (err) {
			throw toGatewayRequestError(err);
		}
	}

	private async generateViaCustomProvider(
		request: GenerateRequest
	): Promise<GenerateResponse> {
		const cp = request.customProvider!;
		const body = await postOpenAICompatible(
			`${normalizeBaseUrl(cp.baseUrl)}/chat/completions`,
			cp.apiKey,
			{
				model: request.model,
				messages: toOpenAIChatMessages(request.system, request.messages),
				tools: toOpenAITools(request.tools),
				temperature: request.temperature,
				max_tokens: request.maxOutputTokens,
				top_p: request.topP,
				stop: request.stopSequences,
			},
			this.gatewayConfig.timeoutMs
		);

		const choice = body?.choices?.[0];
		if (!choice) {
			throw new GatewayRequestError(
				'Custom provider response did not include any choices.',
				502,
				undefined,
				body
			);
		}

		return {
			text: choice.message?.content ?? '',
			finishReason: mapOpenAIFinishReason(choice.finish_reason),
			usage: toChatTokenUsage(body?.usage),
			provider: request.provider,
			model: request.model,
			toolCalls: toToolCallsFromOpenAI(choice.message?.tool_calls),
			raw: body,
			viaGatewayBypass: true,
		};
	}

	/**
	 * `@llmgateway/ai-sdk-provider` does not expose an embedding model
	 * abstraction, even though the gateway itself has a `/v1/embeddings`
	 * REST endpoint (mirroring OpenAI's embeddings API). We call it directly,
	 * via the same helper used for the custom-provider bypass so both paths
	 * compute usage identically.
	 */
	private async embedViaGateway(request: EmbedRequest): Promise<EmbedResponse> {
		this.requireGatewayApiKey();

		const body = await postOpenAICompatible(
			`${normalizeBaseUrl(this.gatewayConfig.baseUrl)}/embeddings`,
			this.gatewayConfig.apiKey,
			{ model: `${request.provider}/${request.model}`, input: request.input },
			this.gatewayConfig.timeoutMs
		);

		return {
			embeddings: (body?.data ?? []).map((item: any) => item.embedding),
			usage: toEmbeddingTokenUsage(body?.usage),
			provider: request.provider,
			model: request.model,
			raw: body,
		};
	}

	private async embedViaCustomProvider(
		request: EmbedRequest
	): Promise<EmbedResponse> {
		const cp = request.customProvider!;
		const body = await postOpenAICompatible(
			`${normalizeBaseUrl(cp.baseUrl)}/embeddings`,
			cp.apiKey,
			{ model: request.model, input: request.input },
			this.gatewayConfig.timeoutMs
		);

		return {
			embeddings: (body?.data ?? []).map((item: any) => item.embedding),
			usage: toEmbeddingTokenUsage(body?.usage),
			provider: request.provider,
			model: request.model,
			raw: body,
		};
	}

	private requireGatewayApiKey(): void {
		if (!this.gatewayConfig.apiKey) {
			throw new GatewayRequestError(
				'LLM_GATEWAY_API_KEY is not configured. Set it to call the gateway, or pass a ' +
					'"customProvider" override to call an OpenAI-compatible endpoint directly.',
				500
			);
		}
	}
}

function normalizeBaseUrl(baseUrl: string): string {
	return baseUrl.replace(/\/$/, '');
}

/**
 * Shared "call an OpenAI-compatible REST endpoint" helper used by both the
 * gateway path (embeddings) and the custom-provider bypass path (chat +
 * embeddings), so error handling, timeouts, and response parsing can't drift
 * between the two.
 */
async function postOpenAICompatible(
	url: string,
	apiKey: string,
	body: unknown,
	timeoutMs: number
): Promise<any> {
	let response: Response;
	try {
		response = await fetch(url, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${apiKey}`,
			},
			body: JSON.stringify(body),
			signal: AbortSignal.timeout(timeoutMs),
		});
	} catch (err) {
		throw toGatewayRequestError(err);
	}

	const json = await response.json().catch(() => undefined);
	if (!response.ok) {
		throw new GatewayRequestError(
			json?.error?.message ??
				`Request to ${url} failed with status ${response.status}`,
			response.status,
			json?.error?.code,
			json
		);
	}
	return json;
}

function toModelMessages(messages: ChatMessage[]): ModelMessage[] {
	return messages.map((message) => ({
		role: message.role,
		content: message.content,
		...(message.toolCallId ? { toolCallId: message.toolCallId } : {}),
		...(message.toolName ? { toolName: message.toolName } : {}),
	})) as ModelMessage[];
}

function toToolSet(tools: ToolDefinition[] | undefined) {
	if (!tools || tools.length === 0) {
		return undefined;
	}

	const toolSet: Record<string, ReturnType<typeof tool>> = {};
	for (const definition of tools) {
		toolSet[definition.name] = tool({
			description: definition.description,
			inputSchema: jsonSchema(definition.parameters as any),
			// No `execute`: tool calls are returned to the caller (e.g. the
			// Vercel AI SDK frontend) to execute themselves, rather than being
			// invoked by this service.
		});
	}
	return toolSet;
}

function toToolCalls(toolCalls: unknown): ToolCall[] | undefined {
	if (!Array.isArray(toolCalls) || toolCalls.length === 0) {
		return undefined;
	}
	return toolCalls.map((call: any) => ({
		toolCallId: call.toolCallId,
		toolName: call.toolName,
		args: call.input ?? call.args,
	}));
}

function normalizeFinishReason(reason: unknown): FinishReason {
	const known: FinishReason[] = [
		'stop',
		'length',
		'content-filter',
		'tool-calls',
		'error',
		'other',
		'unknown',
	];
	return known.includes(reason as FinishReason)
		? (reason as FinishReason)
		: 'unknown';
}

/**
 * Extracts the per-request cost reported by LLM Gateway's usage-accounting
 * extension, when present in the AI SDK result's provider metadata.
 */
function extractCost(providerMetadata: unknown): number | undefined {
	if (!providerMetadata || typeof providerMetadata !== 'object') {
		return undefined;
	}
	const meta = providerMetadata as Record<string, any>;
	const llmgateway = meta.llmgateway ?? meta.openai ?? undefined;
	const cost = llmgateway?.usage?.cost ?? llmgateway?.cost;
	return typeof cost === 'number' ? cost : undefined;
}

// ---------------------------------------------------------------------------
// OpenAI chat-completions request/response mapping, used only for the
// customProvider bypass path (raw fetch, no AI SDK model wrapper involved).
// ---------------------------------------------------------------------------

function toOpenAIChatMessages(
	system: string | undefined,
	messages: ChatMessage[]
): unknown[] {
	const result: unknown[] = [];
	if (system) {
		result.push({ role: 'system', content: system });
	}
	for (const message of messages) {
		result.push({
			role: message.role,
			content: Array.isArray(message.content)
				? message.content.map(toOpenAIContentPart)
				: message.content,
			...(message.toolCallId ? { tool_call_id: message.toolCallId } : {}),
		});
	}
	return result;
}

function toOpenAIContentPart(part: ContentPart): unknown {
	if (part.type === 'image') {
		return { type: 'image_url', image_url: { url: part.image } };
	}
	if (part.type === 'file') {
		// OpenAI's chat-completions file content part only accepts inline
		// `file_data` (a data URL) or a pre-uploaded `file_id`; unlike images,
		// it has no `file_url` variant. Rather than fetch a caller-supplied
		// remote URL server-side (reopening the SSRF surface that
		// `assertSafeCustomProviderBaseUrl` closes for `customProvider.baseUrl`
		// itself, plus unbounded memory use for large files), reject anything
		// that isn't already an inline data URL.
		if (!part.data.startsWith('data:')) {
			throw new GatewayRequestError(
				'File attachments sent through a "customProvider" override must be a ' +
					'data URL (e.g. "data:application/pdf;base64,..."); remote http(s) ' +
					'URLs are not supported on the direct-bypass path.',
				400
			);
		}
		return {
			type: 'file',
			file: {
				...(part.filename ? { filename: part.filename } : {}),
				file_data: part.data,
			},
		};
	}
	return { type: 'text', text: part.text };
}

function toOpenAITools(
	tools: ToolDefinition[] | undefined
): unknown[] | undefined {
	if (!tools || tools.length === 0) {
		return undefined;
	}
	return tools.map((definition) => ({
		type: 'function',
		function: {
			name: definition.name,
			description: definition.description,
			parameters: definition.parameters,
		},
	}));
}

function toToolCallsFromOpenAI(toolCalls: unknown): ToolCall[] | undefined {
	if (!Array.isArray(toolCalls) || toolCalls.length === 0) {
		return undefined;
	}
	return toolCalls.map((call: any) => ({
		toolCallId: call.id,
		toolName: call.function?.name,
		args: parseToolArguments(call.function?.arguments),
	}));
}

function parseToolArguments(rawArguments: unknown): unknown {
	if (typeof rawArguments !== 'string') {
		return rawArguments;
	}
	try {
		return JSON.parse(rawArguments);
	} catch {
		return rawArguments;
	}
}

function mapOpenAIFinishReason(reason: unknown): FinishReason {
	switch (reason) {
		case 'stop':
			return 'stop';
		case 'length':
			return 'length';
		case 'content_filter':
			return 'content-filter';
		case 'tool_calls':
		case 'function_call':
			return 'tool-calls';
		default:
			return typeof reason === 'string' ? 'other' : 'unknown';
	}
}

function toChatTokenUsage(usage: any): TokenUsage {
	return {
		inputTokens: usage?.prompt_tokens ?? undefined,
		outputTokens: usage?.completion_tokens ?? undefined,
		totalTokens: usage?.total_tokens ?? undefined,
	};
}

function toEmbeddingTokenUsage(usage: any): TokenUsage {
	// Embeddings requests have no output tokens, so total == input.
	const inputTokens = usage?.prompt_tokens ?? undefined;
	return {
		inputTokens,
		totalTokens: usage?.total_tokens ?? inputTokens,
	};
}

/**
 * Maps AI SDK / provider errors onto a GatewayRequestError carrying the
 * upstream HTTP status, so the API/CLI layer can propagate meaningful status
 * codes instead of collapsing every failure into one generic error.
 */
export function toGatewayRequestError(err: unknown): GatewayRequestError {
	if (err instanceof GatewayRequestError) {
		return err;
	}

	// The AI SDK wraps transient failures (including HTTP error responses,
	// which it treats as retryable) in an AI_RetryError after exhausting
	// retries. The original APICallError — and its real HTTP status — is
	// available on `lastError` (and in the `errors` array), not on the
	// RetryError itself.
	const anyErr = err as any;
	const innermost = anyErr?.lastError ?? anyErr;

	const status: number | undefined =
		innermost?.statusCode ??
		innermost?.status ??
		innermost?.response?.status ??
		innermost?.cause?.statusCode;
	const message: string =
		innermost?.message ?? anyErr?.message ?? 'LLM Gateway request failed';
	const code: string | undefined = innermost?.code ?? innermost?.name;

	// Default to 502 (bad gateway) when the upstream didn't provide a status,
	// matching "we couldn't successfully reach/interpret the LLM Gateway".
	return new GatewayRequestError(
		message,
		status ?? 502,
		code,
		innermost?.data ?? innermost?.responseBody
	);
}
