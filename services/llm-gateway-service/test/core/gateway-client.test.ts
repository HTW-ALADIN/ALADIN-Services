import dns from 'node:dns';
import { createServer } from 'node:http';
import net, { type LookupFunction } from 'node:net';
import tls from 'node:tls';
import { expect } from 'chai';
import sinon from 'sinon';
import { Agent, getGlobalDispatcher, ProxyAgent, setGlobalDispatcher } from 'undici';
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
	let sandbox: sinon.SinonSandbox;
	let providerAddresses: dns.LookupAddress[];
	let providerLookups: number;
	let previousDirectEgress: string | undefined;

	beforeEach(async () => {
		previousDirectEgress = process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS;
		process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS = 'true';
		server = new MockOpenAIServer();
		baseUrl = await server.listen();
		sandbox = sinon.createSandbox();
		providerAddresses = [{ address: '8.8.8.8', family: 4 }];
		providerLookups = 0;

		const originalLookup = dns.lookup;
		sandbox.stub(dns, 'lookup').callsFake(((hostname, options, callback) => {
			if (hostname === 'custom-provider.test') {
				providerLookups += 1;
				const addresses = providerAddresses;
				queueMicrotask(() => callback(null, addresses));
				return;
			}
			return (originalLookup as any)(hostname, options, callback);
		}) as typeof dns.lookup);

		const originalConnect = net.connect;
		sandbox.stub(net, 'connect').callsFake(((...args: any[]) => {
			const options = args[0];
			if (options?.host === 'custom-provider.test') {
				const lookup: LookupFunction = options.lookup;
				return originalConnect({
					...options,
					lookup: (hostname, lookupOptions, callback) => {
						lookup(hostname, lookupOptions, (error, address, family) => {
							if (error) {
								callback(error, address, family);
							} else if (lookupOptions.all) {
								callback(null, [{ address: '127.0.0.1', family: 4 }]);
							} else {
								callback(null, '127.0.0.1', 4);
							}
						});
					},
				});
			}
			return (originalConnect as any)(...args);
		}) as typeof net.connect);
	});

	afterEach(async () => {
		sandbox.restore();
		if (previousDirectEgress === undefined) {
			delete process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS;
		} else {
			process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS = previousDirectEgress;
		}
		await server.close();
	});

	function publicProviderUrl(localUrl: string): string {
		const url = new URL(localUrl);
		url.hostname = 'custom-provider.test';
		return url.origin;
	}

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
			const customBaseUrl = publicProviderUrl(await customServer.listen());
			customServer.on('/chat/completions', (body, req) => {
				expect(body.model).to.equal('custom-gpt-4');
				expect(req.headers.host).to.equal(new URL(customBaseUrl).host);
				expect(req.headers.authorization).to.equal('Bearer custom-key');
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
				expect(providerLookups).to.equal(1);
				expect(gatewayCalled).to.equal(false);
			} finally {
				await customServer.close();
			}
		});

		it('sends system, image content, and tool definitions in OpenAI chat-completions shape', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = publicProviderUrl(await customServer.listen());
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
			const customBaseUrl = publicProviderUrl(await customServer.listen());
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
			const customBaseUrl = publicProviderUrl(await customServer.listen());
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
			const customBaseUrl = publicProviderUrl(await customServer.listen());
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
			const customBaseUrl = publicProviderUrl(await customServer.listen());
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
			const customBaseUrl = publicProviderUrl(await customServer.listen());
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

		for (const status of [307, 308]) {
			it(`follows a same-origin ${status} gateway redirect with the request intact`, async () => {
				let redirectedBody: unknown;
				let redirectedAuthorization: string | undefined;
				server.on('/embeddings', () => ({
					status,
					body: {},
					headers: { Location: '/forwarded-embeddings' },
				}));
				server.on('/forwarded-embeddings', (body, req) => {
					redirectedBody = body;
					redirectedAuthorization = req.headers.authorization;
					expect(req.method).to.equal('POST');
					return { status: 200, body: embeddingResponse([[0.1]]) };
				});

				const client = new GatewayClient({ baseUrl, apiKey: 'test-key', timeoutMs: 5000 });
				const result = await client.embedText({ provider: 'openai', model: 'embed', input: 'hello' });
				expect(result.embeddings).to.deep.equal([[0.1]]);
				expect(redirectedBody).to.deep.equal({ model: 'openai/embed', input: 'hello' });
				expect(redirectedAuthorization).to.equal('Bearer test-key');
			});
		}

		it('follows a cross-origin gateway redirect without forwarding its authorization', async () => {
			const destination = new MockOpenAIServer();
			const destinationUrl = await destination.listen();
			let destinationAuthorization: string | undefined;
			server.on('/embeddings', () => ({
				status: 307,
				body: {},
				headers: { Location: `${destinationUrl}/embeddings` },
			}));
			destination.on('/embeddings', (body, req) => {
				destinationAuthorization = req.headers.authorization;
				expect(body).to.deep.equal({ model: 'openai/embed', input: 'hello' });
				return { status: 200, body: embeddingResponse([[0.1]]) };
			});

			try {
				const client = new GatewayClient({ baseUrl, apiKey: 'test-key', timeoutMs: 5000 });
				const result = await client.embedText({ provider: 'openai', model: 'embed', input: 'hello' });
				expect(result.embeddings).to.deep.equal([[0.1]]);
				expect(destinationAuthorization).to.equal(undefined);
			} finally {
				await destination.close();
			}
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
			const customBaseUrl = publicProviderUrl(await customServer.listen());
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
			const customBaseUrl = publicProviderUrl(await customServer.listen());
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

	describe('custom provider destination safety', () => {
		function callProvider(
			client: GatewayClient,
			operation: 'generate' | 'embeddings',
			customBaseUrl: string
		) {
			const customProvider = { baseUrl: customBaseUrl, apiKey: 'custom-key' };
			if (operation === 'generate') {
				return client.generate(baseRequest({ customProvider }));
			}
			return client.embedText({
				provider: 'custom',
				model: 'embedding-model',
				input: 'hello',
				customProvider,
			});
		}

		async function captureError(promise: Promise<unknown>): Promise<unknown> {
			try {
				await promise;
			} catch (error) {
				return error;
			}
			throw new Error('Expected the request to fail');
		}

		for (const { name, value } of [
			{ name: 'HTTP_PROXY', value: 'http://proxy.invalid:8080' },
			{ name: 'HTTPS_PROXY', value: 'http://proxy.invalid:8080' },
			{ name: 'ALL_PROXY', value: 'http://proxy.invalid:8080' },
			{ name: 'http_proxy', value: 'http://proxy.invalid:8080' },
			{ name: 'https_proxy', value: 'http://proxy.invalid:8080' },
			{ name: 'all_proxy', value: 'http://proxy.invalid:8080' },
			{ name: 'GLOBAL_AGENT_HTTP_PROXY', value: 'http://proxy.invalid:8080' },
			{ name: 'GLOBAL_AGENT_HTTPS_PROXY', value: 'http://proxy.invalid:8080' },
			{ name: 'NODE_USE_ENV_PROXY', value: '1' },
			{ name: 'NODE_OPTIONS', value: '"--use-env-proxy"' },
		]) {
			it(`fails closed for ${name}, even when NO_PROXY is set`, async () => {
				const previous = process.env[name];
				const previousNoProxy = process.env.NO_PROXY;
				process.env[name] = value;
				process.env.NO_PROXY = '*';
				try {
					const client = new GatewayClient({ baseUrl, apiKey: 'test-key', timeoutMs: 5000 });
					for (const operation of ['generate', 'embeddings'] as const) {
						const error = await captureError(callProvider(client, operation, publicProviderUrl(baseUrl)));
						expect(error).to.be.instanceOf(GatewayRequestError);
						expect((error as GatewayRequestError).status).to.equal(503);
					}
					expect(providerLookups).to.equal(0);
				} finally {
					if (previous === undefined) delete process.env[name];
					else process.env[name] = previous;
					if (previousNoProxy === undefined) delete process.env.NO_PROXY;
					else process.env.NO_PROXY = previousNoProxy;
				}
			});
		}

		it('fails closed when Node enables its environment-proxy option', async () => {
			sandbox.stub(process, 'execArgv').value([...process.execArgv, '--use-env-proxy']);
			const client = new GatewayClient({ baseUrl, apiKey: 'test-key', timeoutMs: 5000 });
			const error = await captureError(callProvider(client, 'embeddings', publicProviderUrl(baseUrl)));
			expect(error).to.be.instanceOf(GatewayRequestError);
			expect((error as GatewayRequestError).status).to.equal(503);
			expect(providerLookups).to.equal(0);
		});

		it('fails closed when an unknown global dispatcher replaces the original', async () => {
			const previous = getGlobalDispatcher();
			const replacement = new Agent({ connect: () => { throw new Error('unexpected connection'); } });
			setGlobalDispatcher(replacement);
			try {
				const client = new GatewayClient({ baseUrl, apiKey: 'test-key', timeoutMs: 5000 });
				for (const operation of ['generate', 'embeddings'] as const) {
					const error = await captureError(callProvider(client, operation, publicProviderUrl(baseUrl)));
					expect(error).to.be.instanceOf(GatewayRequestError);
					expect((error as GatewayRequestError).status).to.equal(503);
				}
				expect(providerLookups).to.equal(0);
			} finally {
				setGlobalDispatcher(previous);
				await replacement.destroy();
			}
		});

		it('fails closed if the original global dispatcher is modified', async () => {
			sandbox.stub(getGlobalDispatcher(), 'dispatch').callsFake(() => {
				throw new Error('unexpected global dispatch');
			});
			const client = new GatewayClient({ baseUrl, apiKey: 'test-key', timeoutMs: 5000 });
			const error = await captureError(callProvider(client, 'embeddings', publicProviderUrl(baseUrl)));
			expect(error).to.be.instanceOf(GatewayRequestError);
			expect((error as GatewayRequestError).status).to.equal(503);
			expect(providerLookups).to.equal(0);
		});

		it('fails closed if another Undici global dispatcher version is present', async () => {
			const symbol = Symbol.for('undici.globalDispatcher.2');
			Object.defineProperty(globalThis, symbol, { value: {}, configurable: true });
			try {
				const client = new GatewayClient({ baseUrl, apiKey: 'test-key', timeoutMs: 5000 });
				const error = await captureError(callProvider(client, 'embeddings', publicProviderUrl(baseUrl)));
				expect(error).to.be.instanceOf(GatewayRequestError);
				expect((error as GatewayRequestError).status).to.equal(503);
				expect(providerLookups).to.equal(0);
			} finally {
				Reflect.deleteProperty(globalThis, symbol);
			}
		});

		it('uses the configured global proxy for trusted gateway traffic without bypassing it for custom providers', async () => {
			const proxyServer = createServer();
			let proxyConnections = 0;
			let proxyTarget: string | undefined;
			proxyServer.on('connect', (request, socket, head) => {
				proxyConnections += 1;
				proxyTarget = request.url;
				const upstream = net.connect({ host: '127.0.0.1', port: Number(new URL(baseUrl).port) });
				socket.on('error', () => {});
				upstream.on('error', () => socket.destroy());
				socket.on('close', () => upstream.destroy());
				upstream.on('connect', () => {
					socket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
					if (head.length) upstream.write(head);
					socket.pipe(upstream).pipe(socket);
				});
			});
			await new Promise<void>((resolve) => proxyServer.listen(0, '127.0.0.1', resolve));
			const address = proxyServer.address();
			if (!address || typeof address === 'string') throw new Error('Proxy did not listen');
			const previous = getGlobalDispatcher();
			const proxy = new ProxyAgent(`http://127.0.0.1:${address.port}`);
			setGlobalDispatcher(proxy);
			let gatewayCalls = 0;
			let gatewayRedirects = 0;
			server.on('/embeddings', () => {
				gatewayRedirects += 1;
				return { status: 307, body: {}, headers: { Location: '/redirected-embeddings' } };
			});
			server.on('/redirected-embeddings', () => {
				gatewayCalls += 1;
				return { status: 200, body: embeddingResponse([[0.3]]) };
			});

			try {
				const client = new GatewayClient({ baseUrl, apiKey: 'test-key', timeoutMs: 5000 });
				const result = await client.embedText({ provider: 'openai', model: 'embed', input: 'hello' });
				expect(result.embeddings).to.deep.equal([[0.3]]);
				expect(proxyConnections).to.be.at.least(1);
				expect(proxyTarget).to.equal(new URL(baseUrl).host);
				expect(gatewayRedirects).to.equal(1);
				const establishedProxyConnections = proxyConnections;

				for (const operation of ['generate', 'embeddings'] as const) {
					const error = await captureError(callProvider(client, operation, publicProviderUrl(baseUrl)));
					expect(error).to.be.instanceOf(GatewayRequestError);
					expect((error as GatewayRequestError).status).to.equal(503);
				}
				expect(gatewayCalls).to.equal(1);
				expect(gatewayRedirects).to.equal(1);
				expect(proxyConnections).to.equal(establishedProxyConnections);
				expect(providerLookups).to.equal(0);
			} finally {
				setGlobalDispatcher(previous);
				await proxy.destroy();
				await new Promise<void>((resolve, reject) => proxyServer.close((error) => error ? reject(error) : resolve()));
			}
		});

		it('does not reuse an open custom-provider connection after the global dispatcher changes', async () => {
			let destinationCalls = 0;
			server.on('/embeddings', () => {
				destinationCalls += 1;
				return { status: 200, body: embeddingResponse([[0.1]]) };
			});
			const client = new GatewayClient({ baseUrl, apiKey: 'test-key', timeoutMs: 5000 });
			const customBaseUrl = publicProviderUrl(baseUrl);
			const first = await callProvider(client, 'embeddings', customBaseUrl);
			expect(first).to.have.property('embeddings');
			expect(providerLookups).to.equal(1);

			const previous = getGlobalDispatcher();
			const proxy = new ProxyAgent('http://127.0.0.1:1');
			setGlobalDispatcher(proxy);
			try {
				const error = await captureError(callProvider(client, 'embeddings', customBaseUrl));
				expect(error).to.be.instanceOf(GatewayRequestError);
				expect((error as GatewayRequestError).status).to.equal(503);
				expect(destinationCalls).to.equal(1);
				expect(providerLookups).to.equal(1);
			} finally {
				setGlobalDispatcher(previous);
				await proxy.destroy();
			}
		});

		it('fails closed if the global dispatcher changes while DNS is resolving', async () => {
			let releaseLookup: (() => void) | undefined;
			let markLookupStarted: (() => void) | undefined;
			const lookupStarted = new Promise<void>((resolve) => { markLookupStarted = resolve; });
			(dns.lookup as unknown as sinon.SinonStub).callsFake(((_hostname, _options, callback) => {
				providerLookups += 1;
				releaseLookup = () => callback(null, [{ address: '8.8.8.8', family: 4 }]);
				markLookupStarted!();
			}) as typeof dns.lookup);
			let destinationCalled = false;
			server.on('/embeddings', () => {
				destinationCalled = true;
				return { status: 200, body: embeddingResponse([[0.1]]) };
			});
			const client = new GatewayClient({ baseUrl, apiKey: 'test-key', timeoutMs: 5000 });
			const pending = callProvider(client, 'embeddings', publicProviderUrl(baseUrl));
			const previous = getGlobalDispatcher();
			const proxy = new ProxyAgent('http://127.0.0.1:1');
			try {
				await lookupStarted;
				setGlobalDispatcher(proxy);
				releaseLookup!();
				const error = await captureError(pending);
				expect(error).to.be.instanceOf(GatewayRequestError);
				expect((error as GatewayRequestError).status).to.equal(503);
				expect(providerLookups).to.equal(1);
				expect(destinationCalled).to.equal(false);
			} finally {
				setGlobalDispatcher(previous);
				await proxy.destroy();
			}
		});

		for (const operation of ['generate', 'embeddings'] as const) {
			it(`rejects literal private destinations for programmatic ${operation} requests`, async () => {
				let destinationCalled = false;
				const path =
					operation === 'generate' ? '/chat/completions' : '/embeddings';
				server.on(path, () => {
					destinationCalled = true;
					return { status: 200, body: {} };
				});
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				const error = await captureError(
					callProvider(client, operation, baseUrl)
				);

				expect(error).to.be.instanceOf(GatewayRequestError);
				expect((error as GatewayRequestError).status).to.equal(400);
				expect(providerLookups).to.equal(0);
				expect(destinationCalled).to.equal(false);
			});

			for (const { name, addresses } of [
				{
					name: 'IPv4 loopback',
					addresses: [{ address: '127.0.0.1', family: 4 }],
				},
				{
					name: 'IPv6 link-local',
					addresses: [{ address: 'febf::1', family: 6 }],
				},
				{
					name: 'IPv4-mapped IPv6',
					addresses: [{ address: '::ffff:10.0.0.1', family: 6 }],
				},
				{
					name: 'mixed public and private records',
					addresses: [
						{ address: '8.8.8.8', family: 4 },
						{ address: '169.254.169.254', family: 4 },
					],
				},
			]) {
				it(`rejects ${name} DNS answers at connection time for ${operation}`, async () => {
					providerAddresses = addresses;
					const customServer = new MockOpenAIServer();
					const customBaseUrl = publicProviderUrl(await customServer.listen());
					const path =
						operation === 'generate' ? '/chat/completions' : '/embeddings';
					let destinationCalled = false;
					customServer.on(path, () => {
						destinationCalled = true;
						return { status: 200, body: {} };
					});

					try {
						const client = new GatewayClient({
							baseUrl,
							apiKey: 'test-key',
							timeoutMs: 5000,
						});
						const error = await captureError(
							callProvider(client, operation, customBaseUrl)
						);
						expect(error).to.be.instanceOf(GatewayRequestError);
						expect((error as GatewayRequestError).status).to.equal(400);
						expect(providerLookups).to.equal(1);
						expect(destinationCalled).to.equal(false);
					} finally {
						await customServer.close();
					}
				});
			}

			for (const status of [301, 302, 303, 307, 308]) {
				it(`does not follow ${status} redirects to a private ${operation} destination`, async () => {
					const customServer = new MockOpenAIServer();
					const customBaseUrl = publicProviderUrl(await customServer.listen());
					const path =
						operation === 'generate' ? '/chat/completions' : '/embeddings';
					let providerCalled = false;
					let destinationCalled = false;
					customServer.on(path, () => {
						providerCalled = true;
						return {
							status,
							body: {},
							headers: { Location: `${baseUrl}${path}` },
						};
					});
					server.on(path, () => {
						destinationCalled = true;
						return { status: 200, body: {} };
					});

					try {
						const client = new GatewayClient({
							baseUrl,
							apiKey: 'test-key',
							timeoutMs: 5000,
						});
						const error = await captureError(
							callProvider(client, operation, customBaseUrl)
						);
						expect(error).to.be.instanceOf(GatewayRequestError);
						expect((error as GatewayRequestError).status).to.equal(502);
						expect(providerCalled).to.equal(true);
						expect(destinationCalled).to.equal(false);
					} finally {
						await customServer.close();
					}
				});
			}
		}

		it('accepts a public IPv6 DNS answer for a custom provider', async () => {
			providerAddresses = [{ address: '2606:4700:4700::1111', family: 6 }];
			const customServer = new MockOpenAIServer();
			const customBaseUrl = publicProviderUrl(await customServer.listen());
			customServer.on('/embeddings', (_body, req) => {
				expect(req.headers.host).to.equal(new URL(customBaseUrl).host);
				return { status: 200, body: embeddingResponse([[0.2]]) };
			});

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				const result = await callProvider(client, 'embeddings', customBaseUrl);
				expect(result)
					.to.have.property('embeddings')
					.that.deep.equals([[0.2]]);
				expect(providerLookups).to.equal(1);
			} finally {
				await customServer.close();
			}
		});

		it('preserves the hostname and TLS verification for HTTPS providers', async () => {
			providerAddresses = [{ address: '127.0.0.1', family: 4 }];
			const tlsConnect = sandbox.spy(tls, 'connect');
			const client = new GatewayClient({
				baseUrl,
				apiKey: 'test-key',
				timeoutMs: 5000,
			});
			const error = await captureError(
				callProvider(client, 'generate', 'https://custom-provider.test')
			);

			expect(error).to.be.instanceOf(GatewayRequestError);
			expect((error as GatewayRequestError).status).to.equal(400);
			expect(tlsConnect.calledOnce).to.equal(true);
			const options = tlsConnect.firstCall.args[0] as tls.ConnectionOptions;
			expect(options.host).to.equal('custom-provider.test');
			expect(options.servername).to.equal('custom-provider.test');
			expect(options.rejectUnauthorized).not.to.equal(false);
		});

		it('rechecks DNS after a public provider rebinds between connections', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = publicProviderUrl(await customServer.listen());
			let calls = 0;
			customServer.on('/embeddings', () => {
				calls += 1;
				return {
					status: 200,
					body: embeddingResponse([[0.1]]),
					headers: { Connection: 'close' },
				};
			});

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				const first = await callProvider(client, 'embeddings', customBaseUrl);
				expect(first).to.have.property('embeddings');
				expect(providerLookups).to.equal(1);

				providerAddresses = [{ address: '127.0.0.1', family: 4 }];
				const error = await captureError(
					callProvider(client, 'embeddings', customBaseUrl)
				);
				expect(error).to.be.instanceOf(GatewayRequestError);
				expect((error as GatewayRequestError).status).to.equal(400);
				expect(providerLookups).to.equal(2);
				expect(calls).to.equal(1);
			} finally {
				await customServer.close();
			}
		});

		it('does not follow a relative redirect on the provider origin', async () => {
			const customServer = new MockOpenAIServer();
			const customBaseUrl = publicProviderUrl(await customServer.listen());
			let redirected = false;
			customServer.on('/chat/completions', () => ({
				status: 307,
				body: {},
				headers: { Location: '/redirected' },
			}));
			customServer.on('/redirected', () => {
				redirected = true;
				return { status: 200, body: chatCompletionResponse() };
			});

			try {
				const client = new GatewayClient({
					baseUrl,
					apiKey: 'test-key',
					timeoutMs: 5000,
				});
				const error = await captureError(
					callProvider(client, 'generate', customBaseUrl)
				);
				expect(error).to.be.instanceOf(GatewayRequestError);
				expect((error as GatewayRequestError).status).to.equal(502);
				expect(redirected).to.equal(false);
			} finally {
				await customServer.close();
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
