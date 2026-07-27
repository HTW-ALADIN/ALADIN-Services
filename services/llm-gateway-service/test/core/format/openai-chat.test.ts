import { expect } from 'chai';
import { openaiChatFormatAdapter } from '../../../src/core/format/openai-chat.js';
import type { GenerateResponse } from '../../../src/core/types.js';

describe('openaiChatFormatAdapter', () => {
	describe('parseRequest', () => {
		it('parses a minimal request', () => {
			const result = openaiChatFormatAdapter.parseRequest({
				format: 'openai-chat',
				provider: 'openai',
				model: 'gpt-4o',
				messages: [{ role: 'user', content: 'hello' }],
			});

			expect(result).to.deep.equal({
				provider: 'openai',
				model: 'gpt-4o',
				messages: [{ role: 'user', content: 'hello', toolCallId: undefined }],
				tools: undefined,
				temperature: undefined,
				maxOutputTokens: undefined,
				topP: undefined,
				stopSequences: undefined,
				metadata: undefined,
				customProvider: undefined,
			});
		});

		it('maps temperature, max_tokens, top_p, and stop', () => {
			const result = openaiChatFormatAdapter.parseRequest({
				format: 'openai-chat',
				provider: 'openai',
				model: 'gpt-4o',
				messages: [{ role: 'user', content: 'hello' }],
				temperature: 0.5,
				max_tokens: 100,
				top_p: 0.9,
				stop: ['\n'],
			});

			expect(result.temperature).to.equal(0.5);
			expect(result.maxOutputTokens).to.equal(100);
			expect(result.topP).to.equal(0.9);
			expect(result.stopSequences).to.deep.equal(['\n']);
		});

		it('normalizes a single stop string into an array', () => {
			const result = openaiChatFormatAdapter.parseRequest({
				format: 'openai-chat',
				provider: 'openai',
				model: 'gpt-4o',
				messages: [{ role: 'user', content: 'hello' }],
				stop: '\n',
			});

			expect(result.stopSequences).to.deep.equal(['\n']);
		});

		it('translates function tool definitions', () => {
			const result = openaiChatFormatAdapter.parseRequest({
				format: 'openai-chat',
				provider: 'openai',
				model: 'gpt-4o',
				messages: [{ role: 'user', content: 'what is the weather?' }],
				tools: [
					{
						type: 'function',
						function: {
							name: 'weather',
							description: 'Get the weather for a location',
							parameters: {
								type: 'object',
								properties: { location: { type: 'string' } },
							},
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

		it('translates image_url content parts', () => {
			const result = openaiChatFormatAdapter.parseRequest({
				format: 'openai-chat',
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{
						role: 'user',
						content: [
							{ type: 'text', text: 'describe this' },
							{
								type: 'image_url',
								image_url: { url: 'data:image/png;base64,AAA' },
							},
						],
					},
				],
			});

			expect(result.messages[0].content).to.deep.equal([
				{ type: 'text', text: 'describe this' },
				{ type: 'image', image: 'data:image/png;base64,AAA' },
			]);
		});

		it('carries the tool_call_id through for tool-role messages', () => {
			const result = openaiChatFormatAdapter.parseRequest({
				format: 'openai-chat',
				provider: 'openai',
				model: 'gpt-4o',
				messages: [
					{ role: 'user', content: 'what is the weather?' },
					{
						role: 'assistant',
						content: null,
						tool_calls: [
							{
								id: 'call_1',
								type: 'function',
								function: { name: 'weather', arguments: '{}' },
							},
						],
					},
					{
						role: 'tool',
						content: '{"tempC":20}',
						tool_call_id: 'call_1',
					},
				],
			});

			expect(result.messages[1]).to.deep.equal({
				role: 'assistant',
				content: '',
				toolCallId: undefined,
			});
			expect(result.messages[2]).to.deep.equal({
				role: 'tool',
				content: '{"tempC":20}',
				toolCallId: 'call_1',
			});
		});

		it('passes through the customProvider override', () => {
			const result = openaiChatFormatAdapter.parseRequest({
				format: 'openai-chat',
				provider: 'mycompany',
				model: 'custom-gpt-4',
				messages: [{ role: 'user', content: 'hi' }],
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
				openaiChatFormatAdapter.parseRequest({
					format: 'openai-chat',
					provider: 'mycompany',
					model: 'custom-gpt-4',
					messages: [{ role: 'user', content: 'hi' }],
					customProvider: {
						baseUrl: 'http://169.254.169.254/latest/meta-data',
						apiKey: 'sk-xxx',
					},
				})
			).to.throw(/disallowed/);
		});

		it('throws when provider is missing', () => {
			expect(() =>
				openaiChatFormatAdapter.parseRequest({
					format: 'openai-chat',
					model: 'gpt-4o',
					messages: [{ role: 'user', content: 'hi' }],
				} as any)
			).to.throw('"provider" is required');
		});

		it('throws when model is missing', () => {
			expect(() =>
				openaiChatFormatAdapter.parseRequest({
					format: 'openai-chat',
					provider: 'openai',
					messages: [{ role: 'user', content: 'hi' }],
				} as any)
			).to.throw('"model" is required');
		});

		it('throws when messages is missing or empty', () => {
			expect(() =>
				openaiChatFormatAdapter.parseRequest({
					format: 'openai-chat',
					provider: 'openai',
					model: 'gpt-4o',
					messages: [],
				} as any)
			).to.throw('"messages" is required');
		});

		it('throws when the input is not an object', () => {
			expect(() =>
				openaiChatFormatAdapter.parseRequest(null as any)
			).to.throw('must be a JSON object');
		});
	});

	describe('formatResponse', () => {
		it('formats a full response including tool calls', () => {
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

			const result = openaiChatFormatAdapter.formatResponse(response);

			expect(result.object).to.equal('chat.completion');
			expect(result.model).to.equal('gpt-4o');
			expect(result.provider).to.equal('openai');
			expect(result.choices).to.deep.equal([
				{
					index: 0,
					message: {
						role: 'assistant',
						content: 'hello there',
						tool_calls: [
							{
								id: 'call_1',
								type: 'function',
								function: {
									name: 'weather',
									arguments: JSON.stringify({ location: 'Berlin' }),
								},
							},
						],
					},
					finish_reason: 'tool_calls',
				},
			]);
			expect(result.usage).to.deep.equal({
				prompt_tokens: 3,
				completion_tokens: 4,
				total_tokens: 7,
			});
			expect(result.cost).to.equal(0.0012);
		});

		it('uses null content when the response text is empty', () => {
			const response: GenerateResponse = {
				text: '',
				finishReason: 'stop',
				usage: {},
				provider: 'openai',
				model: 'gpt-4o',
			};

			const result = openaiChatFormatAdapter.formatResponse(response);
			expect(result.choices[0].message.content).to.equal(null);
			expect(result.choices[0].finish_reason).to.equal('stop');
		});
	});
});
