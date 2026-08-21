import { describe, it, expect } from 'vitest';
import {
	isUsableLlmGatewayBlock,
	redactLlmGatewayBlock,
} from '../../../src/shared/llm-gateway/llm-gateway-config';

describe('isUsableLlmGatewayBlock', () => {
	it('accepts a block with endpoint and apiKey', () => {
		expect(
			isUsableLlmGatewayBlock({
				endpoint: 'http://gateway:8080',
				apiKey: 'secret',
			}),
		).toBe(true);
	});

	it('accepts a block with optional provider and model overrides', () => {
		expect(
			isUsableLlmGatewayBlock({
				endpoint: 'http://gateway:8080',
				apiKey: 'secret',
				provider: 'anthropic',
				model: 'claude-3-haiku',
			}),
		).toBe(true);
	});

	it('accepts a block with a customProvider override', () => {
		expect(
			isUsableLlmGatewayBlock({
				endpoint: 'http://gateway:8080',
				apiKey: 'secret',
				customProvider: {
					baseUrl: 'https://custom.example.com/v1',
					apiKey: 'custom-key',
				},
			}),
		).toBe(true);
	});

	it('rejects a block with an incomplete customProvider override', () => {
		expect(
			isUsableLlmGatewayBlock({
				endpoint: 'http://gateway:8080',
				apiKey: 'secret',
				customProvider: { baseUrl: '' },
			}),
		).toBe(false);
		expect(
			isUsableLlmGatewayBlock({
				endpoint: 'http://gateway:8080',
				apiKey: 'secret',
				customProvider: { baseUrl: 'https://x', apiKey: '' },
			}),
		).toBe(false);
	});

	it('rejects non-objects and null', () => {
		expect(isUsableLlmGatewayBlock(undefined)).toBe(false);
		expect(isUsableLlmGatewayBlock(null)).toBe(false);
		expect(isUsableLlmGatewayBlock('http://x')).toBe(false);
		expect(isUsableLlmGatewayBlock(42)).toBe(false);
	});

	it('rejects a block without an endpoint', () => {
		expect(isUsableLlmGatewayBlock({ apiKey: 'secret' })).toBe(false);
	});

	it('rejects a block without an apiKey', () => {
		expect(isUsableLlmGatewayBlock({ endpoint: 'http://gateway:8080' })).toBe(
			false,
		);
	});

	it('rejects empty-string endpoint or apiKey', () => {
		expect(
			isUsableLlmGatewayBlock({ endpoint: '', apiKey: 'secret' }),
		).toBe(false);
		expect(
			isUsableLlmGatewayBlock({ endpoint: 'http://x', apiKey: '   ' }),
		).toBe(false);
	});

	it('rejects non-string provider/model values', () => {
		expect(
			isUsableLlmGatewayBlock({
				endpoint: 'http://x',
				apiKey: 'secret',
				provider: 42,
			}),
		).toBe(false);
	});
});

describe('redactLlmGatewayBlock', () => {
	it('replaces apiKey values in an llmGateway block', () => {
		const redacted = redactLlmGatewayBlock({
			connectionInfo: { type: 'pglite', databaseId: 'db' },
			llmGateway: { endpoint: 'http://x', apiKey: 'super-secret' },
		});
		expect(redacted.llmGateway.apiKey).toBe('[REDACTED]');
		expect(redacted.llmGateway.endpoint).toBe('http://x');
	});

	it('replaces apiKey values in nested objects and arrays', () => {
		const redacted = redactLlmGatewayBlock({
			list: [{ llmGateway: { endpoint: 'http://x', apiKey: 'a' } }],
		});
		expect((redacted.list as any)[0].llmGateway.apiKey).toBe('[REDACTED]');
	});

	it('replaces apiKey values inside a customProvider override', () => {
		const redacted = redactLlmGatewayBlock({
			llmGateway: {
				endpoint: 'http://x',
				apiKey: 'gateway-key',
				customProvider: { baseUrl: 'https://x', apiKey: 'custom-key' },
			},
		});
		expect(redacted.llmGateway.apiKey).toBe('[REDACTED]');
		expect(redacted.llmGateway.customProvider.apiKey).toBe('[REDACTED]');
		expect(redacted.llmGateway.customProvider.baseUrl).toBe('https://x');
	});

	it('leaves values without apiKey untouched', () => {
		const input = { foo: 'bar', n: 42 };
		expect(redactLlmGatewayBlock(input)).toEqual(input);
	});
});
