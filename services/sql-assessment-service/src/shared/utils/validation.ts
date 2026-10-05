import { PostgresConnectionOptions } from 'typeorm/driver/postgres/PostgresConnectionOptions';
import dns from 'dns';
import { isIP } from 'net';
import { databaseMetadata } from '../../database/internal-memory';
import { invalidAggregationPatterns } from '../constants';
import { t, SupportedLanguage } from '../i18n';

// `dns.lookupSync` exists at runtime (Node >= 0.11) but is not declared by the
// installed @types/node version; declare the subset we use so callers stay typed.
interface LookupSyncEntry {
    address: string;
    family: number;
}
const lookupSyncAll = (
    hostname: string,
): LookupSyncEntry[] =>
    (dns as unknown as {
        lookupSync: (
            hostname: string,
            options: { all: true },
        ) => LookupSyncEntry[];
    }).lookupSync(hostname, { all: true });

export function isDatabaseRegistered(databaseKey: string): boolean {
    return databaseMetadata.has(databaseKey);
}

export function isValidForAggregation(columnName: string): boolean {
    return !invalidAggregationPatterns.test(columnName);
}

const LOOPBACK_NAMES = new Set(['localhost', '0.0.0.0', '::1', '::']);

/**
 * Cloud metadata endpoints (AWS/GCP/Azure/OpenStack/Alibaba) that must never
 * be reachable from this service.
 */
const BLOCKED_HOSTS = new Set([
    '169.254.169.254',
    'metadata.google.internal',
    'metadata.azure.com',
    '100.100.100.200',
]);

function isPrivateOrLoopbackIPv4(a: number, b: number): boolean {
    if (a === 127) return true; // 127.0.0.0/8 loopback
    if (a === 10) return true; // 10.0.0.0/8
    if (a === 172 && b >= 16 && b <= 31) return true; // 172.16.0.0/12
    if (a === 192 && b === 168) return true; // 192.168.0.0/16
    if (a === 169 && b === 254) return true; // 169.254.0.0/16 link-local
    if (a === 0) return true; // 0.0.0.0/8
    if (a >= 224) return true; // multicast/reserved
    return false;
}

function isPrivateOrLoopbackIP(address: string): boolean {
    const v4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(address);
    if (v4) {
        return isPrivateOrLoopbackIPv4(Number(v4[1]), Number(v4[2]));
    }

    const lower = address.toLowerCase();
    if (lower === '::' || lower === '::1') return true; // unspecified / loopback
    if (lower.startsWith('fe80:')) return true; // link-local
    if (lower.startsWith('fc') || lower.startsWith('fd')) return true; // unique local

    if (lower.startsWith('::ffff:')) {
        // IPv4-mapped IPv6, e.g. ::ffff:127.0.0.1 or ::ffff:7f00:1
        const mapped = lower.slice('::ffff:'.length);
        const dotted = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(mapped);
        if (dotted) {
            return isPrivateOrLoopbackIP(
                `${dotted[1]}.${dotted[2]}.${dotted[3]}.${dotted[4]}`,
            );
        }
        const hex = /^([0-9a-f]{1,4}):([0-9a-f]{1,4})$/.exec(mapped);
        if (hex) {
            const high = parseInt(hex[1], 16);
            const low = parseInt(hex[2], 16);
            return isPrivateOrLoopbackIPv4((high >> 8) & 0xff, high & 0xff) ||
                isPrivateOrLoopbackIPv4((low >> 8) & 0xff, low & 0xff);
        }
        return true; // non-decodable IPv4-mapped forms are refused
    }
    return false;
}

/**
 * Block connection targets that point at internal infrastructure: loopback,
 * RFC1918 private ranges, link-local, multicast/reserved, cloud metadata, or
 * DNS names that resolve (best effort) to any of those.
 */
function isUnsafeHost(hostname: string): boolean {
    const host = hostname.replace(/^\[/, '').replace(/\]$/, '').toLowerCase();
    if (!host) {
        return true;
    }
    if (LOOPBACK_NAMES.has(host) || host.endsWith('.localhost')) {
        return true;
    }
    if (BLOCKED_HOSTS.has(host)) {
        return true;
    }

    if (isIP(host) !== 0) {
        return isPrivateOrLoopbackIP(host);
    }

    // Best-effort DNS resolution: names that resolve to internal addresses
    // (DNS rebinding or plain internal hostnames) must not be reachable.
    try {
        return lookupSyncAll(host).some((entry) =>
            isPrivateOrLoopbackIP(entry.address),
        );
    } catch {
        return false; // unresolvable now; the connection attempt itself will fail
    }
}

/**
 * Validates required fields on a Postgres connection info object AND blocks
 * connection targets that point at internal infrastructure (loopback, RFC1918
 * private ranges, link-local, cloud metadata, or DNS names resolving to them).
 * Returns a translated error message string if invalid, or null if valid.
 *
 * @param connectionInfo - The connection options to validate.
 * @param lang           - Language for the error message (defaults to 'en').
 */
export function validateConnectionInfo(
    connectionInfo: PostgresConnectionOptions,
    lang: SupportedLanguage = 'en'
): string | null {
    if (
        !connectionInfo.host ||
        !connectionInfo.port ||
        !connectionInfo.username ||
        !connectionInfo.password ||
        !connectionInfo.schema
    ) {
        return t('INVALID_CONNECTION_INFO', lang);
    }
    if (isUnsafeHost(connectionInfo.host)) {
        return t('UNSAFE_CONNECTION_HOST', lang);
    }
    return null;
}