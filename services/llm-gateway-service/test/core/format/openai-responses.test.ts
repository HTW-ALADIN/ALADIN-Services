import { expect } from 'chai';
import { openaiResponsesFormatAdapter } from '../../../src/core/format/openai-responses.js';
import type { GenerateResponse } from '../../../src/core/types.js';

describe('openaiResponsesFormatAdapter', () => {
	describe('parseRequest', () => {
		it('parses a minimal request with a string input', () => {
			const result = openaiResponsesFormatAdapter.parseRequest({
				format: 'openai-responses',
				provider: 'openai',
				model: 'gpt-4o',
				input: 'hello',
			});

			expect(result).to.deep.equal({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [{ role: 'user', content: 'hello' }],
				system: undefined,
				tools: undefined,
				temperature: undefined,
				maxOutputTokens: undefined,
				topP: undefined,
				metadata: undefined,
				customProvider: undefined,
			});
		});

		it('maps instructions onto the internal system prompt', () => {
			const result = openaiResponsesFormatAdapter.parseRequest({
				format: 'openai-responses',
				provider: 'openai',
				model: 'gpt-4o',
				input: 'hello',
				instructions: 'Be concise.',
			});

			expect(result.system).to.equal('Be concise.');
		});

		it('parses an array input with messages and image content', () => {
			const result = openaiResponsesFormatAdapter.parseRequest({
				format: 'openai-responses',
				provider: 'openai',
				model: 'gpt-4o',
				input: [
					{
						role: 'user',
						content: [
							{ type: 'input_text', text: 'describe this' },
							{ type: 'input_image', image_url: 'https://example.com/a.png' },
						],
					},
				],
			});

			expect(result.messages).to.deep.equal([
				{
					role: 'user',
					content: [
						{ type: 'text', text: 'describe this' },
						{ type: 'image', image: 'https://example.com/a.png' },
					],
				},
			]);
		});

		it('translates a function_call_output item into a tool-role message', () => {
			const result = openaiResponsesFormatAdapter.parseRequest({
				format: 'openai-responses',
				provider: 'openai',
				model: 'gpt-4o',
				input: [
					{ role: 'user', content: 'what is the weather?' },
					{
						type: 'function_call_output',
						call_id: 'call_1',
						output: '{"tempC":20}',
					},
				],
			});

			expect(result.messages).to.deep.equal([
				{ role: 'user', content: 'what is the weather?' },
				{
					role: 'tool',
					content: '{"tempC":20}',
					toolCallId: 'call_1',
				},
			]);
		});

		it('translates function tool definitions', () => {
			const result = openaiResponsesFormatAdapter.parseRequest({
				format: 'openai-responses',
				provider: 'openai',
				model: 'gpt-4o',
				input: 'what is the weather?',
				tools: [
					{
						type: 'function',
						name: 'weather',
						description: 'Get the weather for a location',
						parameters: {
							type: 'object',
							properties: { location: { type: 'string' } },
						},
					},
				],
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

		it('maps temperature, max_output_tokens, and top_p', () => {
			const result = openaiResponsesFormatAdapter.parseRequest({
				format: 'openai-responses',
				provider: 'openai',
				model: 'gpt-4o',
				input: 'hello',
				temperature: 0.4,
				max_output_tokens: 200,
				top_p: 0.8,
			});

			expect(result.temperature).to.equal(0.4);
			expect(result.maxOutputTokens).to.equal(200);
			expect(result.topP).to.equal(0.8);
		});

		it('passes through the customProvider override', () => {
			const result = openaiResponsesFormatAdapter.parseRequest({
				format: 'openai-responses',
				provider: 'mycompany',
				model: 'custom-gpt-4',
				input: 'hi',
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
				openaiResponsesFormatAdapter.parseRequest({
					format: 'openai-responses',
					provider: 'mycompany',
					model: 'custom-gpt-4',
					input: 'hi',
					customProvider: {
						baseUrl: 'http://169.254.169.254/latest/meta-data',
						apiKey: 'sk-xxx',
					},
				})
			).to.throw(/disallowed/);
		});

		it('throws when provider is missing', () => {
			expect(() =>
				openaiResponsesFormatAdapter.parseRequest({
					format: 'openai-responses',
					model: 'gpt-4o',
					input: 'hi',
				} as any)
			).to.throw('"provider" is required');
		});

		it('throws when model is missing', () => {
			expect(() =>
				openaiResponsesFormatAdapter.parseRequest({
					format: 'openai-responses',
					provider: 'openai',
					input: 'hi',
				} as any)
			).to.throw('"model" is required');
		});

		it('throws when input is missing', () => {
			expect(() =>
				openaiResponsesFormatAdapter.parseRequest({
					format: 'openai-responses',
					provider: 'openai',
					model: 'gpt-4o',
				} as any)
			).to.throw('"input" is required');
		});

		it('throws when input is an empty array', () => {
			expect(() =>
				openaiResponsesFormatAdapter.parseRequest({
					format: 'openai-responses',
					provider: 'openai',
					model: 'gpt-4o',
					input: [],
				} as any)
			).to.throw('must not be an empty array');
		});

		it('throws when the input is not an object', () => {
			expect(() =>
				openaiResponsesFormatAdapter.parseRequest(null as any)
			).to.throw('must be a JSON object');
		});
	});

	describe('formatResponse', () => {
		it('formats a full response including function calls', () => {
			const response: GenerateResponse = {
				text: 'hello there',
				finishReason: 'tool-calls',
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

			const result = openaiResponsesFormatAdapter.formatResponse(response);

			expect(result.object).to.equal('response');
			expect(result.model).to.equal('gpt-4o');
			expect(result.provider).to.equal('openai');
			expect(result.status).to.equal('completed');
			expect(result.output_text).to.equal('hello there');
			expect(result.output).to.deep.equal([
				{
					type: 'message',
					role: 'assistant',
					content: [{ type: 'output_text', text: 'hello there' }],
				},
				{
					type: 'function_call',
					call_id: 'call_1',
					name: 'weather',
					arguments: JSON.stringify({ location: 'Berlin' }),
				},
			]);
			expect(result.usage).to.deep.equal({
				input_tokens: 3,
				output_tokens: 4,
				total_tokens: 7,
			});
			expect(result.cost).to.equal(0.0012);
		});

		it('omits the message output item when text is empty', () => {
			const response: GenerateResponse = {
				text: '',
				finishReason: 'stop',
				usage: {},
				provider: 'openai',
				model: 'gpt-4o',
			};

			const result = openaiResponsesFormatAdapter.formatResponse(response);
			expect(result.output).to.deep.equal([]);
			expect(result.output_text).to.equal('');
		});

		it('maps the length finish reason to an incomplete status', () => {
			const response: GenerateResponse = {
				text: 'partial',
				finishReason: 'length',
				usage: {},
				provider: 'openai',
				model: 'gpt-4o',
			};

			const result = openaiResponsesFormatAdapter.formatResponse(response);
			expect(result.status).to.equal('incomplete');
		});
	});
});
