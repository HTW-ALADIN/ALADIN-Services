import { parentPort } from 'node:worker_threads';
import jsRealB from 'jsrealb';
import { postFailure, postOutput } from './worker-message.js';

export interface SurfaceWorkerPayload {
	structure: unknown;
	language: 'en' | 'fr';
	maxOutputBytes: number;
}

const port = parentPort!;

jsRealB.setExceptionOnWarning(true);

port.on('message', (payload: SurfaceWorkerPayload) => {
	try {
		const structure = payload.structure as Record<string, unknown> & {
			lang?: string;
		};
		structure.lang = payload.language;
		const constituent = jsRealB.fromJSON(structure, payload.language);
		if (constituent === undefined) {
			throw new Error('jsRealB did not create a realisable structure');
		}
		const text = constituent.realize().trimEnd();
		postOutput(
			port,
			'realised',
			text,
			payload.maxOutputBytes,
			jsRealB.jsRealB_version
		);
	} catch (error) {
		postFailure(port, error);
	}
});
