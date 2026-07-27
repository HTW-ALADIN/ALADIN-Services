import { expect } from 'chai';
import { GatewayClient } from '../../src/core/gateway-client.js';
import { GatewayRequestError } from '../../src/core/types.js';
import { loadEnvFile } from '../support/load-env.js';

/**
 * Integration test against a *real* custom OpenAI-compatible provider,
 * configured via a local, gitignored `.env` file (see `.example.env` for the
 * expected key names: `API_KEY`, `BASE_ENDPOINT`).
 *
 * This exercises the `customProvider` bypass path in `GatewayClient` (see
 * `core/gateway-client.ts`) against the real endpoint, rather than a mock
 * server. It is skipped automatically when `.env` is absent or incomplete
 * (e.g. in CI), so `npm test` stays hermetic. Run explicitly via
 * `npm run test:integration:real`.
 */
describe('GatewayClient: real custom provider', () => {
	const MODEL = 'qwen3.5-122b-a10b_ma';

	let apiKey: string | undefined;
	let baseEndpoint: string | undefined;
	let client: GatewayClient;

	before(function () {
		const env = loadEnvFile();
		apiKey = env.API_KEY;
		baseEndpoint = env.BASE_ENDPOINT;

		if (!apiKey || !baseEndpoint) {
			this.skip();
		}

		// Dummy gateway config: unused by the customProvider bypass path, but
		// required to construct the client.
		client = new GatewayClient({
			baseUrl: 'http://localhost:0/v1',
			apiKey: '',
			timeoutMs: 60000,
		});
	});

	it('generates a response from the real provider', async function () {
		this.timeout(60000);

		const result = await client.generate({
			provider: 'real-provider',
			model: MODEL,
			messages: [{ role: 'user', content: 'What is 2 + 2? Reply with only the number.' }],
			customProvider: { baseUrl: baseEndpoint!, apiKey: apiKey! },
		});

		expect(result.text).to.be.a('string');
		expect(result.text.trim().length).to.be.greaterThan(0);
		expect([
			'stop',
			'length',
			'content-filter',
			'tool-calls',
			'error',
			'other',
			'unknown',
		]).to.include(result.finishReason);
		expect(result.viaGatewayBypass).to.equal(true);
		expect(result.provider).to.equal('real-provider');
		expect(result.model).to.equal(MODEL);
		expect(result.usage.inputTokens).to.be.a('number');
		expect(result.usage.outputTokens).to.be.a('number');
	});

	it('handles a multi-turn conversation with a system prompt', async function () {
		this.timeout(60000);

		const result = await client.generate({
			provider: 'real-provider',
			model: MODEL,
			system: 'You are a concise assistant. Only answer with the final number.',
			messages: [
				{ role: 'user', content: 'What is 21 + 21?' },
				{ role: 'assistant', content: '21 + 21 is 42.' },
				{ role: 'user', content: 'Now multiply that result by 2.' },
			],
			customProvider: { baseUrl: baseEndpoint!, apiKey: apiKey! },
		});

		expect(result.text.trim().length).to.be.greaterThan(0);
		expect(result.viaGatewayBypass).to.equal(true);
	});

	it('surfaces a GatewayRequestError for an invalid model name', async function () {
		this.timeout(60000);

		try {
			await client.generate({
				provider: 'real-provider',
				model: 'this-model-definitely-does-not-exist-xyz',
				messages: [{ role: 'user', content: 'hello' }],
				customProvider: { baseUrl: baseEndpoint!, apiKey: apiKey! },
			});
			expect.fail('expected generate() to throw for an invalid model');
		} catch (err) {
			expect(err).to.be.instanceOf(GatewayRequestError);
			expect((err as GatewayRequestError).status).to.be.at.least(400);
		}
	});
});
