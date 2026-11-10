import { parentPort } from 'node:worker_threads';
import rosaeNlg from 'rosaenlg';
import type { TemplateWorkerPayload } from './template-realizer.js';
import { postFailure, postOutput } from './worker-message.js';

const port = parentPort!;

port.on('message', (payload: TemplateWorkerPayload) => {
	try {
		const text = rosaeNlg.render(payload.template, {
			...payload.data,
			language: payload.language,
			forceRandomSeed: payload.seed,
			compileDebug: false,
			cache: false,
		});
		postOutput(
			port,
			'generated',
			text,
			payload.maxOutputBytes,
			rosaeNlg.getRosaeNlgVersion()
		);
	} catch (error) {
		postFailure(port, error);
	}
});
