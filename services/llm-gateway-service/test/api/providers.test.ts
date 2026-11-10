import { expect } from 'chai';
import type { FastifyInstance } from 'fastify';
import { buildServer } from '../../src/api/server.js';
import type { ProviderRegistry } from '../../src/core/provider-registry.js';

class FakeProviderRegistry {
	async register(input: { name: string; baseUrl: string; apiKey: string }) {
		if (input.name === 'boom') {
			throw new Error('unexpected failure');
		}
		return {
			registered: false,
			mode: 'skipped' as const,
			message: 'no admin API configured',
		};
	}
}

describe('POST /providers', () => {
	let app: FastifyInstance;

	beforeEach(async () => {
		app = await buildServer({
			providers: {
				registry: new FakeProviderRegistry() as unknown as ProviderRegistry,
			},
		});
	});

	afterEach(async () => {
		await app.close();
	});

	it('returns the registration result', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/providers',
			payload: {
				name: 'mycompany',
				baseUrl: 'https://api.mycompany.com',
				apiKey: 'sk-xxx',
			},
		});

		expect(response.statusCode).to.equal(200);
		expect(response.json()).to.deep.equal({
			registered: false,
			mode: 'skipped',
			message: 'no admin API configured',
		});
	});

	it('rejects a request with an invalid provider name at the schema level', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/providers',
			payload: {
				name: 'Invalid Name',
				baseUrl: 'https://api.mycompany.com',
				apiKey: 'sk-xxx',
			},
		});

		expect(response.statusCode).to.equal(400);
	});
});
