import { spawnSync } from 'node:child_process';
import dns from 'node:dns';
import { expect } from 'chai';
import sinon from 'sinon';
import {
	assertSafeCustomProviderBaseUrl,
	lookupPublicAddress,
} from '../../src/core/url-safety.js';
import { GatewayRequestError } from '../../src/core/types.js';

describe('assertSafeCustomProviderBaseUrl', () => {
	it('allows a public https URL', () => {
		expect(() =>
			assertSafeCustomProviderBaseUrl('https://api.mycompany.com/v1')
		).to.not.throw();
	});

	it('rejects an invalid URL', () => {
		expect(() => assertSafeCustomProviderBaseUrl('not-a-url')).to.throw(
			GatewayRequestError
		);
	});

	it('rejects a non-http(s) scheme', () => {
		expect(() =>
			assertSafeCustomProviderBaseUrl('file:///etc/passwd')
		).to.throw(GatewayRequestError);
	});

	for (const url of [
		'http://localhost:4001/v1',
		'http://localhost./v1',
		'http://service.localhost/v1',
		'http://127.0.0.1/v1',
		'http://127.1/v1',
		'http://2130706433/v1',
		'http://0x7f000001/v1',
		'http://0.0.0.0/v1',
		'http://0.1.2.3/v1',
		'http://100.64.0.1/v1',
		'http://169.254.169.254/latest/meta-data',
		'http://metadata.google.internal/computeMetadata/v1',
		'http://metadata.google.internal./computeMetadata/v1',
		'http://10.0.0.5/v1',
		'http://172.16.0.5/v1',
		'http://192.168.1.5/v1',
		'http://public.example@127.0.0.1/v1',
		'http://[::1]/v1',
		'http://[::]/v1',
		'http://[fe80::1]/v1',
		'http://[febf::1]/v1',
		'http://[fec0::1]/v1',
		'http://[fd00::1]/v1',
		'http://[ff02::1]/v1',
		'http://[::ffff:127.0.0.1]/v1',
		'http://[::127.0.0.1]/v1',
		'http://[64:ff9b::a00:1]/v1',
		'http://[2002:7f00:1::]/v1',
	]) {
		it(`rejects disallowed target ${url}`, () => {
			expect(() => assertSafeCustomProviderBaseUrl(url)).to.throw(
				GatewayRequestError
			);
		});
	}

	for (const url of [
		'https://8.8.8.8/v1',
		'https://[2606:4700:4700::1111]/v1',
		'https://[::ffff:8.8.8.8]/v1',
		'https://[64:ff9b::808:808]/v1',
		'https://fcloud.example.com/v1',
		'https://fd-provider.example.com/v1',
	]) {
		it(`allows public target ${url}`, () => {
			expect(() => assertSafeCustomProviderBaseUrl(url)).to.not.throw();
		});
	}
});

describe('lookupPublicAddress', () => {
	let sandbox: sinon.SinonSandbox;
	let addresses: dns.LookupAddress[];
	let lookupStub: sinon.SinonStub;
	let previousDirectEgress: string | undefined;

	beforeEach(() => {
		previousDirectEgress = process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS;
		process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS = 'true';
		sandbox = sinon.createSandbox();
		addresses = [
			{ address: '8.8.8.8', family: 4 },
			{ address: '2606:4700:4700::1111', family: 6 },
		];
		lookupStub = sandbox.stub(dns, 'lookup').callsFake(((
			_hostname,
			_options,
			callback
		) => {
			queueMicrotask(() => callback(null, addresses));
		}) as typeof dns.lookup);
	});

	afterEach(() => {
		sandbox.restore();
		if (previousDirectEgress === undefined) {
			delete process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS;
		} else {
			process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS = previousDirectEgress;
		}
	});

	function lookup(options: dns.LookupOptions) {
		return new Promise<{
			error: NodeJS.ErrnoException | null;
			address: string | dns.LookupAddress[];
			family?: number;
		}>((resolve) => {
			lookupPublicAddress(
				'provider.example',
				options,
				(error, address, family) => {
					resolve({ error, address, family });
				}
			);
		});
	}

	it('returns the exact validated addresses for a multi-address connection', async () => {
		const result = await lookup({ all: true, hints: dns.ADDRCONFIG });
		expect(result.error).to.equal(null);
		expect(result.address).to.deep.equal(addresses);
		expect(lookupStub.firstCall.args[1]).to.include({
			all: true,
			hints: dns.ADDRCONFIG,
		});
	});

	it('returns one validated address when the connection requests one', async () => {
		const result = await lookup({ all: false });
		expect(result).to.deep.equal({
			error: null,
			address: '8.8.8.8',
			family: 4,
		});
		expect(lookupStub.firstCall.args[1].all).to.equal(true);
	});

	it('rejects mixed public and private DNS answers', async () => {
		addresses.push({ address: '127.0.0.1', family: 4 });
		const result = await lookup({ all: true });
		expect(result.error).to.be.instanceOf(GatewayRequestError);
		expect((result.error as GatewayRequestError).status).to.equal(400);
	});

	it('rejects an invalid address family from the resolver', async () => {
		addresses = [{ address: '8.8.8.8', family: 6 }];
		const result = await lookup({ all: false });
		expect(result.error).to.be.instanceOf(GatewayRequestError);
	});

	it('propagates resolver failures without attempting a connection', async () => {
		const failure = Object.assign(new Error('lookup failed'), {
			code: 'ENOTFOUND',
		});
		lookupStub.callsFake(((_hostname, _options, callback) => {
			queueMicrotask(() => callback(failure));
		}) as typeof dns.lookup);
		const result = await lookup({ all: true });
		expect(result.error).to.equal(failure);
	});
});

describe('custom provider egress startup policy', () => {
	const cases = [
		{
			name: 'allows the unmodified default dispatcher on a clean start',
			script: `
				const { getCustomProviderDispatcher } = await import('./src/core/url-safety.ts');
				if (!getCustomProviderDispatcher()) throw new Error('missing dispatcher');
			`,
		},
		{
			name: 'allows direct providers when the server starts without a proxy',
			script: `
				await import('./src/api/server.ts');
				const { getCustomProviderDispatcher } = await import('./src/core/url-safety.ts');
				if (!getCustomProviderDispatcher()) throw new Error('missing dispatcher');
			`,
		},
		{
			name: 'rejects a preinitialized default agent without explicit opt-in',
			script: `
				await import('undici');
				const { getCustomProviderDispatcher } = await import('./src/core/url-safety.ts');
				let error;
				try { getCustomProviderDispatcher(); } catch (caught) { error = caught; }
				if (error?.status !== 503) throw new Error('expected a 503');
			`,
		},
		{
			name: 'allows an explicitly approved preinitialized plain agent',
			script: `
				await import('undici');
				process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS = 'true';
				const { getCustomProviderDispatcher } = await import('./src/core/url-safety.ts');
				if (!getCustomProviderDispatcher()) throw new Error('missing dispatcher');
			`,
		},
		{
			name: 'rejects a preinstalled custom Agent without explicit opt-in',
			script: `
				const { Agent, setGlobalDispatcher } = await import('undici');
				setGlobalDispatcher(new Agent({ connect() { throw new Error('unexpected connection'); } }));
				const { getCustomProviderDispatcher } = await import('./src/core/url-safety.ts');
				let error;
				try { getCustomProviderDispatcher(); } catch (caught) { error = caught; }
				if (error?.status !== 503) throw new Error('expected a 503');
			`,
		},
		{
			name: 'rejects a preinstalled environment proxy agent',
			script: `
				const { EnvHttpProxyAgent, setGlobalDispatcher } = await import('undici');
				setGlobalDispatcher(new EnvHttpProxyAgent({ httpProxy: 'http://127.0.0.1:1' }));
				process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS = 'true';
				const { getCustomProviderDispatcher } = await import('./src/core/url-safety.ts');
				let error;
				try { getCustomProviderDispatcher(); } catch (caught) { error = caught; }
				if (error?.status !== 503) throw new Error('expected a 503');
			`,
		},
		{
			name: 'rejects a preinstalled ProxyAgent even with direct opt-in',
			script: `
				const { ProxyAgent, setGlobalDispatcher } = await import('undici');
				setGlobalDispatcher(new ProxyAgent('http://127.0.0.1:1'));
				process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS = 'true';
				const { getCustomProviderDispatcher } = await import('./src/core/url-safety.ts');
				let error;
				try { getCustomProviderDispatcher(); } catch (caught) { error = caught; }
				if (error?.status !== 503) throw new Error('expected a 503');
			`,
		},
	];

	for (const { name, script } of cases) {
		it(name, () => {
			const env = { ...process.env };
			for (const key of [
				'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
				'http_proxy', 'https_proxy', 'all_proxy',
				'GLOBAL_AGENT_HTTP_PROXY', 'GLOBAL_AGENT_HTTPS_PROXY',
				'NODE_USE_ENV_PROXY', 'NODE_OPTIONS',
				'LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS',
			]) {
				delete env[key];
			}
			const result = spawnSync(
				process.execPath,
				['--import=tsx', '--input-type=module', '-e', script],
				{ cwd: process.cwd(), env, encoding: 'utf8', timeout: 10000 }
			);
			expect(result.status, result.stderr || String(result.error ?? '')).to.equal(0);
		});
	}
});
