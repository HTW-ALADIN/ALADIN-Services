import { expect } from 'chai';
import { assertSafeCustomProviderBaseUrl } from '../../src/core/url-safety.js';
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
		'http://127.0.0.1/v1',
		'http://0.0.0.0/v1',
		'http://169.254.169.254/latest/meta-data',
		'http://metadata.google.internal/computeMetadata/v1',
		'http://10.0.0.5/v1',
		'http://172.16.0.5/v1',
		'http://192.168.1.5/v1',
		'http://[::1]/v1',
		'http://[fe80::1]/v1',
		'http://[fd00::1]/v1',
		'http://[::ffff:127.0.0.1]/v1',
	]) {
		it(`rejects disallowed target ${url}`, () => {
			expect(() => assertSafeCustomProviderBaseUrl(url)).to.throw(
				GatewayRequestError
			);
		});
	}

	it('allows a public IPv4 address', () => {
		expect(() =>
			assertSafeCustomProviderBaseUrl('https://8.8.8.8/v1')
		).to.not.throw();
	});
});
