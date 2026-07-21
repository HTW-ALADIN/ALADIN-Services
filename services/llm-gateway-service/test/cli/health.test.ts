import { expect } from 'chai';
import { readFileSync, mkdtempSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { healthCommand } from '../../src/cli/commands/health.js';

describe('healthCommand', () => {
	it('writes the health status to an output file', () => {
		const dir = mkdtempSync(join(tmpdir(), 'llm-gateway-cli-test-'));
		const outputPath = join(dir, 'health.json');

		healthCommand({ output: outputPath });

		expect(JSON.parse(readFileSync(outputPath, 'utf-8'))).to.deep.equal({
			status: 'ok',
		});
	});
});
