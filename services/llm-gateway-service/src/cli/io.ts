import { readFileSync, writeFileSync } from 'fs';

/**
 * Reads a JSON payload from a file path, or from stdin when the path is "-"
 * or omitted. This is the primary input mechanism for the CLI, since the
 * service is mainly invoked from automated workflows.
 */
export function readJsonInput(path: string | undefined): unknown {
	const raw = readRawInput(path);
	try {
		return JSON.parse(raw);
	} catch (err) {
		const message = err instanceof Error ? err.message : String(err);
		throw new Error(`Failed to parse JSON input: ${message}`);
	}
}

function readRawInput(path: string | undefined): string {
	if (!path || path === '-') {
		return readStdin();
	}
	return readFileSync(path, 'utf-8');
}

function readStdin(): string {
	try {
		return readFileSync(0, 'utf-8');
	} catch {
		throw new Error(
			'No input file given and stdin is empty. Pass a JSON file path or pipe JSON via stdin.'
		);
	}
}

export function writeJsonOutput(
	payload: unknown,
	outputPath: string | undefined
): void {
	const serialized = JSON.stringify(payload, null, 2);
	if (!outputPath) {
		process.stdout.write(serialized + '\n');
		return;
	}
	writeFileSync(outputPath, serialized + '\n');
}
