import { Command } from 'commander';
import type { ServiceLimits } from '../config.js';
import { loadLimits } from '../config.js';
import { ServiceError, toProblem } from '../errors.js';
import { inspectRequestStructure, realize } from '../realizer.js';
import { validateGenerateRequest } from '../validation.js';
import { readRequest } from './io.js';

export interface CliStreams {
	stdout: Pick<NodeJS.WriteStream, 'write'>;
	stderr: Pick<NodeJS.WriteStream, 'write'>;
}

export interface RunCliOptions {
	streams?: CliStreams;
	limits?: ServiceLimits;
}

export async function runCli(
	argv: string[],
	options: RunCliOptions = {}
): Promise<number> {
	const streams = options.streams ?? {
		stdout: process.stdout,
		stderr: process.stderr,
	};
	const limits = options.limits ?? loadLimits();
	const program = new Command();
	program
		.name('nlg')
		.description(
			'Deterministic surface realisation and trusted template generation.'
		)
		.exitOverride()
		.configureOutput({
			writeOut: (value) => streams.stdout.write(value),
			writeErr: (value) => streams.stderr.write(value),
		});

	program
		.command('generate')
		.description(
			'Generate text from the same JSON request used by POST /v1/generate.'
		)
		.requiredOption(
			'-r, --request <path>',
			'JSON request file, or - for stdin.'
		)
		.option('--json', 'Write the complete JSON response instead of text.')
		.action(async (commandOptions: { request: string; json?: boolean }) => {
			const raw = await readRequest(
				commandOptions.request,
				limits.maxBodyBytes
			);
			inspectRequestStructure(raw, limits);
			const request = validateGenerateRequest(raw);
			const result = await realize(request, limits);
			streams.stdout.write(
				commandOptions.json ? `${JSON.stringify(result)}\n` : `${result.text}\n`
			);
		});

	try {
		await program.parseAsync(argv, { from: 'user' });
		return 0;
	} catch (error) {
		if (error instanceof ServiceError) {
			streams.stderr.write(`${JSON.stringify(toProblem(error))}\n`);
		} else if (
			error instanceof Error &&
			'code' in error &&
			String(error.code).startsWith('commander.')
		) {
			// Commander already wrote a concise usage error to stderr.
		} else {
			const detail = error instanceof Error ? error.message : String(error);
			streams.stderr.write(
				`${JSON.stringify(
					toProblem(
						new ServiceError('internal-error', 500, 'Internal error', detail)
					)
				)}\n`
			);
		}
		return 1;
	}
}
