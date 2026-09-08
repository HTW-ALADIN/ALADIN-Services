import { expect } from 'chai';
import { afterEach, describe, it } from 'node:test';
import { EventEmitter } from 'node:events';
import type { Worker } from 'node:worker_threads';
import {
	resetWorkerPool,
	runWorker,
	setWorkerIdleEvictionMs,
	workerPoolStats,
	type RunWorkerOptions,
	type WorkerTaskFactory,
} from '../src/worker-runner.js';

interface FakeWorker extends EventEmitter {
	postMessage: () => void;
	unref: () => void;
	terminate: () => Promise<number>;
	terminated: boolean;
}

function newFakeWorker(): FakeWorker {
	let terminated = false;
	const worker = Object.assign(new EventEmitter(), {
		postMessage: () => {},
		unref: () => {},
		terminate: async () => {
			terminated = true;
			return 0;
		},
	}) as FakeWorker;
	Object.defineProperty(worker, 'terminated', { get: () => terminated });
	return worker;
}

function succeed(worker: FakeWorker): void {
	worker.emit('message', { ok: true, text: 'hi', engineVersion: 'v' });
}

async function rejection(promise: Promise<unknown>): Promise<unknown> {
	try {
		await promise;
	} catch (error) {
		return error;
	}
	throw new Error('expected promise to reject');
}

function baseOptions(
	workerFactory: WorkerTaskFactory,
	overrides: Partial<RunWorkerOptions> = {}
): RunWorkerOptions {
	return {
		workerData: {},
		timeoutMs: 1000,
		timeoutDetail: 'exceeded',
		workerFactory,
		maxConcurrent: 4,
		failureTitle: 'Failed',
		busyDetail: 'busy',
		internalDetail: 'internal',
		reuseWorker: true,
		...overrides,
	};
}

describe('engine worker pool', () => {
	afterEach(() => {
		resetWorkerPool();
		setWorkerIdleEvictionMs(60_000);
	});

	it('reuses an idle worker for the same engine', async () => {
		const created: FakeWorker[] = [];
		const factory = (): Worker => {
			const worker = newFakeWorker();
			created.push(worker);
			return worker as unknown as Worker;
		};
		const options = baseOptions(factory);

		const first = runWorker(options);
		succeed(created[created.length - 1]!);
		await first;
		expect(workerPoolStats()).to.deep.equal({ live: 1, busy: 0, idle: 1 });

		const second = runWorker(options);
		succeed(created[created.length - 1]!);
		await second;
		expect(created).to.have.length(1);
		expect(workerPoolStats()).to.deep.equal({ live: 1, busy: 0, idle: 1 });
	});

	it('evicts an idle worker of the other engine before creating a new one', async () => {
		const createdB: FakeWorker[] = [];
		const factoryB = () => {
			const worker = newFakeWorker();
			createdB.push(worker);
			return worker as unknown as Worker;
		};
		const createdA: FakeWorker[] = [];
		const factoryA = () => {
			const worker = newFakeWorker();
			createdA.push(worker);
			return worker as unknown as Worker;
		};
		const capped = { maxConcurrent: 1 as number };

		const bFirst = runWorker(
			baseOptions(factoryB, { ...capped, reuseWorker: false })
		);
		succeed(createdB[createdB.length - 1]!);
		await bFirst;
		expect(workerPoolStats()).to.deep.equal({ live: 0, busy: 0, idle: 0 });

		const aWarm = runWorker(baseOptions(factoryA, capped));
		succeed(createdA[createdA.length - 1]!);
		await aWarm;
		expect(workerPoolStats()).to.deep.equal({ live: 1, busy: 0, idle: 1 });

		const bAgain = runWorker(baseOptions(factoryB, capped));
		succeed(createdB[createdB.length - 1]!);
		await bAgain;
		expect(createdA[0]!.terminated).to.equal(true);
		expect(workerPoolStats()).to.deep.equal({ live: 1, busy: 0, idle: 1 });
	});

	it('rejects with 429 when all engine capacity is busy', async () => {
		const created: FakeWorker[] = [];
		const factory = (): Worker => {
			const worker = newFakeWorker();
			created.push(worker);
			return worker as unknown as Worker;
		};
		const options = baseOptions(factory, { maxConcurrent: 1 });

		const first = runWorker(options);
		const second = await rejection(runWorker(options));
		expect(second).to.include({ code: 'server-busy', status: 429 });

		succeed(created[created.length - 1]!);
		await first;
	});

	it('evicts idle workers after the idle interval', async () => {
		setWorkerIdleEvictionMs(20);
		const created: FakeWorker[] = [];
		const factory = (): Worker => {
			const worker = newFakeWorker();
			created.push(worker);
			return worker as unknown as Worker;
		};

		const task = runWorker(baseOptions(factory));
		succeed(created[created.length - 1]!);
		await task;
		expect(workerPoolStats()).to.deep.equal({ live: 1, busy: 0, idle: 1 });

		await new Promise((resolve) => setTimeout(resolve, 80));
		expect(workerPoolStats()).to.deep.equal({ live: 0, busy: 0, idle: 0 });
		expect(created[0]!.terminated).to.equal(true);
	});

	it('keeps an error listener on idle workers so later faults cannot crash the process', async () => {
		const created: FakeWorker[] = [];
		const factory = (): Worker => {
			const worker = newFakeWorker();
			created.push(worker);
			return worker as unknown as Worker;
		};

		const task = runWorker(baseOptions(factory));
		succeed(created[created.length - 1]!);
		await task;
		expect(workerPoolStats()).to.deep.equal({ live: 1, busy: 0, idle: 1 });

		created[created.length - 1]!.emit('error', new Error('idle fault'));
		expect(workerPoolStats()).to.deep.equal({ live: 0, busy: 0, idle: 0 });
	});

	it('does not pool workers that opt out of reuse', async () => {
		const created: FakeWorker[] = [];
		const factory = (): Worker => {
			const worker = newFakeWorker();
			created.push(worker);
			return worker as unknown as Worker;
		};

		const task = runWorker(baseOptions(factory, { reuseWorker: false }));
		succeed(created[created.length - 1]!);
		await task;
		expect(workerPoolStats()).to.deep.equal({ live: 0, busy: 0, idle: 0 });
		expect(created[0]!.terminated).to.equal(true);
	});

	it('ignores a worker message that arrives after the task has settled', async () => {
		const created: FakeWorker[] = [];
		const factory = (): Worker => {
			const worker = newFakeWorker();
			created.push(worker);
			return worker as unknown as Worker;
		};

		const task = runWorker(
			baseOptions(factory, { timeoutMs: 30, reuseWorker: false })
		);
		const error = await rejection(task);
		expect(error).to.have.property('code', 'resource-limit');

		created[created.length - 1]!.emit('message', {
			ok: true,
			text: 'late',
			engineVersion: 'v',
		});
		expect(workerPoolStats()).to.deep.equal({ live: 0, busy: 0, idle: 0 });
	});

	it('does not re-pool a worker that was reset while its task was in flight', async () => {
		const created: FakeWorker[] = [];
		const factory = (): Worker => {
			const worker = newFakeWorker();
			created.push(worker);
			return worker as unknown as Worker;
		};

		const task = runWorker(baseOptions(factory));
		resetWorkerPool();
		created[created.length - 1]!.emit('message', {
			ok: true,
			text: 'late',
			engineVersion: 'v',
		});
		await task;
		expect(workerPoolStats()).to.deep.equal({ live: 0, busy: 0, idle: 0 });
	});

	it('does not evict warm idle workers for transient tasks', async () => {
		const createdA: FakeWorker[] = [];
		const factoryA = (): Worker => {
			const worker = newFakeWorker();
			createdA.push(worker);
			return worker as unknown as Worker;
		};
		const createdB: FakeWorker[] = [];
		const factoryB = (): Worker => {
			const worker = newFakeWorker();
			createdB.push(worker);
			return worker as unknown as Worker;
		};
		const capped = { maxConcurrent: 1 as number };

		const aWarm = runWorker(baseOptions(factoryA, capped));
		succeed(createdA[createdA.length - 1]!);
		await aWarm;
		expect(workerPoolStats()).to.deep.equal({ live: 1, busy: 0, idle: 1 });

		const bTask = runWorker(
			baseOptions(factoryB, { ...capped, reuseWorker: false })
		);
		succeed(createdB[createdB.length - 1]!);
		await bTask;
		expect(createdA[0]!.terminated).to.equal(false);
		expect(workerPoolStats()).to.deep.equal({ live: 1, busy: 0, idle: 1 });
	});
});
