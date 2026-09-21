import { LlmGatewayConfig } from '../interfaces/llm-gateway';

/** Default provider applied when a request's `llmGateway` block omits `provider`. */
export const LLM_GATEWAY_DEFAULT_PROVIDER = 'openai';

/** Default model applied when a request's `llmGateway` block omits `model`. */
export const LLM_GATEWAY_DEFAULT_MODEL = 'gpt-4o-mini';

/**
 * Decides whether a request carries a usable gateway block.
 *
 * A block is usable when it is an object with a non-empty string `endpoint`
 * and a non-empty string `apiKey`. `provider`/`model` are optional; when
 * omitted the service-side defaults are applied by the client. An optional
 * `customProvider` override (non-empty string `baseUrl` and `apiKey`) is
 * forwarded to the gateway so calls can bypass its provider registration.
 */
export function isUsableLlmGatewayBlock(
	block: unknown,
): block is LlmGatewayConfig {
	if (typeof block !== 'object' || block === null) return false;
	const candidate = block as Record<string, unknown>;
	if (
		typeof candidate.endpoint !== 'string' ||
		candidate.endpoint.trim().length === 0 ||
		typeof candidate.apiKey !== 'string' ||
		candidate.apiKey.trim().length === 0 ||
		(candidate.provider !== undefined &&
			typeof candidate.provider !== 'string') ||
		(candidate.model !== undefined && typeof candidate.model !== 'string')
	) {
		return false;
	}
	if (candidate.customProvider === undefined) return true;
	const custom = candidate.customProvider as Record<string, unknown>;
	return (
		typeof custom === 'object' &&
		custom !== null &&
		typeof custom.baseUrl === 'string' &&
		custom.baseUrl.trim().length > 0 &&
		typeof custom.apiKey === 'string' &&
		custom.apiKey.trim().length > 0
	);
}

/**
 * Returns a copy of an unknown value with any `llmGateway.apiKey` replaced by
 * a placeholder, so request bodies can be logged without leaking credentials.
 */
export function redactLlmGatewayBlock<T>(value: T): T {
	if (typeof value !== 'object' || value === null) return value;
	if (Array.isArray(value)) {
		return value.map((item) => redactLlmGatewayBlock(item)) as unknown as T;
	}
	const out: Record<string, unknown> = {};
	for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
		if (
			key === 'llmGateway' &&
			typeof item === 'object' &&
			item !== null
		) {
			out[key] = redactLlmGatewayBlock({ ...(item as object) });
		} else if (key === 'apiKey' && typeof item === 'string') {
			out[key] = '[REDACTED]';
		} else {
			out[key] = redactLlmGatewayBlock(item);
		}
	}
	return out as unknown as T;
}
