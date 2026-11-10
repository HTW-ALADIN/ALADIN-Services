import { writeJsonOutput } from '../io.js';

export function healthCommand(options: { output?: string } = {}): void {
	writeJsonOutput({ status: 'ok' }, options.output);
}
