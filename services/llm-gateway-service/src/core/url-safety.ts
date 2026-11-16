import dns from 'node:dns';
import { createRequire } from 'node:module';
import { isIP, type LookupFunction } from 'node:net';
import ipaddr from 'ipaddr.js';
import type { Dispatcher } from 'undici';
import { GatewayRequestError } from './types.js';

const dispatcherSymbol = Symbol.for('undici.globalDispatcher.1');
const preexistingGlobalDispatcher = Object.getOwnPropertySymbols(globalThis).some(
	(symbol) =>
		(Symbol.keyFor(symbol) ?? '').startsWith('undici.globalDispatcher.') &&
		Reflect.get(globalThis, symbol) !== undefined
);
const { Agent, buildConnector, getGlobalDispatcher } = createRequire(import.meta.url)(
	'undici'
) as typeof import('undici');
const initialGlobalDispatcher = getGlobalDispatcher();
const initialGlobalDispatch = initialGlobalDispatcher.dispatch;
const proxyEnvironmentVariables = [
	'HTTP_PROXY',
	'HTTPS_PROXY',
	'ALL_PROXY',
	'http_proxy',
	'https_proxy',
	'all_proxy',
	'GLOBAL_AGENT_HTTP_PROXY',
	'GLOBAL_AGENT_HTTPS_PROXY',
];
const globalUnicastPrefix = ipaddr.IPv6.parse('2000::');
const nat64Prefix = ipaddr.IPv6.parse('64:ff9b::');

export function assertSafeCustomProviderBaseUrl(rawUrl: string): void {
	let url: URL;
	try {
		url = new URL(rawUrl);
	} catch {
		throw new GatewayRequestError(
			`"customProvider.baseUrl" is not a valid URL: ${rawUrl}`,
			400
		);
	}

	if (url.protocol !== 'http:' && url.protocol !== 'https:') {
		throw new GatewayRequestError(
			`"customProvider.baseUrl" must use http or https, got "${url.protocol}"`,
			400
		);
	}

	const hostname = url.hostname.toLowerCase().replace(/^\[|\]$/g, '');
	const normalized = hostname.replace(/\.$/, '');
	if (
		normalized === 'localhost' ||
		normalized.endsWith('.localhost') ||
		normalized === 'metadata.google.internal' ||
		(isIP(hostname) !== 0 && !isPublicIpAddress(hostname))
	) {
		throw disallowedDestination(hostname);
	}
}

export const lookupPublicAddress: LookupFunction = (
	hostname,
	options,
	callback
) => {
	try {
		assertDirectProviderEgress();
	} catch (error) {
		callback(error as GatewayRequestError, '', 0);
		return;
	}

	dns.lookup(hostname, { ...options, all: true }, (error, addresses) => {
		try {
			assertDirectProviderEgress();
		} catch (policyError) {
			callback(policyError as GatewayRequestError, '', 0);
			return;
		}
		if (error) {
			callback(error, '', 0);
			return;
		}
		if (
			addresses.length === 0 ||
			addresses.some(
				({ address, family }) =>
					isIP(address) !== family || !isPublicIpAddress(address)
			)
		) {
			callback(disallowedDestination(hostname), '', 0);
			return;
		}
		if (options.all) {
			callback(null, addresses);
		} else {
			callback(null, addresses[0].address, addresses[0].family);
		}
	});
};

const connectToPublicAddress = buildConnector({ lookup: lookupPublicAddress });
const customProviderDispatcher = new Agent({
	connect: (options, callback) => {
		try {
			assertDirectProviderEgress();
		} catch (error) {
			callback(error as GatewayRequestError, null);
			return;
		}
		connectToPublicAddress(options, callback);
	},
});

export function getCustomProviderDispatcher(): Dispatcher {
	assertDirectProviderEgress();
	return customProviderDispatcher;
}

function assertDirectProviderEgress(): void {
	const currentDispatcher = getGlobalDispatcher();
	const otherGlobalDispatcher = Object.getOwnPropertySymbols(globalThis).some(
		(symbol) =>
			symbol !== dispatcherSymbol &&
			(Symbol.keyFor(symbol) ?? '').startsWith('undici.globalDispatcher.') &&
			Reflect.get(globalThis, symbol) !== undefined
	);
	if (
		proxyEnvironmentVariables.some((name) => Boolean(process.env[name])) ||
		process.env.NODE_USE_ENV_PROXY === '1' ||
		process.execArgv.some((arg) => arg === '--use-env-proxy' || arg.startsWith('--use-env-proxy=')) ||
		(process.env.NODE_OPTIONS ?? '').includes('--use-env-proxy') ||
		otherGlobalDispatcher ||
		currentDispatcher !== initialGlobalDispatcher ||
		currentDispatcher.dispatch !== initialGlobalDispatch ||
		currentDispatcher.constructor.name !== 'Agent' ||
		(preexistingGlobalDispatcher &&
			process.env.LLM_GATEWAY_ALLOW_DIRECT_PROVIDER_EGRESS !== 'true')
	) {
		throw new GatewayRequestError(
			'Direct custom-provider egress is disabled because a proxy or unverified global dispatcher may enforce an egress policy.',
			503
		);
	}
}

function isPublicIpAddress(address: string): boolean {
	if (isIP(address) === 0 || address.includes('%')) {
		return false;
	}

	const parsed = ipaddr.process(address);
	if (parsed.kind() === 'ipv4') {
		return parsed.range() === 'unicast';
	}

	const ipv6 = parsed as ipaddr.IPv6;
	if (ipv6.match(nat64Prefix, 96)) {
		return new ipaddr.IPv4(ipv6.toByteArray().slice(-4)).range() === 'unicast';
	}
	return ipv6.range() === 'unicast' && ipv6.match(globalUnicastPrefix, 3);
}

function disallowedDestination(hostname: string): GatewayRequestError {
	return new GatewayRequestError(
		`"customProvider.baseUrl" resolves to a disallowed loopback/private/link-local or non-public address: ${hostname}`,
		400
	);
}
