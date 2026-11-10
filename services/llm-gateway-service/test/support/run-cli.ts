import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI_ENTRY = resolve(__dirname, '../../src/cli/index.ts');

export interface RunCliResult {
	exitCode: number | null;
	stdout: string;
	stderr: string;
}

/**
 * Spawns the actual CLI entrypoint as a real child process (via `tsx`), so
 * integration tests exercise real argv parsing, env-driven configuration,
 * and stdin/stdout I/O exactly as a workflow invoking this CLI would —
 * rather than calling internal command functions directly in-process.
 */
export function runCli(
	args: string[],
	options: { env?: Record<string, string | undefined>; stdin?: string } = {}
): Promise<RunCliResult> {
	return new Promise((resolvePromise, reject) => {
		// Strip any debugger bootloader injected via NODE_OPTIONS (e.g. by an
		// attached IDE debugger) — it can hang a spawned child process.
		const env: Record<string, string | undefined> = { ...process.env };
		delete env.NODE_OPTIONS;
		Object.assign(env, options.env);

		const child = spawn(
			process.execPath,
			['--import', 'tsx', CLI_ENTRY, ...args],
			{ env }
		);

		let stdout = '';
		let stderr = '';
		child.stdout.on('data', (chunk) => (stdout += chunk.toString()));
		child.stderr.on('data', (chunk) => (stderr += chunk.toString()));

		child.on('error', reject);
		child.on('close', (exitCode) => {
			resolvePromise({ exitCode, stdout, stderr });
		});

		if (options.stdin !== undefined) {
			child.stdin.write(options.stdin);
		}
		child.stdin.end();
	});
}
