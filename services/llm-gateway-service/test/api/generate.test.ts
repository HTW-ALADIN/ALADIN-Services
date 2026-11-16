import dns from 'node:dns';
import { expect } from 'chai';
import sinon from 'sinon';
import type { FastifyInstance } from 'fastify';
import { buildServer } from '../../src/api/server.js';
import { GatewayClient } from '../../src/core/gateway-client.js';
import {
	GatewayRequestError,
	type EmbedRequest,
	type GenerateRequest,
} from '../../src/core/types.js';
import { MockOpenAIServer } from '../support/mock-openai-server.js';

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
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [{ type: 'text', text: 'hello' }],
					},
				],
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
			},
		]);
	});

	it('defaults to the Vercel format when "format" is omitted', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/generate',
			payload: {
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [{ type: 'text', text: 'hello' }],
					},
				],
			},
		});

		expect(response.statusCode).to.equal(200);
		expect(response.json()).to.have.property('finishReason');
	});

	it('accepts an OpenAI Chat Completions-format request', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/generate',
			payload: {
				format: 'openai-chat',
				provider: 'openai',
				model: 'gpt-4o',
				messages: [{ role: 'user', content: 'hello' }],
			},
		});

		expect(response.statusCode).to.equal(200);
		const body = response.json();
		expect(body.object).to.equal('chat.completion');
		expect(body.choices[0].message.role).to.equal('assistant');
		expect(client.lastGenerateRequest?.messages).to.deep.equal([
			{ role: 'user', content: 'hello', toolCallId: undefined },
		]);
	});

	it('accepts an OpenAI Responses-format request', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/generate',
			payload: {
				format: 'openai-responses',
				provider: 'openai',
				model: 'gpt-4o',
				input: 'hello',
			},
		});

		expect(response.statusCode).to.equal(200);
		const body = response.json();
		expect(body.object).to.equal('response');
		expect(client.lastGenerateRequest?.messages).to.deep.equal([
			{ role: 'user', content: 'hello' },
		]);
	});

	it('rejects a request with an unknown format', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/generate',
			payload: {
				format: 'not-a-real-format',
				provider: 'openai',
				model: 'gpt-4o',
				messages: [{ role: 'user', content: 'hello' }],
			},
		});

		expect(response.statusCode).to.equal(400);
	});

	it('rejects a request missing required fields with 400', async () => {
		const response = await app.inject({
			method: 'POST',
			url: '/generate',
			payload: {
				model: 'gpt-4o',
				messages: [
					{ id: 'msg-1', role: 'user', parts: [{ type: 'text', text: 'hi' }] },
				],
			},
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
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [{ type: 'text', text: 'hello' }],
					},
				],
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
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [{ type: 'text', text: 'hello' }],
					},
				],
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

	for (const baseUrl of [
		'http://127.0.0.1/v1',
		'http://10.0.0.1/v1',
		'http://169.254.169.254/v1',
		'http://[::ffff:127.0.0.1]/v1',
		'file:///etc/passwd',
		'not-a-url',
	]) {
		it(`rejects custom provider ${baseUrl} before invoking the client`, async () => {
			const response = await app.inject({
				method: 'POST',
				url: '/embeddings',
				payload: {
					provider: 'custom',
					model: 'embedding-model',
					input: 'hello',
					customProvider: { baseUrl, apiKey: 'custom-key' },
				},
			});

			expect(response.statusCode).to.equal(400);
			expect(client.lastEmbedRequest).to.equal(undefined);
		});
	}

	it('forwards a public custom provider to the embeddings client', async () => {
		const customProvider = {
			baseUrl: 'https://fcloud.example.com/v1',
			apiKey: 'custom-key',
		};
		const response = await app.inject({
			method: 'POST',
			url: '/embeddings',
			payload: {
				provider: 'custom',
				model: 'embedding-model',
				input: 'hello',
				customProvider,
			},
		});

		expect(response.statusCode).to.equal(200);
		expect(client.lastEmbedRequest?.customProvider).to.deep.equal(
			customProvider
		);
	});
});

describe('HTTP custom provider connection safety', () => {
	for (const operation of ['generate', 'embeddings'] as const) {
		it(`returns 503 without sending ${operation} traffic when proxy egress is configured`, async () => {
			const previousProxy = process.env.HTTPS_PROXY;
			process.env.HTTPS_PROXY = 'http://127.0.0.1:1';
			const fetchStub = sinon.stub(globalThis, 'fetch');
			const app = await buildServer({
				generate: {
					client: new GatewayClient({
						baseUrl: 'http://127.0.0.1:1',
						apiKey: 'gateway-key',
						timeoutMs: 5000,
					}),
				},
			});
			try {
				const common = {
					provider: 'custom',
					model: 'model',
					customProvider: { baseUrl: 'https://provider.example/v1', apiKey: 'custom-key' },
				};
				const payload = operation === 'generate'
					? { ...common, format: 'openai-chat', messages: [{ role: 'user', content: 'hello' }] }
					: { ...common, input: 'hello' };
				const response = await app.inject({ method: 'POST', url: `/${operation}`, payload });
				expect(response.statusCode).to.equal(503);
				expect(response.json().message).to.match(/proxy or unverified global dispatcher/);
				expect(fetchStub.notCalled).to.equal(true);
			} finally {
				fetchStub.restore();
				if (previousProxy === undefined) delete process.env.HTTPS_PROXY;
				else process.env.HTTPS_PROXY = previousProxy;
				await app.close();
			}
		});
	}

	for (const operation of ['generate', 'embeddings'] as const) {
		it(`blocks a DNS-resolved private ${operation} destination`, async () => {
			const previousDirectEgress = process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS;
			process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS = 'true';
			const destination = new MockOpenAIServer();
			const localUrl = await destination.listen();
			const providerUrl = new URL(localUrl);
			providerUrl.hostname = 'rebinding-api.test';
			const path =
				operation === 'generate' ? '/chat/completions' : '/embeddings';
			let destinationCalled = false;
			destination.on(path, () => {
				destinationCalled = true;
				return { status: 200, body: {} };
			});

			const originalLookup = dns.lookup;
			const lookupStub = sinon.stub(dns, 'lookup').callsFake(((
				hostname,
				options,
				callback
			) => {
				if (hostname === 'rebinding-api.test') {
					queueMicrotask(() =>
						callback(null, [{ address: '127.0.0.1', family: 4 }])
					);
					return;
				}
				return (originalLookup as any)(hostname, options, callback);
			}) as typeof dns.lookup);
			const app = await buildServer({
				generate: {
					client: new GatewayClient({
						baseUrl: localUrl,
						apiKey: 'gateway-key',
						timeoutMs: 5000,
					}),
				},
			});

			try {
				const common = {
					provider: 'custom',
					model: 'model',
					customProvider: { baseUrl: providerUrl.origin, apiKey: 'custom-key' },
				};
				const payload =
					operation === 'generate'
						? {
								...common,
								format: 'openai-chat',
								messages: [{ role: 'user', content: 'hello' }],
							}
						: { ...common, input: 'hello' };
				const response = await app.inject({
					method: 'POST',
					url: `/${operation}`,
					payload,
				});
				expect(response.statusCode).to.equal(400);
				expect(response.json().message).to.match(/disallowed/);
				expect(lookupStub.calledOnce).to.equal(true);
				expect(destinationCalled).to.equal(false);
			} finally {
				lookupStub.restore();
				if (previousDirectEgress === undefined) {
					delete process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS;
				} else {
					process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS = previousDirectEgress;
				}
				await app.close();
				await destination.close();
			}
		});
	}
});
