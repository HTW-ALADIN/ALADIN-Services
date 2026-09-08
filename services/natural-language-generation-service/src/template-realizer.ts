import { createRequire } from 'node:module';
import type { Worker } from 'node:worker_threads';
import type { ServiceLimits } from './config.js';
import { ServiceError } from './errors.js';
import type {
	TemplateGenerationRequest,
	TemplateGenerationResponse,
} from './schemas.js';
import {
	createEngineWorker,
	runWorker,
	type RunnerSuccess,
} from './worker-runner.js';

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
	maxOutputBytes: number;
}

export type TemplateWorkerFactory = () => Worker;

export function createTemplateWorker(): Worker {
	return createEngineWorker('template-worker');
}

export async function runTemplateWorker(
	payload: TemplateWorkerPayload,
	timeoutMs: number,
	workerFactory: TemplateWorkerFactory,
	maxConcurrent = Number.POSITIVE_INFINITY
): Promise<RunnerSuccess> {
	return runWorker({
		workerData: payload,
		timeoutMs,
		timeoutDetail: `template generation exceeded ${timeoutMs} ms`,
		workerFactory,
		maxConcurrent,
		failureTitle: 'Template generation failed',
		busyDetail:
			'the server is already processing the maximum number of concurrent generations',
		internalDetail: 'template worker failed',
		reuseWorker: false,
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
			maxOutputBytes: limits.maxOutputBytes,
		},
		limits.templateTimeoutMs,
		createTemplateWorker,
		limits.maxConcurrentWorkers
	);
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
