import { expect } from 'chai';
import type { FastifyInstance } from 'fastify';
import { buildServer } from '../../src/api/server.js';

describe('GET /health', () => {
	let app: FastifyInstance;

	beforeEach(async () => {
		app = await buildServer();
	});

	afterEach(async () => {
		await app.close();
	});

	it('returns ok', async () => {
		const response = await app.inject({ method: 'GET', url: '/health' });
		expect(response.statusCode).to.equal(200);
		expect(response.json()).to.deep.equal({ status: 'ok' });
	});
});
