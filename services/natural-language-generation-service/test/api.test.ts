import { expect } from 'chai';
import { describe, it } from 'node:test';
import { buildServer } from '../src/api/server.js';
import { DEFAULT_LIMITS } from '../src/config.js';
import { realize } from '../src/realizer.js';
import { resetWorkerPool } from '../src/worker-runner.js';
import { englishRequest, templateRequest } from './fixtures.js';

describe('REST API', () => {
	it('serves health, discovery, and OpenAPI endpoints', async () => {
		const server = await buildServer();
		await server.ready();

		const health = await server.inject({ method: 'GET', url: '/healthz' });
		expect(health.statusCode).to.equal(200);
		expect(health.json()).to.deep.equal({ status: 'ok' });

		const discovery = await server.inject({
			method: 'GET',
			url: '/v1/capabilities',
		});
		expect(discovery.json().coverage.percentage).to.equal(100);
		expect(discovery.json().modes).to.have.keys([
			'surface_realization',
			'template_generation',
		]);

		const openapi = await server.inject({
			method: 'GET',
			url: '/api-docs/openapi.json',
		});
		expect(openapi.statusCode).to.equal(200);
		const document = openapi.json();
		expect(document.openapi).to.equal('3.1.0');
		expect(document.paths).to.have.property('/v1/generate');
		expect(document.paths['/v1/generate'].post.operationId).to.equal(
			'generateText'
		);
		expect(
			document.paths['/v1/generate'].post.requestBody.content[
				'application/json'
			].schema.discriminator.propertyName
		).to.equal('mode');
		expect(
			document.paths['/v1/generate'].post.responses['200'].content
		).to.have.keys(['application/json', 'text/plain']);
		for (const status of ['400', '413', '415', '422', '429', '500']) {
			expect(
				document.paths['/v1/generate'].post.responses[status].content
			).to.have.keys(['application/problem+json']);
		}

		const references = [
			...JSON.stringify(document).matchAll(/"\$ref":"#\/([^"]+)"/g),
		]
			.map((match) => match[1])
			.filter((reference): reference is string => reference !== undefined);
		expect(references).not.to.have.length(0);
		for (const pointer of references) {
			const target = pointer
				.split('/')
				.reduce<unknown>((value, encodedPart) => {
					if (value === null || typeof value !== 'object') return undefined;
					const part = encodedPart.replaceAll('~1', '/').replaceAll('~0', '~');
					return (value as Record<string, unknown>)[part];
				}, document);
			expect(target, `unresolved OpenAPI reference: #/${pointer}`).not.to.equal(
				undefined
			);
		}
		await server.close();
	});

	it('returns JSON or plain text from the generation endpoint', async () => {
		const server = await buildServer();
		const json = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			payload: englishRequest(),
		});
		expect(json.statusCode).to.equal(200);
		expect(json.json().text).to.equal('The cat chases the mouse.');

		const text = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			headers: { accept: 'text/plain' },
			payload: englishRequest(),
		});
		expect(text.headers['content-type']).to.contain('text/plain');
		expect(text.body).to.equal('The cat chases the mouse.');

		const template = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			payload: templateRequest(),
		});
		expect(template.statusCode).to.equal(200);
		expect(template.json()).to.include({
			text: '<p>Hello Alice!</p>',
			mode: 'template_generation',
			backend: 'rosaenlg',
		});
		await server.close();
	});

	it('returns problem details for validation, body, and realization failures', async () => {
		const server = await buildServer({
			limits: { ...DEFAULT_LIMITS, maxBodyBytes: 400 },
		});
		const invalid = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			payload: { expression: 'S(N("cat"))' },
		});
		expect(invalid.statusCode).to.equal(400);
		expect(invalid.headers['content-type']).to.contain(
			'application/problem+json'
		);
		expect(invalid.json().code).to.equal('invalid-request');
		const invalidChild = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			payload: {
				...englishRequest(),
				input: {
					representation: 'constituent',
					structure: { phrase: 'S', elements: [null] },
				},
			},
		});
		expect(invalidChild.statusCode).to.equal(400);
		expect(invalidChild.json().code).to.equal('invalid-request');

		const malformed = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			headers: { 'content-type': 'application/json' },
			payload: '{not-json',
		});
		expect(malformed.statusCode).to.equal(400);

		const tooLarge = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			headers: { 'content-type': 'application/json' },
			payload: JSON.stringify({ padding: 'x'.repeat(500) }),
		});
		expect(tooLarge.statusCode).to.equal(413);
		expect(tooLarge.json().code).to.equal('payload-too-large');
		await server.close();
	});

	it('enforces structure depth before recursive schema validation', async () => {
		const server = await buildServer({
			limits: { ...DEFAULT_LIMITS, maxDepth: 2 },
		});
		const response = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			payload: englishRequest(),
		});
		expect(response.statusCode).to.equal(422);
		expect(response.json().code).to.equal('resource-limit');
		await server.close();
	});

	it('terminates template workers that exceed their execution limit', async () => {
		const server = await buildServer({
			limits: { ...DEFAULT_LIMITS, templateTimeoutMs: 100 },
		});
		const payload = templateRequest();
		payload.input.template = '- while (true) {}';
		const response = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			payload,
		});
		expect(response.statusCode).to.equal(422);
		expect(response.json().code).to.equal('resource-limit');

		const health = await server.inject({ method: 'GET', url: '/healthz' });
		expect(health.statusCode).to.equal(200);
		await server.close();
	});

	it('applies the same strict validation as the CLI', async () => {
		const server = await buildServer();
		const smuggled = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			payload: {
				...englishRequest(),
				input: {
					representation: 'constituent',
					structure: {
						terminal: 'N',
						lemma: 'cat',
						props: { eval: 'x' },
					},
				},
			},
		});
		expect(smuggled.statusCode).to.equal(400);
		expect(smuggled.json().code).to.equal('invalid-request');

		const coerced = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			payload: {
				...templateRequest(),
				input: {
					template: 'p Hello #{name}!',
					data: { name: 'Alice' },
					seed: '5',
				},
			},
		});
		expect(coerced.statusCode).to.equal(400);
		expect(coerced.json().code).to.equal('invalid-request');
		await server.close();
	});

	it('maps client media and empty-body failures to 4xx problem details', async () => {
		const server = await buildServer();
		const media = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			headers: { 'content-type': 'application/x-www-form-urlencoded' },
			payload: 'a=1',
		});
		expect(media.statusCode).to.equal(415);
		expect(media.json()).to.include({
			code: 'unsupported-media-type',
			status: 415,
		});

		const empty = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			headers: { 'content-type': 'application/json' },
			payload: '',
		});
		expect(empty.statusCode).to.equal(400);
		expect(empty.json()).to.include({ code: 'invalid-request', status: 400 });
		await server.close();
	});

	it('rejects saturated generation requests with a retryable 429', async () => {
		resetWorkerPool();
		const limits = {
			...DEFAULT_LIMITS,
			maxConcurrentWorkers: 1,
			templateTimeoutMs: 2000,
		};
		const busy = templateRequest();
		busy.input.template = '- while (true) {}';
		const inflight = realize(busy, limits);
		const server = await buildServer({ limits });

		const saturated = await server.inject({
			method: 'POST',
			url: '/v1/generate',
			payload: templateRequest(),
		});
		expect(saturated.statusCode).to.equal(429);
		expect(saturated.json().code).to.equal('server-busy');
		expect(saturated.headers['retry-after']).to.equal('1');
		try {
			await inflight;
			expect.fail('expected the saturated request to time out');
		} catch (error) {
			expect(error).to.have.property('code', 'resource-limit');
		}
		await server.close();
	});

	it('hides unexpected internal errors behind problem details', async () => {
		const server = await buildServer();
		server.get('/test/internal-error', async () => {
			throw new Error('sensitive implementation detail');
		});
		const response = await server.inject({
			method: 'GET',
			url: '/test/internal-error',
		});
		expect(response.statusCode).to.equal(500);
		expect(response.json()).to.include({
			code: 'internal-error',
			detail: 'the request could not be processed',
		});
		expect(response.body).not.to.contain('sensitive implementation detail');
		await server.close();
	});
});
