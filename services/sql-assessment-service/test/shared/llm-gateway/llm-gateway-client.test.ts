import { afterEach, describe, expect, it, vi } from 'vitest';
import {
	LlmGatewayClient,
	LlmGatewayRequestError,
	toGatewayChatMessage,
} from '../../../src/shared/llm-gateway/llm-gateway-client';

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' },
	});
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('LlmGatewayClient', () => {
	const client = new LlmGatewayClient();
	const config = { endpoint: 'http://gateway:8080', apiKey: 'secret-key' };

	it('POSTs a UIMessage-shaped GenerateRequest body and returns the text field', async () => {
		const fetchMock = vi.fn().mockResolvedValue(
			jsonResponse({ text: 'Describe the query.', finishReason: 'stop' }),
		);
		vi.stubGlobal('fetch', fetchMock);

		const result = await client.generate(config, {
			provider: 'openai',
			model: 'gpt-4o-mini',
			messages: [
				{
					id: 'm1',
					role: 'system',
					parts: [{ type: 'text', text: 'You are an expert.' }],
				},
			],
			temperature: 0,
		});

		expect(result).toBe('Describe the query.');
		expect(fetchMock).toHaveBeenCalledTimes(1);
		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe('http://gateway:8080/generate');
		expect(init.method).toBe('POST');
		expect(init.headers.Authorization).toBe('Bearer secret-key');
		const body = JSON.parse(init.body);
		expect(body.provider).toBe('openai');
		expect(body.model).toBe('gpt-4o-mini');
		expect(body.messages).toEqual([
			{
				id: 'm1',
				role: 'system',
				parts: [{ type: 'text', text: 'You are an expert.' }],
			},
		]);
		expect(body.temperature).toBe(0);
	});

	it('applies service-side defaults when provider/model are omitted', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ text: 'ok' }));
		vi.stubGlobal('fetch', fetchMock);

		await client.generate(config, {
			messages: [{ id: 'm1', role: 'system', parts: [] }],
		});

		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.provider).toBe('openai');
		expect(body.model).toBe('gpt-4o-mini');
		expect(body.temperature).toBeUndefined();
		expect(body.system).toBeUndefined();
	});

	it('lets per-request overrides win over config and defaults', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ text: 'ok' }));
		vi.stubGlobal('fetch', fetchMock);

		await client.generate(
			{ ...config, provider: 'config-provider', model: 'config-model' },
			{
				provider: 'request-provider',
				model: 'request-model',
				messages: [],
			},
		);

		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.provider).toBe('request-provider');
		expect(body.model).toBe('request-model');
	});

	it('passes the optional system prompt through', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ text: 'ok' }));
		vi.stubGlobal('fetch', fetchMock);

		await client.generate(config, {
			messages: [{ id: 'm1', role: 'user', parts: [] }],
			system: 'Answer in German.',
		});

		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.system).toBe('Answer in German.');
	});

	it('forwards a customProvider override to the gateway', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ text: 'ok' }));
		vi.stubGlobal('fetch', fetchMock);

		await client.generate(config, {
			messages: [{ id: 'm1', role: 'system', parts: [] }],
			customProvider: {
				baseUrl: 'https://custom.example.com/v1',
				apiKey: 'custom-key',
			},
		});

		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.customProvider).toEqual({
			baseUrl: 'https://custom.example.com/v1',
			apiKey: 'custom-key',
		});
	});

	it('forwards a customProvider override supplied on the config', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ text: 'ok' }));
		vi.stubGlobal('fetch', fetchMock);

		await client.generate(
			{
				...config,
				customProvider: {
					baseUrl: 'https://config-custom.example.com/v1',
					apiKey: 'config-custom-key',
				},
			},
			{ messages: [{ id: 'm1', role: 'system', parts: [] }] },
		);

		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.customProvider).toEqual({
			baseUrl: 'https://config-custom.example.com/v1',
			apiKey: 'config-custom-key',
		});
	});

	it('prefers a request-level customProvider over the config one', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ text: 'ok' }));
		vi.stubGlobal('fetch', fetchMock);

		await client.generate(
			{
				...config,
				customProvider: {
					baseUrl: 'https://config.example.com/v1',
					apiKey: 'config-key',
				},
			},
			{
				messages: [{ id: 'm1', role: 'system', parts: [] }],
				customProvider: {
					baseUrl: 'https://request.example.com/v1',
					apiKey: 'request-key',
				},
			},
		);

		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.customProvider.baseUrl).toBe('https://request.example.com/v1');
	});

	it('does not include customProvider when absent', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ text: 'ok' }));
		vi.stubGlobal('fetch', fetchMock);

		await client.generate(config, {
			messages: [{ id: 'm1', role: 'system', parts: [] }],
		});

		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.customProvider).toBeUndefined();
	});

	it('strips trailing slashes from the endpoint', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ text: 'ok' }));
		vi.stubGlobal('fetch', fetchMock);

		await client.generate({ ...config, endpoint: 'http://x:8080//' }, {
			messages: [],
		});

		expect(fetchMock.mock.calls[0][0]).toBe('http://x:8080/generate');
	});

	it('propagates non-2xx responses as a typed error with the upstream message', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockImplementation(() =>
				Promise.resolve(jsonResponse({ message: 'upstream exploded' }, 500)),
			),
		);

		try {
			await client.generate(config, { messages: [] });
			expect.unreachable('expected the call to fail');
		} catch (error) {
			expect(error).toBeInstanceOf(LlmGatewayRequestError);
			expect(String((error as Error).message)).toMatch(/upstream exploded/);
		}
	});

	it('throws a typed error when the response is missing the text field', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(jsonResponse({ finishReason: 'stop' })),
		);

		await expect(client.generate(config, { messages: [] })).rejects.toThrow(
			/missing the text field/,
		);
	});

	it('throws a typed error on network failure', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockRejectedValue(new Error('ECONNREFUSED')),
		);

		await expect(client.generate(config, { messages: [] })).rejects.toThrow(
			/ECONNREFUSED/,
		);
	});

	it('never includes the api key in error messages', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(jsonResponse({ message: 'boom' }, 502)),
		);

		try {
			await client.generate(config, { messages: [] });
			expect.unreachable('expected the call to fail');
		} catch (error) {
			expect(error).toBeInstanceOf(LlmGatewayRequestError);
			expect(String((error as Error).message)).not.toContain('secret-key');
		}
	});
});

describe('toGatewayChatMessage', () => {
	it('produces a UIMessage with a unique id, role, and text parts', () => {
		const message = toGatewayChatMessage('system', 'Be helpful.');
		expect(typeof message.id).toBe('string');
		expect(message.id.length).toBeGreaterThan(0);
		expect(message.role).toBe('system');
		expect(message.parts).toEqual([{ type: 'text', text: 'Be helpful.' }]);
	});

	it('generates distinct ids across messages', () => {
		const a = toGatewayChatMessage('system', 'one');
		const b = toGatewayChatMessage('system', 'two');
		expect(a.id).not.toBe(b.id);
	});
});
