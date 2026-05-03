import dotenv from 'dotenv';
dotenv.config();

import { createControllers } from '../bootstrap';
import { CLIRoute, extractRoutes, invokeHandler } from './express-cli-adapter';
import * as fs from 'fs';
import * as path from 'path';

// ---------------------------------------------------------------------------
// Route table builder
// ---------------------------------------------------------------------------

/**
 * Build the full route table by walking every controller's Express Router.
 * The mount prefixes mirror those in rest-api.ts registerControllers().
 */
function buildRouteTable(initSqlFile?: string): CLIRoute[] {
	const c = createControllers({ pgliteInitSqlFile: initSqlFile });
	return [
		...extractRoutes(c.connectionController.router, '/api/database'),
		...extractRoutes(c.taskGenerationController.router, '/api/generation'),
		...extractRoutes(c.gradingController.router, '/api/grading'),
		...extractRoutes(c.descriptionController.router, '/api/description'),
		...extractRoutes(c.queryExecutionController.router, '/api/query'),
	];
}

function printHelp(routes: CLIRoute[]) {
	const lines = [
		'SQL Assessment Service CLI',
		'',
		'Usage: sql-assess <command> [options]',
		'',
		'Options:',
		'  -f, --file <path>              Read JSON body from file',
		'  --stdin                        Read JSON body from stdin',
		'  --list                         List all commands',
		'  --init-sql-file <path>         SQL file used to initialise a PGlite database',
		'                                 when sqlContent is not in the request body.',
		'                                 Overrides the PGLITE_INIT_SQL_FILE env var.',
		'  -h, --help                     Show help',
		'',
		'Commands:',
		...routes.map((r) => `  ${r.command.padEnd(40)} ${r.method} ${r.path}`),
		'',
		'Body can also be provided as a positional JSON string argument,',
		'or piped via stdin (auto-detected when not a TTY).',
	];
	console.log(lines.join('\n'));
}

async function readStdin(): Promise<string> {
	return new Promise((resolve, reject) => {
		let data = '';
		process.stdin.setEncoding('utf-8');
		process.stdin.on('data', (chunk) => (data += chunk));
		process.stdin.on('end', () => resolve(data));
		process.stdin.on('error', reject);
	});
}

/**
 * Returns the index of the -f / --file flag in args, giving -f priority over
 * --file when both are present.  Returns -1 when neither flag is present.
 */
export function resolveFileFlag(args: string[]): number {
	const shortIdx = args.indexOf('-f');
	if (shortIdx !== -1) return shortIdx;
	return args.indexOf('--file');
}

/**
 * Resolves the --init-sql-file flag value from the raw CLI args.
 * Throws if the flag is present but not followed by a non-flag argument,
 * so the caller can surface a clear error instead of silently ignoring it.
 */
export function resolveInitSqlFile(args: string[]): string | undefined {
	const idx = args.indexOf('--init-sql-file');
	if (idx === -1) return undefined;
	const value = args[idx + 1];
	if (!value || value.startsWith('-')) {
		throw new Error('--init-sql-file requires a path argument.');
	}
	return path.resolve(value);
}

/** Flags that consume the following token as their value. */
const FLAGS_WITH_VALUES = new Set(['--init-sql-file', '-f', '--file']);

/**
 * Scans args (from index 1, after the command) and returns the first token
 * that is neither a flag nor the value of a flag that takes a value.
 * Returns undefined when no such positional argument exists.
 */
export function resolvePositionalBody(args: string[]): string | undefined {
	let i = 1; // skip args[0] (the command)
	while (i < args.length) {
		const arg = args[i];
		if (FLAGS_WITH_VALUES.has(arg)) {
			i += 2; // skip flag + its value
		} else if (arg.startsWith('-')) {
			i += 1; // skip boolean flag
		} else {
			return arg;
		}
	}
	return undefined;
}

async function main() {
	const args = process.argv.slice(2);

	// ── Resolve --init-sql-file early so it feeds buildRouteTable ────────────
	let initSqlFile: string | undefined;
	try {
		initSqlFile = resolveInitSqlFile(args);
	} catch (e) {
		console.error((e as Error).message);
		process.exit(1);
	}

	if (
		args.includes('--list') ||
		args.includes('--help') ||
		args.includes('-h') ||
		args.length === 0
	) {
		const routes = buildRouteTable(initSqlFile);
		if (args.includes('--list')) {
			for (const r of routes)
				console.log(`${r.command}\t${r.method}\t${r.path}`);
		} else {
			printHelp(routes);
		}
		return;
	}

	const command = args[0];
	const routes = buildRouteTable(initSqlFile);
	const route = routes.find((r) => r.command === command);

	if (!route) {
		console.error(`Unknown command: ${command}`);
		console.error('Run with --list to see available commands.');
		process.exit(1);
	}

	// ── Resolve request body ─────────────────────────────────────────────
	let body: unknown;
	const fileIdx = resolveFileFlag(args);

	if (args.includes('--stdin')) {
		body = JSON.parse(await readStdin());
	} else if (fileIdx !== -1) {
		const filePath = args[fileIdx + 1];
		if (!filePath || filePath.startsWith('-')) {
			console.error('-f/--file requires a path argument.');
			process.exit(1);
		}
		body = JSON.parse(fs.readFileSync(path.resolve(filePath), 'utf-8'));
	} else {
		const positional = resolvePositionalBody(args);
		if (positional !== undefined) {
			body = JSON.parse(positional);
		} else if (!process.stdin.isTTY) {
			body = JSON.parse(await readStdin());
		} else {
			console.error(
				'No input provided. Use -f <file>, --stdin, or pass JSON as an argument.',
			);
			process.exit(1);
		}
	}

	const result = await invokeHandler(route.handler, body);
	console.log(JSON.stringify(result.data, null, 2));
	process.exit(result.statusCode >= 400 ? 1 : 0);
}

main().catch((err) => {
	console.error(err.message ?? err);
	process.exit(1);
});
