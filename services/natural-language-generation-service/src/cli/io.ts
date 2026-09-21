import { readFile } from 'node:fs/promises';
import { stdin } from 'node:process';
import { ServiceError } from '../errors.js';

type InputStream = AsyncIterable<Buffer | string>;

async function readStdin(input: InputStream, maximum: number): Promise<Buffer> {
	const chunks: Buffer[] = [];
	let total = 0;
	for await (const chunk of input) {
		const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
		total += buffer.length;
		if (total > maximum) {
			throw new ServiceError(
				'payload-too-large',
				413,
				'Payload too large',
				`request exceeds ${maximum} bytes`
			);
		}
		chunks.push(buffer);
	}
	return Buffer.concat(chunks);
}

export async function readRequest(
	path: string,
	maximum: number,
	input: InputStream = stdin
): Promise<unknown> {
	let buffer: Buffer;
	try {
		buffer =
			path === '-' ? await readStdin(input, maximum) : await readFile(path);
	} catch (error) {
		if (error instanceof ServiceError) throw error;
		const message = error instanceof Error ? error.message : String(error);
		throw new ServiceError(
			'input-error',
			400,
			'Input error',
			`could not read request: ${message}`
		);
	}

	if (buffer.length > maximum) {
		throw new ServiceError(
			'payload-too-large',
			413,
			'Payload too large',
			`request exceeds ${maximum} bytes`
		);
	}
	try {
		return JSON.parse(buffer.toString('utf8')) as unknown;
	} catch {
		throw new ServiceError(
			'invalid-json',
			400,
			'Invalid JSON',
			'request is not valid JSON'
		);
	}
}
