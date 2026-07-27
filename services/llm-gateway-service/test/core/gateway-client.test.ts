import { expect } from 'chai';
import {
	GatewayClient,
	toGatewayRequestError,
} from '../../src/core/gateway-client.js';
import {
	GatewayRequestError,
	type GenerateRequest,
} from '../../src/core/types.js';
import {
	MockOpenAIServer,
	chatCompletionResponse,
	embeddingResponse,
} from '../support/mock-openai-server.js';

describe('GatewayClient', () => {
	let server: MockOpenAIServer;
	let baseUrl: string;

	beforeEach(async () => {
		server = new MockOpenAIServer();
		baseUrl = await server.listen();
	});

	afterEach(async () => {
		await server.close();
	});

	function baseRequest(
		overrides: Partial<GenerateRequest> = {}
	): GenerateRequest {
		return {
			provider: 'openai',
			model: 'gpt-4o',
			messages: [{ role: 'user', content: 'hello' }],
			...overrides,
		};
	}

	describe('generate — via gateway', () => {
		it('routes through the configured gateway base URL and returns a normalized response', async () => {
			server.on('/chat/completions', (body) => {
				expect(body.model).to.equal('openai/gpt-4o');
				expect(body.messages).to.deep.equal([
					{ role: 'user', content: 'hello' },
				]);
				return { status: 200, body: chatCompletionResponse() };
			});

			const client = new GatewayClient({
				baseUrl,
				apiKey: 'test-key',
				timeoutMs: 5000,
			});
			const result = await client.generate(baseRequest());

			expect(result.text).to.equal('Hello there');
			expect(result.finishReason).to.equal('stop');
			expect(result.usage).to.deep.equal({
				inputTokens: 3,
				outputTokens: 4,
				totalTokens: 7,
			});
			expect(result.provider).to.equal('openai');
			expect(result.model).to.equal('gpt-4o');
			expect(result.viaGatewayBypass).to.equal(false);
		});

		it('surfaces the cost reported by LLM Gateway usage accounting', async () => {
			server.on('/chat/completions', () => ({
				status: 200,
				body: chatCompletionResponse({
					usage: {
						prompt_tokens: 3,
						completion_tokens: 4,
						total_tokens: 7,
						cost: 0.0042,
					},
				}),
			}));

			const client = new GatewayClient({
				baseUrl,
				apiKey: 'test-key',
				timeoutMs: 5000,
			});
			const result = await client.generate(baseRequest());

			expect(result.cost).to.equal(0.0042);
		});

		it('maps a 4xx gateway error to a GatewayRequestError with the same status', async () => {
			server.on('/chat/completions', () => ({
				status: 429,
				body: { error: { message: 'rate limited', type: 'rate_limit_error' } },
			}));

			const client = new GatewayClient({
				baseUrl,
				apiKey: 'test-key',
				timeoutMs: 5000,
			});

			try {
				await client.generate(baseRequest());
				expect.fail('expected generate() to throw');
			} catch (err) {
				expect(err).to.be.instanceOf(GatewayRequestError);
				expect((err as GatewayRequestError).status).to.equal(429);
			}
		});

		it('maps tool calls back onto the response', async () => {
			server.on('/chat/completions', () => ({
				status: 200,
				body: chatCompletionResponse({
					choices: [
						{
							index: 0,
							message: {
								role: 'assistant',
								content: null,
								tool_calls: [
									{
										id: 'call_1',
										type: 'function',
										function: {
											name: 'weather',
											arguments: '{"location":"Berlin"}',
										},
									},
								],
							},
							finish_reason: 'tool_calls',
						},
					],
				}),
			}));

			const client = new GatewayClient({
				baseUrl,
				apiKey: 'test-key',
				timeoutMs: 5000,
			});
			const result = await client.generate(
				baseRequest({
					tools: [
						{
							name: 'weather',
							description: 'Get the weather',
							parameters: {
								type: 'object',
								properties: { location: { type: 'string' } },
							},
						},
					],
				})
			);

			expect(result.finishReason).to.equal('tool-calls');
			expect(result.toolCalls).to.have.length(1);
			expect(result.toolCalls?.[0].toolName).to.equal('weather');
		});
	});

	describe('generate — missing gateway API key', () => {
		it('fails fast with a clear message instead of silently calling the gateway unauthenticated', async () => {
			let gatewayCalled = false;
			server.on('/chat/completions', () => {
				gatewayCalled = true;
				return { status: 200, body: chatCompletionResponse() };
			});

			const client = new GatewayClient({
				baseUrl,
				apiKey: '',
				timeoutMs: 5000,
			});

			try {
				await client.generate(baseRequest());
				expect.fail('expected generate() to throw');
			} catch (err) {
				expect(err).to.be.instanceOf(GatewayRequestError);
				expect((err as GatewayRequestError).message).to.match(
					/LLM_GATEWAY_API_KEY is not configured/
				);
			}
			expect(gatewayCalled).to.equal(false);
		});
	});

	describe('generate — via customProvider bypass', () => {
		it('calls the custom endpoint directly instead of the gateway', async () => {
			let gatewayCalled = false;
			server.on('/chat/completions', () => {
				gatewayCalled = true;
				return { status: 200, body: chatCompletionResponse() };
			});

			const customServer = new MockOpenAIServer();
			const customBaseUrl = await customServer.listen();
			customServer.on('/chat/completions', (body) => {
				expect(body.model).to.equal('custom-gpt-4');
				return {
					status: 200,
					body: chatCompletionResponse({ model: 'custom-gpt-4' }),
				};
			});

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				const result = await client.generate(
					baseRequest({
						provider: 'mycompany',
						model: 'custom-gpt-4',
						customProvider: { baseUrl: customBaseUrl, apiKey: 'custom-key' },
					})
				);

				expect(result.viaGatewayBypass).to.equal(true);
				expect(result.text).to.equal('Hello there');
				expect(gatewayCalled).to.equal(false);
			} finally {
				await customServer.close();
			}
		});

		it('sends system, image content, and tool definitions in OpenAI chat-completions shape', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = await customServer.listen();
			customServer.on('/chat/completions', (body) => {
				expect(body.messages[0]).to.deep.equal({
					role: 'system',
					content: 'Answer concisely.',
				});
				expect(body.messages[1].content).to.deep.equal([
					{ type: 'text', text: 'describe this' },
					{
						type: 'image_url',
						image_url: { url: 'https://example.com/cat.png' },
					},
				]);
				expect(body.tools).to.deep.equal([
					{
						type: 'function',
						function: {
							name: 'weather',
							description: 'Get the weather',
							parameters: {
								type: 'object',
								properties: { location: { type: 'string' } },
							},
						},
					},
				]);
				return { status: 200, body: chatCompletionResponse() };
			});

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				await client.generate(
					baseRequest({
						provider: 'mycompany',
						model: 'custom-gpt-4',
						system: 'Answer concisely.',
						messages: [
							{
								role: 'user',
								content: [
									{ type: 'text', text: 'describe this' },
									{ type: 'image', image: 'https://example.com/cat.png' },
								],
							},
						],
						tools: [
							{
								name: 'weather',
								description: 'Get the weather',
								parameters: {
									type: 'object',
									properties: { location: { type: 'string' } },
								},
							},
						],
						customProvider: { baseUrl: customBaseUrl, apiKey: 'custom-key' },
					})
				);
			} finally {
				await customServer.close();
			}
		});

		it('sends a data-URL file part as an inline OpenAI file content part', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = await customServer.listen();
			customServer.on('/chat/completions', (body) => {
				expect(body.messages[0].content).to.deep.equal([
					{ type: 'text', text: 'summarize this' },
					{
						type: 'file',
						file: {
							filename: 'report.pdf',
							file_data: 'data:application/pdf;base64,AAA',
						},
					},
				]);
				return { status: 200, body: chatCompletionResponse() };
			});

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				await client.generate(
					baseRequest({
						provider: 'mycompany',
						model: 'custom-gpt-4',
						messages: [
							{
								role: 'user',
								content: [
									{ type: 'text', text: 'summarize this' },
									{
										type: 'file',
										data: 'data:application/pdf;base64,AAA',
										mediaType: 'application/pdf',
										filename: 'report.pdf',
									},
								],
							},
						],
						customProvider: { baseUrl: customBaseUrl, apiKey: 'custom-key' },
					})
				);
			} finally {
				await customServer.close();
			}
		});

		it('rejects a non-data-URL file part on the customProvider bypass path', async () => {
			const client = new GatewayClient({
				baseUrl,
				apiKey: 'test-key',
				timeoutMs: 5000,
			});

			let error: unknown;
			try {
				await client.generate(
					baseRequest({
						provider: 'mycompany',
						model: 'custom-gpt-4',
						messages: [
							{
								role: 'user',
								content: [
									{
										type: 'file',
										data: 'https://example.com/report.pdf',
										mediaType: 'application/pdf',
									},
								],
							},
						],
						customProvider: {
							baseUrl: 'https://api.mycompany.com',
							apiKey: 'custom-key',
						},
					})
				);
			} catch (err) {
				error = err;
			}

			expect(error).to.be.instanceOf(GatewayRequestError);
			expect((error as GatewayRequestError).status).to.equal(400);
			expect((error as GatewayRequestError).message).to.match(
				/must be a .*data URL/
			);
		});

		it('maps tool calls and finish reason returned by a custom provider', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = await customServer.listen();
			customServer.on('/chat/completions', () => ({
				status: 200,
				body: chatCompletionResponse({
					choices: [
						{
							index: 0,
							message: {
								role: 'assistant',
								content: null,
								tool_calls: [
									{
										id: 'call_9',
										type: 'function',
										function: {
											name: 'weather',
											arguments: '{"location":"Paris"}',
										},
									},
								],
							},
							finish_reason: 'tool_calls',
						},
					],
				}),
			}));

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				const result = await client.generate(
					baseRequest({
						provider: 'mycompany',
						model: 'custom-gpt-4',
						customProvider: { baseUrl: customBaseUrl, apiKey: 'custom-key' },
					})
				);

				expect(result.finishReason).to.equal('tool-calls');
				expect(result.toolCalls).to.deep.equal([
					{
						toolCallId: 'call_9',
						toolName: 'weather',
						args: { location: 'Paris' },
					},
				]);
			} finally {
				await customServer.close();
			}
		});

		it('falls back to the raw string when tool call arguments are not valid JSON', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = await customServer.listen();
			customServer.on('/chat/completions', () => ({
				status: 200,
				body: chatCompletionResponse({
					choices: [
						{
							index: 0,
							message: {
								role: 'assistant',
								content: null,
								tool_calls: [
									{
										id: 'call_1',
										type: 'function',
										function: { name: 'weather', arguments: 'not-json' },
									},
								],
							},
							finish_reason: 'tool_calls',
						},
					],
				}),
			}));

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				const result = await client.generate(
					baseRequest({
						provider: 'mycompany',
						model: 'custom-gpt-4',
						customProvider: { baseUrl: customBaseUrl, apiKey: 'custom-key' },
					})
				);

				expect(result.toolCalls?.[0].args).to.equal('not-json');
			} finally {
				await customServer.close();
			}
		});

		it('surfaces a 502 when the custom provider returns no choices', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = await customServer.listen();
			customServer.on('/chat/completions', () => ({
				status: 200,
				body: { choices: [] },
			}));

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				try {
					await client.generate(
						baseRequest({
							provider: 'mycompany',
							model: 'custom-gpt-4',
							customProvider: { baseUrl: customBaseUrl, apiKey: 'custom-key' },
						})
					);
					expect.fail('expected generate() to throw');
				} catch (err) {
					expect(err).to.be.instanceOf(GatewayRequestError);
					expect((err as GatewayRequestError).status).to.equal(502);
				}
			} finally {
				await customServer.close();
			}
		});

		it('maps content_filter and unrecognized finish reasons', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = await customServer.listen();
			customServer.on('/chat/completions', () => ({
				status: 200,
				body: chatCompletionResponse({
					choices: [
						{
							index: 0,
							message: { role: 'assistant', content: 'blocked' },
							finish_reason: 'content_filter',
						},
					],
				}),
			}));

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				const result = await client.generate(
					baseRequest({
						provider: 'mycompany',
						model: 'custom-gpt-4',
						customProvider: { baseUrl: customBaseUrl, apiKey: 'custom-key' },
					})
				);
				expect(result.finishReason).to.equal('content-filter');
			} finally {
				await customServer.close();
			}
		});
	});

	describe('embedText', () => {
		it('calls the gateway embeddings endpoint directly', async () => {
			server.on('/embeddings', (body) => {
				expect(body.model).to.equal('openai/text-embedding-3-small');
				return { status: 200, body: embeddingResponse([[0.1, 0.2, 0.3]]) };
			});

			const client = new GatewayClient({
				baseUrl,
				apiKey: 'test-key',
				timeoutMs: 5000,
			});
			const result = await client.embedText({
				provider: 'openai',
				model: 'text-embedding-3-small',
				input: 'hello',
			});

			expect(result.embeddings).to.deep.equal([[0.1, 0.2, 0.3]]);
			expect(result.provider).to.equal('openai');
			expect(result.model).to.equal('text-embedding-3-small');
		});

		it('maps embeddings errors to GatewayRequestError', async () => {
			server.on('/embeddings', () => ({
				status: 401,
				body: { error: { message: 'invalid api key' } },
			}));

			const client = new GatewayClient({
				baseUrl,
				apiKey: 'bad-key',
				timeoutMs: 5000,
			});

			try {
				await client.embedText({
					provider: 'openai',
					model: 'text-embedding-3-small',
					input: 'hello',
				});
				expect.fail('expected embedText() to throw');
			} catch (err) {
				expect(err).to.be.instanceOf(GatewayRequestError);
				expect((err as GatewayRequestError).status).to.equal(401);
			}
		});

		it('embeds via a custom provider bypass', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = await customServer.listen();
			customServer.on('/embeddings', () => ({
				status: 200,
				body: embeddingResponse([[0.4, 0.5]]),
			}));

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				const result = await client.embedText({
					provider: 'mycompany',
					model: 'custom-embed',
					input: 'hello',
					customProvider: { baseUrl: customBaseUrl, apiKey: 'custom-key' },
				});

				expect(result.embeddings).to.deep.equal([[0.4, 0.5]]);
			} finally {
				await customServer.close();
			}
		});

		it('batches multiple inputs into a single request via a custom provider', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = await customServer.listen();
			let callCount = 0;
			customServer.on('/embeddings', (body) => {
				callCount += 1;
				expect(body.input).to.deep.equal(['hello', 'world']);
				return { status: 200, body: embeddingResponse([[0.1], [0.2]]) };
			});

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				const result = await client.embedText({
					provider: 'mycompany',
					model: 'custom-embed',
					input: ['hello', 'world'],
					customProvider: { baseUrl: customBaseUrl, apiKey: 'custom-key' },
				});

				expect(callCount).to.equal(1);
				expect(result.embeddings).to.deep.equal([[0.1], [0.2]]);
			} finally {
				await customServer.close();
			}
		});

		it('fails fast with a clear message when the gateway API key is missing', async () => {
			const client = new GatewayClient({
				baseUrl,
				apiKey: '',
				timeoutMs: 5000,
			});

			try {
				await client.embedText({
					provider: 'openai',
					model: 'text-embedding-3-small',
					input: 'hi',
				});
				expect.fail('expected embedText() to throw');
			} catch (err) {
				expect(err).to.be.instanceOf(GatewayRequestError);
				expect((err as GatewayRequestError).message).to.match(
					/LLM_GATEWAY_API_KEY is not configured/
				);
			}
		});
	});
});

describe('toGatewayRequestError', () => {
	it('passes through an existing GatewayRequestError unchanged', () => {
		const original = new GatewayRequestError('boom', 418);
		expect(toGatewayRequestError(original)).to.equal(original);
	});

	it('defaults to a 502 status when the error has no status information', () => {
		const wrapped = toGatewayRequestError(new Error('connection reset'));
		expect(wrapped.status).to.equal(502);
		expect(wrapped.message).to.equal('connection reset');
	});

	it('extracts a status code from provider-shaped errors', () => {
		const wrapped = toGatewayRequestError({
			message: 'bad request',
			statusCode: 400,
		});
		expect(wrapped.status).to.equal(400);
	});
});
