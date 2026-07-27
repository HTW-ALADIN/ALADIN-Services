import { expect } from 'chai';
import { vercelFormatAdapter } from '../../../src/core/format/vercel.js';
import type { GenerateResponse } from '../../../src/core/types.js';

describe('vercelFormatAdapter', () => {
	describe('parseRequest', () => {
		it('parses a minimal request', () => {
			const result = vercelFormatAdapter.parseRequest({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [{ type: 'text', text: 'hello' }],
					},
				],
			});

			expect(result).to.deep.equal({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						role: 'user',
						content: 'hello',
					},
				],
				system: undefined,
				tools: undefined,
				temperature: undefined,
				maxOutputTokens: undefined,
				topP: undefined,
				stopSequences: undefined,
				metadata: undefined,
				customProvider: undefined,
			});
		});

		it('joins multiple text parts within a single message', () => {
			const result = vercelFormatAdapter.parseRequest({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [
							{ type: 'text', text: 'hello ' },
							{ type: 'text', text: 'world' },
						],
					},
				],
			});

			expect(result.messages[0].content).to.equal('hello world');
		});

		it('translates tool definitions from a record into a list', () => {
			const result = vercelFormatAdapter.parseRequest({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [{ type: 'text', text: 'what is the weather?' }],
					},
				],
				tools: {
					weather: {
						description: 'Get the weather for a location',
						inputSchema: {
							type: 'object',
							properties: { location: { type: 'string' } },
						},
					},
				},
			});

			expect(result.tools).to.deep.equal([
				{
					name: 'weather',
					description: 'Get the weather for a location',
					parameters: {
						type: 'object',
						properties: { location: { type: 'string' } },
					},
				},
			]);
		});

		it('translates file parts into image content parts', () => {
			const result = vercelFormatAdapter.parseRequest({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [
							{ type: 'text', text: 'describe this' },
							{
								type: 'file',
								url: 'data:image/png;base64,AAA',
								mediaType: 'image/png',
							},
						],
					},
				],
			});

			expect(result.messages[0].content).to.deep.equal([
				{ type: 'text', text: 'describe this' },
				{
					type: 'image',
					image: 'data:image/png;base64,AAA',
					mediaType: 'image/png',
				},
			]);
		});

		it('does not prepend an empty text part for an image-only message', () => {
			const result = vercelFormatAdapter.parseRequest({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [
							{
								type: 'file',
								url: 'data:image/png;base64,AAA',
								mediaType: 'image/png',
							},
						],
					},
				],
			});

			expect(result.messages[0].content).to.deep.equal([
				{
					type: 'image',
					image: 'data:image/png;base64,AAA',
					mediaType: 'image/png',
				},
			]);
		});

		it('translates non-image file parts (e.g. PDFs) into file content parts', () => {
			const result = vercelFormatAdapter.parseRequest({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [
							{ type: 'text', text: 'see attached' },
							{
								type: 'file',
								url: 'data:application/pdf;base64,AAA',
								mediaType: 'application/pdf',
								filename: 'report.pdf',
							},
						],
					},
				],
			});

			expect(result.messages[0].content).to.deep.equal([
				{ type: 'text', text: 'see attached' },
				{
					type: 'file',
					data: 'data:application/pdf;base64,AAA',
					mediaType: 'application/pdf',
					filename: 'report.pdf',
				},
			]);
		});

		it('translates a PDF-only message without a leading empty text part', () => {
			const result = vercelFormatAdapter.parseRequest({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'user',
						parts: [
							{
								type: 'file',
								url: 'data:application/pdf;base64,AAA',
								mediaType: 'application/pdf',
							},
						],
					},
				],
			});

			expect(result.messages[0].content).to.deep.equal([
				{
					type: 'file',
					data: 'data:application/pdf;base64,AAA',
					mediaType: 'application/pdf',
					filename: undefined,
				},
			]);
		});

		it('splits a completed tool part out into a separate tool-role message', () => {
			const result = vercelFormatAdapter.parseRequest({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'assistant',
						parts: [
							{ type: 'text', text: 'let me check' },
							{
								type: 'tool-weather',
								toolCallId: 'call_1',
								state: 'output-available',
								input: { location: 'Berlin' },
								output: { tempC: 20 },
							} as any,
						],
					},
				],
			});

			expect(result.messages).to.deep.equal([
				{ role: 'assistant', content: 'let me check' },
				{
					role: 'tool',
					content: JSON.stringify({ tempC: 20 }),
					toolCallId: 'call_1',
					toolName: 'weather',
				},
			]);
		});

		it('ignores tool parts that have not produced output yet', () => {
			const result = vercelFormatAdapter.parseRequest({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						id: 'msg-1',
						role: 'assistant',
						parts: [
							{
								type: 'tool-weather',
								toolCallId: 'call_1',
								state: 'input-available',
								input: { location: 'Berlin' },
							} as any,
						],
					},
				],
			});

			expect(result.messages).to.deep.equal([]);
		});

		it('passes through the customProvider override', () => {
			const result = vercelFormatAdapter.parseRequest({
				provider: 'mycompany',
				model: 'custom-gpt-4',
				messages: [
					{ id: 'msg-1', role: 'user', parts: [{ type: 'text', text: 'hi' }] },
				],
				customProvider: {
					baseUrl: 'https://api.mycompany.com',
					apiKey: 'sk-xxx',
				},
			});

			expect(result.customProvider).to.deep.equal({
				baseUrl: 'https://api.mycompany.com',
				apiKey: 'sk-xxx',
			});
		});

		it('rejects a customProvider override targeting a loopback/private address', () => {
			expect(() =>
				vercelFormatAdapter.parseRequest({
					provider: 'mycompany',
					model: 'custom-gpt-4',
					messages: [
						{
							id: 'msg-1',
							role: 'user',
							parts: [{ type: 'text', text: 'hi' }],
						},
					],
					customProvider: {
						baseUrl: 'http://169.254.169.254/latest/meta-data',
						apiKey: 'sk-xxx',
					},
				})
			).to.throw(/disallowed/);
		});

		it('rejects a customProvider override with an empty baseUrl', () => {
			expect(() =>
				vercelFormatAdapter.parseRequest({
					provider: 'mycompany',
					model: 'custom-gpt-4',
					messages: [
						{
							id: 'msg-1',
							role: 'user',
							parts: [{ type: 'text', text: 'hi' }],
						},
					],
					customProvider: { baseUrl: '', apiKey: 'sk-xxx' },
				})
			).to.throw('"customProvider.baseUrl" is required');
		});

		it('rejects a customProvider override with an empty apiKey', () => {
			expect(() =>
				vercelFormatAdapter.parseRequest({
					provider: 'mycompany',
					model: 'custom-gpt-4',
					messages: [
						{
							id: 'msg-1',
							role: 'user',
							parts: [{ type: 'text', text: 'hi' }],
						},
					],
					customProvider: { baseUrl: 'https://api.mycompany.com', apiKey: '' },
				})
			).to.throw('"customProvider.apiKey" is required');
		});

		it('throws when provider is missing', () => {
			expect(() =>
				vercelFormatAdapter.parseRequest({
					model: 'gpt-4o',
					messages: [
						{ id: 'msg-1', role: 'user', parts: [{ type: 'text', text: 'hi' }] },
					],
				} as any)
			).to.throw('"provider" is required');
		});

		it('throws when model is missing', () => {
			expect(() =>
				vercelFormatAdapter.parseRequest({
					provider: 'openai',
					messages: [
						{ id: 'msg-1', role: 'user', parts: [{ type: 'text', text: 'hi' }] },
					],
				} as any)
			).to.throw('"model" is required');
		});

		it('throws when messages is missing or empty', () => {
			expect(() =>
				vercelFormatAdapter.parseRequest({
					provider: 'openai',
					model: 'gpt-4o',
					messages: [],
				} as any)
			).to.throw('"messages" is required');
		});

		it('throws when a message is missing an id', () => {
			expect(() =>
				vercelFormatAdapter.parseRequest({
					provider: 'openai',
					model: 'gpt-4o',
					messages: [{ role: 'user', parts: [{ type: 'text', text: 'hi' }] }],
				} as any)
			).to.throw('must have a non-empty string "id"');
		});

		it('throws when a message role is invalid', () => {
			expect(() =>
				vercelFormatAdapter.parseRequest({
					provider: 'openai',
					model: 'gpt-4o',
					messages: [
						{
							id: 'msg-1',
							role: 'tool',
							parts: [{ type: 'text', text: 'hi' }],
						},
					],
				} as any)
			).to.throw('Message "role" must be one of');
		});

		it('throws when a message is missing a parts array', () => {
			expect(() =>
				vercelFormatAdapter.parseRequest({
					provider: 'openai',
					model: 'gpt-4o',
					messages: [{ id: 'msg-1', role: 'user', content: 'hi' }],
				} as any)
			).to.throw('must have a "parts" array');
		});

		it('throws when the input is not an object', () => {
			expect(() => vercelFormatAdapter.parseRequest(null as any)).to.throw(
				'must be a JSON object'
			);
		});
	});

	describe('formatResponse', () => {
		it('formats a full response including tool calls', () => {
			const response: GenerateResponse = {
				text: 'hello there',
				finishReason: 'stop',
				usage: { inputTokens: 3, outputTokens: 4, totalTokens: 7 },
				cost: 0.0012,
				provider: 'openai',
				model: 'gpt-4o',
				toolCalls: [
					{
						toolCallId: 'call_1',
						toolName: 'weather',
						args: { location: 'Berlin' },
					},
				],
				raw: { any: 'thing' },
				viaGatewayBypass: false,
			};

			expect(vercelFormatAdapter.formatResponse(response)).to.deep.equal({
				text: 'hello there',
				finishReason: 'stop',
				usage: { inputTokens: 3, outputTokens: 4, totalTokens: 7 },
				cost: 0.0012,
				provider: 'openai',
				model: 'gpt-4o',
				toolCalls: [
					{
						toolCallId: 'call_1',
						toolName: 'weather',
						input: { location: 'Berlin' },
					},
				],
				raw: { any: 'thing' },
				viaGatewayBypass: false,
			});
		});

		it('omits toolCalls when there are none', () => {
			const response: GenerateResponse = {
				text: 'hi',
				finishReason: 'stop',
				usage: {},
				provider: 'openai',
				model: 'gpt-4o',
			};

			expect(vercelFormatAdapter.formatResponse(response).toolCalls).to.equal(
				undefined
			);
		});
	});
});
