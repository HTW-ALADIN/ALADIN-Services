import { createRequire } from 'node:module';
import { Worker } from 'node:worker_threads';
import type { ServiceLimits } from './config.js';
import { ServiceError } from './errors.js';
import type {
	TemplateGenerationRequest,
	TemplateGenerationResponse,
} from './schemas.js';

const RESERVED_DATA_KEYS = new Set([
	'__proto__',
	'basedir',
	'cache',
	'compileDebug',
	'constructor',
	'filename',
	'forceRandomSeed',
	'fs',
	'globals',
	'hasOwnProperty',
	'language',
	'plugins',
	'prototype',
	'staticFs',
	'util',
]);

const FILE_DIRECTIVE = /^\s*(?:include|extends)\b/m;
const require = createRequire(import.meta.url);
const rosaePackage = require('rosaenlg/package.json') as { version: string };

export interface TemplateWorkerPayload {
	template: string;
	data: TemplateGenerationRequest['input']['data'];
	language: TemplateGenerationRequest['language'];
	seed: number;
}

interface TemplateWorkerSuccess {
	ok: true;
	text: string;
	engineVersion: string;
}

interface TemplateWorkerFailure {
	ok: false;
	detail: string;
}

type TemplateWorkerMessage = TemplateWorkerSuccess | TemplateWorkerFailure;
export type TemplateWorkerFactory = (payload: TemplateWorkerPayload) => Worker;

function createTemplateWorker(payload: TemplateWorkerPayload): Worker {
	const sourceMode = import.meta.url.endsWith('.ts');
	/* c8 ignore next -- the compiled path is exercised by the Docker smoke test. */
	const workerName = sourceMode ? 'template-worker.ts' : 'template-worker.js';
	return new Worker(new URL(workerName, import.meta.url), {
		workerData: payload,
		/* c8 ignore next -- tsx is needed only when executing TypeScript directly. */
		execArgv: sourceMode ? ['--import', 'tsx'] : [],
		resourceLimits: { maxOldGenerationSizeMb: 512 },
	});
}

function internalWorkerError(): ServiceError {
	return new ServiceError(
		'internal-error',
		500,
		'Internal server error',
		'template worker failed'
	);
}

export async function runTemplateWorker(
	payload: TemplateWorkerPayload,
	timeoutMs: number,
	workerFactory: TemplateWorkerFactory = createTemplateWorker
): Promise<TemplateWorkerSuccess> {
	return new Promise<TemplateWorkerSuccess>((resolve, reject) => {
		let worker: Worker;
		try {
			worker = workerFactory(payload);
		} catch {
			reject(internalWorkerError());
			return;
		}

		let settled = false;
		function finish(action: () => void, terminateWorker: boolean): void {
			if (settled) return;
			settled = true;
			clearTimeout(timer);
			if (terminateWorker) {
				void worker.terminate().then(action, action);
				return;
			}
			action();
		}

		const timer = setTimeout(() => {
			finish(
				() =>
					reject(
						new ServiceError(
							'resource-limit',
							422,
							'Resource limit exceeded',
							`template generation exceeded ${timeoutMs} ms`
						)
					),
				true
			);
		}, timeoutMs);

		worker.once('message', (message: TemplateWorkerMessage) => {
			finish(() => {
				if (message.ok) resolve(message);
				else {
					reject(
						new ServiceError(
							'realisation-error',
							422,
							'Template generation failed',
							message.detail
						)
					);
				}
			}, true);
		});
		worker.once('error', () => {
			finish(() => reject(internalWorkerError()), false);
		});
		worker.once('exit', () => {
			finish(() => reject(internalWorkerError()), false);
		});
	});
}

export async function realizeTemplate(
	request: TemplateGenerationRequest,
	limits: ServiceLimits
): Promise<TemplateGenerationResponse> {
	if (FILE_DIRECTIVE.test(request.input.template)) {
		throw new ServiceError(
			'invalid-request',
			400,
			'Invalid request',
			'inline templates cannot include or extend files'
		);
	}
	for (const key of Object.keys(request.input.data)) {
		if (RESERVED_DATA_KEYS.has(key)) {
			throw new ServiceError(
				'invalid-request',
				400,
				'Invalid request',
				`template data key is reserved: ${key}`
			);
		}
	}

	const seed = request.input.seed ?? 0;
	const result = await runTemplateWorker(
		{
			template: request.input.template,
			data: request.input.data,
			language: request.language,
			seed,
		},
		limits.templateTimeoutMs
	);
	if (Buffer.byteLength(result.text, 'utf8') > limits.maxOutputBytes) {
		throw new ServiceError(
			'resource-limit',
			422,
			'Resource limit exceeded',
			`generated output exceeds ${limits.maxOutputBytes} bytes`
		);
	}
	return {
		text: result.text,
		mode: request.mode,
		backend: request.backend,
		language: request.language,
		metadata: {
			engineVersion: result.engineVersion,
			seed,
		},
	};
}

export function rosaeNlgVersion(): string {
	return rosaePackage.version;
}
