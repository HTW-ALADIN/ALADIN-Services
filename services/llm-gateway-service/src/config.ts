/**
 * Environment-driven configuration for connecting to a self-hosted LLM Gateway
 * instance, plus optional (best-effort) admin API settings used to register
 * custom providers ahead of time.
 */

function envValue(name: string): string | undefined {
	const value = process.env[name];
	return value && value.length > 0 ? value : undefined;
}

export interface GatewayConfig {
	/** Base URL of the self-hosted LLM Gateway's OpenAI-compatible API, e.g. http://gateway:3002/v1 */
	baseUrl: string;
	/** Bearer token used to authenticate inference requests against the gateway. */
	apiKey: string;
	/** Request timeout (ms) applied to gateway and custom-provider HTTP calls. */
	timeoutMs: number;
}

export interface AdminConfig {
	/**
	 * Base URL of the LLM Gateway *management* API (apps/api), used only for the
	 * best-effort `register-provider` command. This is distinct from the
	 * inference `baseUrl` above.
	 */
	baseUrl?: string;
	/**
	 * Bearer token for the management API (e.g. an Enterprise "master key",
	 * `llmgmk_...`). Without this, programmatic provider registration is
	 * skipped and callers should rely on the `customProvider` request
	 * override instead (see core/provider-registry.ts).
	 */
	token?: string;
}

export interface AppConfig {
	gateway: GatewayConfig;
	admin: AdminConfig;
	port: number;
	host: string;
}

export function loadConfig(): AppConfig {
	return {
		gateway: {
			baseUrl: envValue('LLM_GATEWAY_BASE_URL') ?? 'http://localhost:4001/v1',
			apiKey: envValue('LLM_GATEWAY_API_KEY') ?? '',
			timeoutMs: parseInt(envValue('LLM_GATEWAY_TIMEOUT_MS') ?? '60000', 10),
		},
		admin: {
			baseUrl: envValue('LLM_GATEWAY_ADMIN_BASE_URL'),
			token: envValue('LLM_GATEWAY_ADMIN_TOKEN'),
		},
		port: parseInt(envValue('PORT') ?? '8002', 10),
		host: envValue('HOST') ?? '0.0.0.0',
	};
}

export const config = loadConfig();
