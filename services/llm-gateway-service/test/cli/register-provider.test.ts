import { expect } from 'chai';
import { readFileSync, mkdtempSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { registerProviderCommand } from '../../src/cli/commands/register-provider.js';
import type { ProviderRegistry } from '../../src/core/provider-registry.js';

class FakeRegistry {
	async register(input: { name: string; baseUrl: string; apiKey: string }) {
		return {
			registered: true,
			mode: 'gateway-admin-api' as const,
			message: `registered ${input.name}`,
		};
	}
}

describe('registerProviderCommand', () => {
	it('writes the registration result to the output file', async () => {
		const dir = mkdtempSync(join(tmpdir(), 'llm-gateway-cli-test-'));
		const outputPath = join(dir, 'result.json');

		await registerProviderCommand(
			{
				name: 'mycompany',
				baseUrl: 'https://api.mycompany.com',
				apiKey: 'sk-xxx',
				output: outputPath,
			},
			new FakeRegistry() as unknown as ProviderRegistry
		);

		const output = JSON.parse(readFileSync(outputPath, 'utf-8'));
		expect(output).to.deep.equal({
			registered: true,
			mode: 'gateway-admin-api',
			message: 'registered mycompany',
		});
	});
});
