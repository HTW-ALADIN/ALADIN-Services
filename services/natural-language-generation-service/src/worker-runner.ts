import { Worker } from 'node:worker_threads';
import { ServiceError } from './errors.js';

export interface RunnerSuccess {
	ok: true;
	text: string;
	engineVersion: string;
}

export interface RunnerFailure {
	ok: false;
	detail: string;
	code?: 'resource-limit';
}

export type RunnerMessage = RunnerSuccess | RunnerFailure;
export type WorkerTaskFactory = () => Worker;

export interface RunWorkerOptions {
	workerData: unknown;
	timeoutMs: number;
	timeoutDetail: string;
	workerFactory: WorkerTaskFactory;
	maxConcurrent: number;
	failureTitle: string;
	busyDetail: string;
	internalDetail: string;
	reuseWorker: boolean;
}

const idleWorkers = new Map<WorkerTaskFactory, Set<Worker>>();
const busyWorkers = new Set<Worker>();
const liveWorkers = new Set<Worker>();
const idleTimers = new Map<Worker, ReturnType<typeof setTimeout>>();
const factoryOf = new Map<Worker, WorkerTaskFactory>();
let idleEvictionMs = 60_000;

export function createEngineWorker(
	workerName: 'surface-worker' | 'template-worker'
): Worker {
	const sourceMode = import.meta.url.endsWith('.ts');
	/* c8 ignore next -- the compiled path is exercised by the Docker smoke test. */
	const resolved = sourceMode ? `${workerName}.ts` : `${workerName}.js`;
	return new Worker(new URL(resolved, import.meta.url), {
		/* c8 ignore next -- tsx is needed only when executing TypeScript directly. */
		execArgv: sourceMode ? ['--import', 'tsx'] : [],
		resourceLimits: { maxOldGenerationSizeMb: 512 },
	});
}

function idleSetFor(factory: WorkerTaskFactory): Set<Worker> {
	let idle = idleWorkers.get(factory);
	if (idle === undefined) {
		idle = new Set<Worker>();
		idleWorkers.set(factory, idle);
	}
	return idle;
}

function removeWorker(worker: Worker): void {
	busyWorkers.delete(worker);
	liveWorkers.delete(worker);
	const timer = idleTimers.get(worker);
	if (timer !== undefined) {
		clearTimeout(timer);
		idleTimers.delete(worker);
	}
	const factory = factoryOf.get(worker);
	factoryOf.delete(worker);
	const idle = factory === undefined ? undefined : idleWorkers.get(factory);
	if (idle !== undefined) idle.delete(worker);
}

function evictWorker(worker: Worker): void {
	removeWorker(worker);
	void worker.terminate().catch(ignoreRejection);
}

function evictOneIdleWorker(): void {
	for (const idle of idleWorkers.values()) {
		if (idle.size > 0) {
			evictWorker(idle.values().next().value as Worker);
			return;
		}
	}
}

function addIdleWorker(worker: Worker): void {
	const idle = idleSetFor(factoryOf.get(worker)!);
	idle.add(worker);
	const timer = setTimeout(() => evictWorker(worker), idleEvictionMs);
	timer.unref();
	idleTimers.set(worker, timer);
}

function acquireWorker(options: RunWorkerOptions): Worker {
	const idle = idleSetFor(options.workerFactory);
	if (idle.size > 0) {
		const worker = idle.values().next().value as Worker;
		idle.delete(worker);
		clearTimeout(idleTimers.get(worker)!);
		idleTimers.delete(worker);
		busyWorkers.add(worker);
		return worker;
	}
	if (busyWorkers.size >= options.maxConcurrent) {
		throw new ServiceError(
			'server-busy',
			429,
			'Server busy',
			options.busyDetail
		);
	}
	if (options.reuseWorker && liveWorkers.size >= options.maxConcurrent) {
		evictOneIdleWorker();
	}
	let worker: Worker;
	try {
		worker = options.workerFactory();
	} catch {
		throw new ServiceError(
			'internal-error',
			500,
			'Internal server error',
			options.internalDetail
		);
	}
	factoryOf.set(worker, options.workerFactory);
	busyWorkers.add(worker);
	liveWorkers.add(worker);
	worker.unref();
	worker.on('error', () => evictWorker(worker));
	worker.on('exit', () => removeWorker(worker));
	return worker;
}

function ignoreRejection(): void {}

export function setWorkerIdleEvictionMs(ms: number): void {
	idleEvictionMs = ms;
}

export function workerPoolStats(): {
	live: number;
	busy: number;
	idle: number;
} {
	let idle = 0;
	for (const set of idleWorkers.values()) idle += set.size;
	return { live: liveWorkers.size, busy: busyWorkers.size, idle };
}

export function resetWorkerPool(): void {
	for (const worker of [...liveWorkers]) {
		void worker.terminate().catch(ignoreRejection);
	}
	for (const timer of idleTimers.values()) clearTimeout(timer);
	busyWorkers.clear();
	liveWorkers.clear();
	idleWorkers.clear();
	idleTimers.clear();
	factoryOf.clear();
}

export async function runWorker(
	options: RunWorkerOptions
): Promise<RunnerSuccess> {
	const worker = acquireWorker(options);

	return new Promise<RunnerSuccess>((resolve, reject) => {
		let settled = false;
		function finish(action: () => void, reuse: boolean): void {
			if (settled) return;
			settled = true;
			clearTimeout(timer);
			worker.off('error', onError);
			worker.off('exit', onExit);
			busyWorkers.delete(worker);
			if (reuse && liveWorkers.has(worker)) addIdleWorker(worker);
			else evictWorker(worker);
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
							options.timeoutDetail
						)
					),
				false
			);
		}, options.timeoutMs);

		const onMessage = (message: RunnerMessage) => {
			finish(() => {
				if (message.ok) resolve(message);
				else if (message.code === 'resource-limit') {
					reject(
						new ServiceError(
							'resource-limit',
							422,
							'Resource limit exceeded',
							message.detail
						)
					);
				} else {
					reject(
						new ServiceError(
							'realisation-error',
							422,
							options.failureTitle,
							message.detail
						)
					);
				}
			}, options.reuseWorker);
		};
		const onError = () => {
			finish(() => reject(internalError(options.internalDetail)), false);
		};
		const onExit = () => {
			finish(() => reject(internalError(options.internalDetail)), false);
		};

		worker.once('message', onMessage);
		worker.once('error', onError);
		worker.once('exit', onExit);
		worker.postMessage(options.workerData);
	});
}

function internalError(detail: string): ServiceError {
	return new ServiceError(
		'internal-error',
		500,
		'Internal server error',
		detail
	);
}
