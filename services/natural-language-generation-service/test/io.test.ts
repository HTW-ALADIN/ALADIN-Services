import { expect } from 'chai';
import { rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, it } from 'node:test';
import { readRequest } from '../src/cli/io.js';
import { ServiceError } from '../src/errors.js';
import { throwUnknown } from './fixtures.js';

async function* chunks(...values: Array<Buffer | string>) {
	for (const value of values) yield value;
}

describe('CLI input', () => {
	it('reads JSON from stdin in string and buffer chunks', async () => {
		const result = await readRequest(
			'-',
			100,
			chunks('{"language":', Buffer.from('"en"}'))
		);
		expect(result).to.deep.equal({ language: 'en' });
	});

	it('stops reading stdin once the body limit is exceeded', async () => {
		try {
			await readRequest('-', 4, chunks('123', '45'));
			expect.fail('expected readRequest to reject');
		} catch (error) {
			expect(error)
				.to.be.instanceOf(ServiceError)
				.and.have.property('code', 'payload-too-large');
		}
	});

	it('rejects an oversized request file', async (context) => {
		const path = join(tmpdir(), `nlg-oversized-${process.pid}.json`);
		context.after(() => rm(path, { force: true }));
		await writeFile(path, '{"too":"large"}', 'utf8');
		try {
			await readRequest(path, 4);
			expect.fail('expected readRequest to reject');
		} catch (error) {
			expect(error)
				.to.be.instanceOf(ServiceError)
				.and.have.property('code', 'payload-too-large');
		}
	});

	it('normalises non-Error input failures', async () => {
		const failedInput: AsyncIterable<string> = {
			[Symbol.asyncIterator]: () => throwUnknown('stream failed'),
		};
		try {
			await readRequest('-', 100, failedInput);
			expect.fail('expected readRequest to reject');
		} catch (error) {
			expect(error)
				.to.be.instanceOf(ServiceError)
				.and.have.property('message', 'could not read request: stream failed');
		}
	});
});
