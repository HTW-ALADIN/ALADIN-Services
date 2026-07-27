/**
 * Helpers shared across format adapters (`./vercel.ts`, `./openai-chat.ts`,
 * `./openai-responses.ts`) to avoid drift between otherwise-identical
 * validation/response-shaping logic.
 */
import type { CustomProviderOverride } from '../types.js';
import { assertSafeCustomProviderBaseUrl } from '../url-safety.js';

/**
 * Validates an inline `customProvider` override. Shared by every format
 * adapter so a future change to these rules (or to the SSRF check in
 * `assertSafeCustomProviderBaseUrl`) can't silently apply to only some
 * wire formats.
 */
export function validateCustomProviderOverride(
	customProvider: CustomProviderOverride
): void {
	if (!customProvider || typeof customProvider !== 'object') {
		throw new Error(
			'"customProvider" must be an object with "baseUrl" and "apiKey".'
		);
	}
	if (!customProvider.baseUrl || typeof customProvider.baseUrl !== 'string') {
		throw new Error(
			'"customProvider.baseUrl" is required and must be a non-empty string.'
		);
	}
	if (!customProvider.apiKey || typeof customProvider.apiKey !== 'string') {
		throw new Error(
			'"customProvider.apiKey" is required and must be a non-empty string.'
		);
	}
	assertSafeCustomProviderBaseUrl(customProvider.baseUrl);
}

/**
 * Generates a short, non-cryptographic random id suffix for synthesized
 * response ids (e.g. `chatcmpl-<id>`, `resp_<id>`). Not used for anything
 * security-sensitive.
 */
export function generateId(): string {
	return Math.random().toString(36).slice(2) + Date.now().toString(36);
}
