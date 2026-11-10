import { randomUUID } from 'crypto';
import { LlmGatewayConfig } from '../interfaces/llm-gateway';
import {
	LLM_GATEWAY_DEFAULT_MODEL,
	LLM_GATEWAY_DEFAULT_PROVIDER,
} from './llm-gateway-config';

/**
 * A single message in the llm-gateway-service `GenerateRequest` (Vercel AI
 * SDK `UIMessage` shape, the gateway's default wire format).
 */
export interface GatewayChatMessage {
	/** Unique id for the message (required by the gateway's UIMessage validation). */
	id: string;
	role: 'system' | 'user' | 'assistant';
	parts: Array<{ type: 'text'; text: string }>;
}

/** Request body accepted by `generate`, mirroring the gateway `GenerateRequest`. */
export interface GatewayGenerateRequest {
	provider?: string;
	model?: string;
	messages: GatewayChatMessage[];
	system?: string;
	temperature?: number;
	/**
	 * Optional inline OpenAI-compatible endpoint override. When present the
	 * gateway bypasses its own provider registration and calls this endpoint
	 * directly with the given apiKey.
	 */
	customProvider?: { baseUrl: string; apiKey: string };
}

/**
 * Typed error raised when an outbound gateway call fails (network error,
 * non-2xx response, or a response missing the `text` field). The upstream
 * message is preserved for diagnostics; the API key never appears in the
 * message because it is only ever sent as a request header.
 */
export class LlmGatewayRequestError extends Error {
	constructor(
		message: string,
		readonly status?: number,
	) {
		super(message);
		this.name = 'LlmGatewayRequestError';
	}
}

/**
 * Thin fetch-based client for an llm-gateway-service-compatible API.
 *
 * Issues `POST {endpoint}/generate` with the gateway `GenerateRequest` body
 * (Vercel AI SDK `UIMessage` wire format), authenticates with
 * `Authorization: Bearer <apiKey>`, applies service-side defaults for
 * `provider`/`model`, and returns the response `text`. An optional
 * `customProvider` override is forwarded so the gateway can call an
 * OpenAI-compatible endpoint directly without prior registration. Any failure
 * raises a {@link LlmGatewayRequestError} carrying the upstream message
 * instead of returning a partial result.
 */
export class LlmGatewayClient {
	async generate(
		config: LlmGatewayConfig,
		request: GatewayGenerateRequest,
	): Promise<string> {
		const provider =
			request.provider ?? config.provider ?? LLM_GATEWAY_DEFAULT_PROVIDER;
		const model = request.model ?? config.model ?? LLM_GATEWAY_DEFAULT_MODEL;
		const customProvider = request.customProvider ?? config.customProvider;

		const body: Record<string, unknown> = {
			provider,
			model,
			messages: request.messages,
		};
		if (request.system !== undefined) body.system = request.system;
		if (request.temperature !== undefined) {
			body.temperature = request.temperature;
		}
		if (customProvider !== undefined) {
			body.customProvider = customProvider;
		}

		const endpoint = config.endpoint.replace(/\/+$/, '');

		let response: Response;
		try {
			response = await fetch(`${endpoint}/generate`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${config.apiKey}`,
				},
				body: JSON.stringify(body),
			});
		} catch (error) {
			const message =
				error instanceof Error ? error.message : 'Unknown network error';
			throw new LlmGatewayRequestError(
				`LLM gateway request failed: ${message}`,
				undefined,
			);
		}

		if (!response.ok) {
			const message = await this.readUpstreamMessage(response);
			throw new LlmGatewayRequestError(message, response.status);
		}

		let data: unknown;
		try {
			data = await response.json();
		} catch {
			throw new LlmGatewayRequestError(
				'LLM gateway returned an invalid response.',
				response.status,
			);
		}

		const text = (data as { text?: unknown } | null)?.text;
		if (typeof text !== 'string' || text.length === 0) {
			throw new LlmGatewayRequestError(
				'LLM gateway response is missing the text field.',
				response.status,
			);
		}
		return text;
	}

	private async readUpstreamMessage(response: Response): Promise<string> {
		let upstream = '';
		try {
			const data = (await response.json()) as {
				message?: unknown;
				error?: unknown;
			} | null;
			if (typeof data?.message === 'string' && data.message.trim()) {
				upstream = data.message;
			} else if (typeof data?.error === 'string' && data.error.trim()) {
				upstream = data.error;
			}
		} catch {
			/* non-JSON error body — fall through to the generic message */
		}
		return upstream
			? `LLM gateway request failed with status ${response.status}: ${upstream}`
			: `LLM gateway request failed with status ${response.status}.`;
	}
}

/**
 * Converts a plain `{ role, content }` message into the gateway's `UIMessage`
 * shape (a required `id` plus a `parts` array of text parts).
 */
export function toGatewayChatMessage(
	role: GatewayChatMessage['role'],
	content: string,
): GatewayChatMessage {
	return {
		id: randomUUID(),
		role,
		parts: [{ type: 'text', text: content }],
	};
}
