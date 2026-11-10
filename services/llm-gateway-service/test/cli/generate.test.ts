import { expect } from 'chai';
import { writeFileSync, readFileSync, mkdtempSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { generateCommand } from '../../src/cli/commands/generate.js';
import type { GatewayClient } from '../../src/core/gateway-client.js';
import type { GenerateRequest } from '../../src/core/types.js';

class FakeGatewayClient {
	async generate(request: GenerateRequest) {
		return {
			text: `you said: ${request.messages[0]?.content}`,
			finishReason: 'stop' as const,
			usage: { totalTokens: 5 },
			provider: request.provider,
			model: request.model,
		};
	}
}

describe('generateCommand', () => {
	let dir: string;

	beforeEach(() => {
		dir = mkdtempSync(join(tmpdir(), 'llm-gateway-cli-test-'));
	});

	it('reads a request file and writes the response to an output file', async () => {
		const inputPath = join(dir, 'request.json');
		const outputPath = join(dir, 'response.json');
		writeFileSync(
			inputPath,
			JSON.stringify({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [{ type: 'text', text: 'hi there' }],
					},
				],
			})
		);

		await generateCommand(
			inputPath,
			{ output: outputPath },
			new FakeGatewayClient() as unknown as GatewayClient
		);

		const output = JSON.parse(readFileSync(outputPath, 'utf-8'));
		expect(output.text).to.equal('you said: hi there');
		expect(output.provider).to.equal('openai');
	});

	it('throws a helpful error for malformed JSON input', async () => {
		const inputPath = join(dir, 'bad.json');
		writeFileSync(inputPath, '{not valid json');

		try {
			await generateCommand(
				inputPath,
				{},
				new FakeGatewayClient() as unknown as GatewayClient
			);
			expect.fail('expected generateCommand to throw');
		} catch (err) {
			expect((err as Error).message).to.match(/Failed to parse JSON input/);
		}
	});
});
