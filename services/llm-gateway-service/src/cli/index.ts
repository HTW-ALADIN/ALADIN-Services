#!/usr/bin/env node
import { Command } from 'commander';
import { generateCommand } from './commands/generate.js';
import { registerProviderCommand } from './commands/register-provider.js';
import { healthCommand } from './commands/health.js';
import { GatewayRequestError } from '../core/types.js';

const program = new Command();

program
	.name('llm-gateway')
	.description(
		'CLI wrapper around a self-hosted LLM Gateway instance, using the Vercel AI SDK.'
	);

program
	.command('health')
	.description('Print the service health status.')
	.option('-o, --output <file>', 'Write output to a file instead of stdout.')
	.action((options) => healthCommand(options));

program
	.command('generate')
	.description(
		'Generate text (non-streaming) via LLM Gateway. Reads a Vercel AI SDK-format ' +
			'request as JSON from a file or stdin, writes the full response as JSON.'
	)
	.argument(
		'[input-file]',
		'Path to a JSON request file, or "-"/omitted to read from stdin.'
	)
	.option('-o, --output <file>', 'Write output to a file instead of stdout.')
	.action(async (inputFile: string | undefined, options) => {
		await generateCommand(inputFile, options);
	});

program
	.command('register-provider')
	.description(
		'Best-effort registration of a custom OpenAI-compatible provider with LLM Gateway. ' +
			'Prefer the `customProvider` field on `generate` for one-shot calls that should not ' +
			'depend on prior gateway-side registration.'
	)
	.requiredOption(
		'--name <name>',
		'Lowercase provider name (e.g. "mycompany").'
	)
	.requiredOption(
		'--base-url <url>',
		'OpenAI-compatible base URL for the provider.'
	)
	.requiredOption('--api-key <key>', "The provider's API token.")
	.option('-o, --output <file>', 'Write output to a file instead of stdout.')
	.action(async (options) => {
		await registerProviderCommand(options);
	});

async function main() {
	try {
		await program.parseAsync(process.argv);
	} catch (err) {
		if (err instanceof GatewayRequestError) {
			process.stderr.write(`Error (${err.status}): ${err.message}\n`);
		} else {
			const message = err instanceof Error ? err.message : String(err);
			process.stderr.write(`Error: ${message}\n`);
		}
		process.exitCode = 1;
	}
}

main();
