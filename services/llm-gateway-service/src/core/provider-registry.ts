import type { AdminConfig } from '../config.js';
import { GatewayRequestError } from './types.js';

export interface RegisterProviderInput {
	/** Lowercase name, must match /^[a-z]+(-[a-z]+)*$/ per LLM Gateway's custom provider naming rules. */
	name: string;
	/** OpenAI-compatible base URL for the custom provider (gateway appends /v1/chat/completions). */
	baseUrl: string;
	/** Provider-specific API token, sent as `Authorization: Bearer {token}` by the gateway. */
	apiKey: string;
}

export interface RegisterProviderResult {
	registered: boolean;
	mode: 'gateway-admin-api' | 'skipped';
	message: string;
}

const CUSTOM_PROVIDER_NAME_PATTERN = /^[a-z]+(-[a-z]+)*$/;

/**
 * Registers a custom OpenAI-compatible provider with LLM Gateway.
 *
 * ## Why this is "best effort"
 *
 * LLM Gateway's custom-provider registration (`providerKey` table, exposed
 * via `apps/api/src/routes/keys-provider.ts` in the gateway's source) is
 * designed to be driven from the dashboard with a logged-in session. LLM
 * Gateway's only documented bearer-token-authenticated programmatic API
 * ("Master Keys", see /features/master-keys) is an **Enterprise-only**
 * feature, and even then it only covers projects, gateway API keys, and IAM
 * rules — not provider-key/BYOK registration.
 *
 * As a result, there is no generally-available, stable, bearer-token API to
 * create a custom provider key in one automated step. This function still
 * attempts it — via a configurable admin base URL + bearer token, in case a
 * self-hosted deployment exposes such an endpoint (e.g. an Enterprise master
 * key, or a future/internal admin API) — but treats failure as a soft
 * failure and logs guidance rather than throwing, since the *actual*
 * "deploy + configure + call in one go" requirement is satisfied by the
 * `customProvider` inline override on `POST /generate` / `generate` CLI
 * command instead (see `gateway-client.ts`), which bypasses the need for
 * prior registration entirely.
 */
export class ProviderRegistry {
	constructor(private readonly adminConfig: AdminConfig) {}

	async register(
		input: RegisterProviderInput
	): Promise<RegisterProviderResult> {
		validateProviderName(input.name);

		if (!this.adminConfig.baseUrl || !this.adminConfig.token) {
			return {
				registered: false,
				mode: 'skipped',
				message:
					'LLM_GATEWAY_ADMIN_BASE_URL / LLM_GATEWAY_ADMIN_TOKEN are not configured, ' +
					'so no attempt was made to register this provider with the gateway. ' +
					'Use the `customProvider` field on generate requests to call this endpoint ' +
					'directly (bypassing the gateway) without prior registration, or register the ' +
					'provider once via the LLM Gateway dashboard for gateway-side cost tracking and reuse.',
			};
		}

		const url = `${this.adminConfig.baseUrl.replace(/\/$/, '')}/keys/provider`;
		let response: Response;
		try {
			response = await fetch(url, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${this.adminConfig.token}`,
				},
				body: JSON.stringify({
					provider: 'custom',
					name: input.name,
					baseUrl: input.baseUrl,
					token: input.apiKey,
				}),
			});
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			throw new GatewayRequestError(
				`Failed to reach LLM Gateway admin API: ${message}`,
				502
			);
		}

		const body = await response.json().catch(() => undefined);
		if (!response.ok) {
			throw new GatewayRequestError(
				body?.error?.message ??
					`LLM Gateway admin API rejected provider registration with status ${response.status}`,
				response.status,
				body?.error?.code,
				body
			);
		}

		return {
			registered: true,
			mode: 'gateway-admin-api',
			message: `Custom provider "${input.name}" registered with LLM Gateway.`,
		};
	}
}

export function validateProviderName(name: string): void {
	if (!CUSTOM_PROVIDER_NAME_PATTERN.test(name)) {
		throw new GatewayRequestError(
			`Invalid provider name "${name}". Custom provider names must be lowercase letters with optional single hyphens (e.g. "mycompany", "eu-west").`,
			400
		);
	}
}
