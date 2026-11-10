import { GatewayRequestError } from './types.js';

/**
 * Best-effort SSRF mitigation for the `customProvider.baseUrl` override.
 *
 * This is a static check against the URL's literal hostname; it does not
 * resolve DNS, so a hostname that only *resolves* to an internal address at
 * request time is not caught here. Full protection against that requires
 * network-level egress controls at the deployment layer. Combined with
 * requiring authentication on the HTTP API (tracked separately), this closes
 * the most common accidental/careless cases (literal loopback, link-local,
 * and RFC1918 private-range targets, plus cloud metadata endpoints).
 */
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

	const hostname = url.hostname.toLowerCase();
	if (isDisallowedHostname(hostname)) {
		throw new GatewayRequestError(
			`"customProvider.baseUrl" resolves to a disallowed loopback/private/link-local address: ${hostname}`,
			400
		);
	}
}

function isDisallowedHostname(hostname: string): boolean {
	const normalized = hostname.replace(/^\[/, '').replace(/\]$/, '');

	if (normalized === 'localhost' || normalized === '0.0.0.0') {
		return true;
	}

	// Cloud metadata services (AWS/GCP/Azure/Alibaba all use this address).
	if (
		normalized === '169.254.169.254' ||
		normalized === 'metadata.google.internal'
	) {
		return true;
	}

	const ipv4 = parseIPv4(normalized);
	if (ipv4) {
		return isPrivateOrLoopbackIPv4(ipv4);
	}

	if (normalized === '::1' || normalized === '::') {
		return true;
	}
	if (
		normalized.startsWith('fe80:') ||
		normalized.startsWith('fc') ||
		normalized.startsWith('fd')
	) {
		// Link-local (fe80::/10) and unique local (fc00::/7) IPv6 ranges.
		return true;
	}
	const mapped = parseIPv4MappedIPv6(normalized);
	if (mapped) {
		return isPrivateOrLoopbackIPv4(mapped);
	}

	return false;
}

/**
 * Parses an IPv4-mapped IPv6 address, in either its dotted-decimal form
 * (`::ffff:127.0.0.1`) or the hex-group form the WHATWG URL parser
 * normalizes it to (`::ffff:7f00:1`).
 */
function parseIPv4MappedIPv6(
	normalized: string
): [number, number, number, number] | undefined {
	if (!normalized.startsWith('::ffff:')) {
		return undefined;
	}
	const rest = normalized.slice('::ffff:'.length);

	const dotted = parseIPv4(rest);
	if (dotted) {
		return dotted;
	}

	const hexMatch = /^([0-9a-f]{1,4}):([0-9a-f]{1,4})$/.exec(rest);
	if (!hexMatch) {
		return undefined;
	}
	const high = parseInt(hexMatch[1], 16);
	const low = parseInt(hexMatch[2], 16);
	return [(high >> 8) & 0xff, high & 0xff, (low >> 8) & 0xff, low & 0xff];
}

function parseIPv4(
	value: string
): [number, number, number, number] | undefined {
	const match = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(value);
	if (!match) {
		return undefined;
	}
	const parts = match.slice(1).map(Number);
	if (parts.some((part) => part < 0 || part > 255)) {
		return undefined;
	}
	return parts as [number, number, number, number];
}

function isPrivateOrLoopbackIPv4([a, b]: [
	number,
	number,
	number,
	number,
]): boolean {
	if (a === 127) return true; // 127.0.0.0/8 loopback
	if (a === 10) return true; // 10.0.0.0/8
	if (a === 172 && b >= 16 && b <= 31) return true; // 172.16.0.0/12
	if (a === 192 && b === 168) return true; // 192.168.0.0/16
	if (a === 169 && b === 254) return true; // 169.254.0.0/16 link-local
	return false;
}
