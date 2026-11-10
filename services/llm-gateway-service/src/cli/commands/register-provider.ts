import {
	ProviderRegistry,
	type RegisterProviderInput,
} from '../../core/provider-registry.js';
import { writeJsonOutput } from '../io.js';
import { config } from '../../config.js';

export interface RegisterProviderCommandOptions {
	name: string;
	baseUrl: string;
	apiKey: string;
	output?: string;
}

/**
 * `llm-gateway register-provider --name <name> --base-url <url> --api-key <key>`
 *
 * Best-effort: see core/provider-registry.ts for why this cannot reliably
 * register a provider with a self-hosted gateway without dashboard/session
 * auth or an Enterprise master key. Prefer the `customProvider` inline
 * override on `generate` for one-shot workflow calls.
 */
export async function registerProviderCommand(
	options: RegisterProviderCommandOptions,
	registry: ProviderRegistry = new ProviderRegistry(config.admin)
): Promise<void> {
	const input: RegisterProviderInput = {
		name: options.name,
		baseUrl: options.baseUrl,
		apiKey: options.apiKey,
	};
	const result = await registry.register(input);
	writeJsonOutput(result, options.output);
}
