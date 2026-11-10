/**
 * Per-request LLM gateway connection details.
 *
 * Callers that want LLM-backed description variants supply this block on the
 * request. The service never reads gateway location or credentials from its
 * own environment; `endpoint` is the base URL of an
 * llm-gateway-service-compatible API (`/generate` is appended by the client)
 * and `apiKey` is sent as an `Authorization: Bearer` header on every outbound
 * call.
 */
export interface LlmGatewayConfig {
	/** Base URL of an llm-gateway-service-compatible API (no trailing slash). */
	endpoint: string;
	/** Bearer token sent to the gateway on every outbound call. */
	apiKey: string;
	/** Provider id override (e.g. "openai"). Defaults to "openai". */
	provider?: string;
	/** Model id override (e.g. "gpt-4o-mini"). Defaults to "gpt-4o-mini". */
	model?: string;
	/**
	 * Optional inline OpenAI-compatible endpoint that bypasses the gateway's
	 * own provider registration. When present, the gateway routes the request
	 * directly to `baseUrl` using `apiKey` instead of its configured default
	 * provider, so callers can use any provider without pre-registering it.
	 */
	customProvider?: {
		/** Base URL of an OpenAI-compatible API (`/chat/completions` is appended by the gateway). */
		baseUrl: string;
		/** Provider-specific token for the custom endpoint. */
		apiKey: string;
	};
}
