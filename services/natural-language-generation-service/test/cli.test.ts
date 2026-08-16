import { expect } from 'chai';
import { describe, it } from 'node:test';
import { rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { runCli } from '../src/cli/program.js';
import { englishRequest, templateRequest, throwUnknown } from './fixtures.js';

function capture() {
	let stdout = '';
	let stderr = '';
	return {
		streams: {
			stdout: { write: (value: string) => ((stdout += value), true) },
			stderr: { write: (value: string) => ((stderr += value), true) },
		},
		stdout: () => stdout,
		stderr: () => stderr,
	};
}

describe('CLI', () => {
	it('mirrors the generation request and supports JSON output', async (context) => {
		const path = join(tmpdir(), `nlg-request-${process.pid}.json`);
		context.after(() => rm(path, { force: true }));
		await writeFile(path, JSON.stringify(englishRequest()), 'utf8');

		const text = capture();
		expect(
			await runCli(['generate', '--request', path], { streams: text.streams })
		).to.equal(0);
		expect(text.stdout()).to.equal('The cat chases the mouse.\n');

		const json = capture();
		expect(
			await runCli(['generate', '--request', path, '--json'], {
				streams: json.streams,
			})
		).to.equal(0);
		expect(JSON.parse(json.stdout()).text).to.equal(
			'The cat chases the mouse.'
		);

		await writeFile(path, JSON.stringify(templateRequest()), 'utf8');
		const template = capture();
		expect(
			await runCli(['generate', '--request', path], {
				streams: template.streams,
			})
		).to.equal(0);
		expect(template.stdout()).to.equal('<p>Hello Alice!</p>\n');
	});

	it('writes structured validation and input errors to stderr', async (context) => {
		const path = join(tmpdir(), `nlg-invalid-${process.pid}.json`);
		context.after(() => rm(path, { force: true }));
		await writeFile(path, '{broken', 'utf8');
		const malformed = capture();
		expect(
			await runCli(['generate', '--request', path], {
				streams: malformed.streams,
			})
		).to.equal(1);
		expect(JSON.parse(malformed.stderr()).code).to.equal('invalid-json');

		const missing = capture();
		expect(
			await runCli(['generate', '--request', `${path}-missing`], {
				streams: missing.streams,
			})
		).to.equal(1);
		expect(JSON.parse(missing.stderr()).code).to.equal('input-error');
	});

	it('returns a non-zero code for usage errors', async () => {
		const output = capture();
		expect(await runCli(['generate'], { streams: output.streams })).to.equal(1);
		expect(output.stderr()).to.contain('required option');
	});

	it('uses the process streams when no streams are supplied', async (context) => {
		const stderr = context.mock.method(process.stderr, 'write', () => true);
		expect(await runCli(['generate'])).to.equal(1);
		expect(stderr.mock.callCount()).to.be.greaterThan(0);
	});

	it('normalises unexpected command failures', async (context) => {
		const path = join(tmpdir(), `nlg-internal-${process.pid}.json`);
		context.after(() => rm(path, { force: true }));
		await writeFile(path, JSON.stringify(englishRequest()), 'utf8');
		for (const failure of [new Error('write failed'), 'write failed']) {
			let stderr = '';
			const exitCode = await runCli(['generate', '--request', path], {
				streams: {
					stdout: {
						write: () => throwUnknown(failure),
					},
					stderr: { write: (value: string) => ((stderr += value), true) },
				},
			});
			expect(exitCode).to.equal(1);
			expect(JSON.parse(stderr)).to.include({
				code: 'internal-error',
				detail: 'write failed',
			});
		}
	});
});
