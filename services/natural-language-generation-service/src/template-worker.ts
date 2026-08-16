import { parentPort, workerData } from 'node:worker_threads';
import rosaeNlg from 'rosaenlg';
import type { TemplateWorkerPayload } from './template-realizer.js';

const payload = workerData as TemplateWorkerPayload;

try {
	const text = rosaeNlg.render(payload.template, {
		...payload.data,
		language: payload.language,
		forceRandomSeed: payload.seed,
		compileDebug: false,
		cache: false,
	});
	parentPort!.postMessage({
		ok: true,
		text,
		engineVersion: rosaeNlg.getRosaeNlgVersion(),
	});
} catch (error) {
	parentPort!.postMessage({
		ok: false,
		detail: error instanceof Error ? error.message : String(error),
	});
}
