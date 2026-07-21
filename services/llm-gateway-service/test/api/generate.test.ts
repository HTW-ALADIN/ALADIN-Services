import { expect } from 'chai';
import type { FastifyInstance } from 'fastify';
import { buildServer } from '../../src/api/server.js';
import type { GatewayClient } from '../../src/core/gateway-client.js';
import {
	GatewayRequestError,
	type EmbedRequest,
	type GenerateRequest,
} from '../../src/core/types.js';

class FakeGatewayClient {
	lastGenerateRequest?: GenerateRequest;
	lastEmbedRequest?: EmbedRequest;
	generateError?: Error;

	async generate(request: GenerateRequest) {
		this.lastGenerateRequest = request;
		if (this.generateError) throw this.generateError;
		return {
			text: `echo: ${JSON.stringify(request.messages)}`,
			finishReason: 'stop' as const,
			usage: { inputTokens: 1, outputTokens: 2, totalTokens: 3 },
			cost: 0.001,
			provider: request.provider,
			model: request.model,
			viaGatewayBypass: Boolean(request.customProvider),
		};
	}

	async embedText(request: EmbedRequest) {
		this.lastEmbedRequest = request;
		return {
			embeddings: [[0.1, 0.2]],
			usage: { inputTokens: 1, totalTokens: 1 },
			provider: request.provider,
			model: request.model,
		};
	}
}

describe('POST /generate', () => {
	let app: FastifyInstance;
	let client: FakeGatewayClient;

	beforeEach(async () => {
		client = new FakeGatewayClient();
		app = await buildServer({
			generate: { client: client as unknown as GatewayClient },
		});
	});

	afterEach(async () => {
		await app.close();
	});

	it('translates a Vercel-format request and returns the formatted response', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/generate',
			payload: {
				provider: 'openai',
				model: 'gpt-4o',
				messages: [{ role: 'user', content: 'hello' }],
			},
		});

		expect(response.statusCode).to.equal(200);
		const body = response.json();
		expect(body.provider).to.equal('openai');
		expect(body.model).to.equal('gpt-4o');
		expect(body.cost).to.equal(0.001);
		expect(client.lastGenerateRequest?.messages).to.deep.equal([
			{
				role: 'user',
				content: 'hello',
				toolCallId: undefined,
				toolName: undefined,
			},
		]);
	});

	it('rejects a request missing required fields with 400', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/generate',
			payload: { model: 'gpt-4o', messages: [{ role: 'user', content: 'hi' }] },
		});

		expect(response.statusCode).to.equal(400);
	});

	it('propagates the upstream status code from a GatewayRequestError', async () => {
		client.generateError = new GatewayRequestError(
			'rate limited',
			429,
			'rate_limit_error'
		);

		const response = await app.inject({
			method: 'POST',
			url: '/generate',
			payload: {
				provider: 'openai',
				model: 'gpt-4o',
				messages: [{ role: 'user', content: 'hello' }],
			},
		});

		expect(response.statusCode).to.equal(429);
		expect(response.json()).to.deep.equal({
			statusCode: 429,
			error: 'Too Many Requests',
			message: 'rate limited',
			code: 'rate_limit_error',
		});
	});

	it('forwards a customProvider override to the client', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/generate',
			payload: {
				provider: 'mycompany',
				model: 'custom-gpt-4',
				messages: [{ role: 'user', content: 'hello' }],
				customProvider: {
					baseUrl: 'https://api.mycompany.com',
					apiKey: 'sk-xxx',
				},
			},
		});

		expect(response.statusCode).to.equal(200);
		expect(response.json().viaGatewayBypass).to.equal(true);
		expect(client.lastGenerateRequest?.customProvider).to.deep.equal({
			baseUrl: 'https://api.mycompany.com',
			apiKey: 'sk-xxx',
		});
	});
});

describe('POST /embeddings', () => {
	let app: FastifyInstance;
	let client: FakeGatewayClient;

	beforeEach(async () => {
		client = new FakeGatewayClient();
		app = await buildServer({
			generate: { client: client as unknown as GatewayClient },
		});
	});

	afterEach(async () => {
		await app.close();
	});

	it('returns embeddings for the given input', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/embeddings',
			payload: {
				provider: 'openai',
				model: 'text-embedding-3-small',
				input: 'hello',
			},
		});

		expect(response.statusCode).to.equal(200);
		expect(response.json().embeddings).to.deep.equal([[0.1, 0.2]]);
	});
});
