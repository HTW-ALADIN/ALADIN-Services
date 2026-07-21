import { expect } from 'chai';
import sinon from 'sinon';
import {
	ProviderRegistry,
	validateProviderName,
} from '../../src/core/provider-registry.js';
import { GatewayRequestError } from '../../src/core/types.js';

describe('validateProviderName', () => {
	it('accepts valid lowercase hyphenated names', () => {
		expect(() => validateProviderName('mycompany')).to.not.throw();
		expect(() => validateProviderName('eu-west')).to.not.throw();
	});

	it('rejects invalid names', () => {
		for (const invalid of [
			'MyCompany',
			'my_company',
			'123test',
			'-mycompany',
			'my-',
			'my--company',
		]) {
			expect(() => validateProviderName(invalid)).to.throw(GatewayRequestError);
		}
	});
});

describe('ProviderRegistry', () => {
	let fetchStub: sinon.SinonStub;

	beforeEach(() => {
		fetchStub = sinon.stub(globalThis, 'fetch' as any);
	});

	afterEach(() => {
		fetchStub.restore();
	});

	it('skips registration when admin config is not set', async () => {
		const registry = new ProviderRegistry({});
		const result = await registry.register({
			name: 'mycompany',
			baseUrl: 'https://api.mycompany.com',
			apiKey: 'sk-x',
		});

		expect(result.registered).to.equal(false);
		expect(result.mode).to.equal('skipped');
		expect(fetchStub.called).to.equal(false);
	});

	it('rejects invalid provider names before calling the admin API', async () => {
		const registry = new ProviderRegistry({
			baseUrl: 'https://admin.example.com',
			token: 'llmgmk_x',
		});

		try {
			await registry.register({
				name: 'Invalid Name',
				baseUrl: 'https://api.mycompany.com',
				apiKey: 'sk-x',
			});
			expect.fail('expected register() to throw');
		} catch (err) {
			expect(err).to.be.instanceOf(GatewayRequestError);
		}
		expect(fetchStub.called).to.equal(false);
	});

	it('calls the configured admin API and reports success', async () => {
		fetchStub.resolves({
			ok: true,
			json: async () => ({ id: 'pk_123' }),
		} as any);

		const registry = new ProviderRegistry({
			baseUrl: 'https://admin.example.com',
			token: 'llmgmk_x',
		});
		const result = await registry.register({
			name: 'mycompany',
			baseUrl: 'https://api.mycompany.com',
			apiKey: 'sk-x',
		});

		expect(result).to.deep.equal({
			registered: true,
			mode: 'gateway-admin-api',
			message: 'Custom provider "mycompany" registered with LLM Gateway.',
		});
		expect(fetchStub.calledOnce).to.equal(true);
		const [url, init] = fetchStub.firstCall.args;
		expect(url).to.equal('https://admin.example.com/keys/provider');
		expect(init.headers.Authorization).to.equal('Bearer llmgmk_x');
	});

	it('propagates the admin API status code on failure', async () => {
		fetchStub.resolves({
			ok: false,
			status: 409,
			json: async () => ({
				error: { message: 'already exists', code: 'conflict' },
			}),
		} as any);

		const registry = new ProviderRegistry({
			baseUrl: 'https://admin.example.com',
			token: 'llmgmk_x',
		});

		try {
			await registry.register({
				name: 'mycompany',
				baseUrl: 'https://api.mycompany.com',
				apiKey: 'sk-x',
			});
			expect.fail('expected register() to throw');
		} catch (err) {
			expect(err).to.be.instanceOf(GatewayRequestError);
			expect((err as GatewayRequestError).status).to.equal(409);
			expect((err as GatewayRequestError).message).to.equal('already exists');
		}
	});

	it('wraps network failures as a 502 GatewayRequestError', async () => {
		fetchStub.rejects(new Error('network down'));
		const registry = new ProviderRegistry({
			baseUrl: 'https://admin.example.com',
			token: 'llmgmk_x',
		});

		try {
			await registry.register({
				name: 'mycompany',
				baseUrl: 'https://api.mycompany.com',
				apiKey: 'sk-x',
			});
			expect.fail('expected register() to throw');
		} catch (err) {
			expect(err).to.be.instanceOf(GatewayRequestError);
			expect((err as GatewayRequestError).status).to.equal(502);
		}
	});
});
