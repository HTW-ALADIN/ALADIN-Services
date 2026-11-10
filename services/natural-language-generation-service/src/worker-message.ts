import type { MessagePort } from 'node:worker_threads';

export function postOutput(
	port: MessagePort,
	kind: 'generated' | 'realised',
	text: string,
	maxOutputBytes: number,
	engineVersion: string
): void {
	if (Buffer.byteLength(text, 'utf8') > maxOutputBytes) {
		port.postMessage({
			ok: false,
			code: 'resource-limit',
			detail: `${kind} output exceeds ${maxOutputBytes} bytes`,
		});
	} else {
		port.postMessage({
			ok: true,
			text,
			engineVersion,
		});
	}
}

export function postFailure(port: MessagePort, error: unknown): void {
	port.postMessage({
		ok: false,
		detail: error instanceof Error ? error.message : String(error),
	});
}
