import { PostgresConnectionOptions } from 'typeorm/driver/postgres/PostgresConnectionOptions';
import dns from 'dns';
import { BlockList, isIP } from 'net';
import { databaseMetadata } from '../../database/internal-memory';
import { invalidAggregationPatterns } from '../constants';
import { t, SupportedLanguage } from '../i18n';

export function isDatabaseRegistered(databaseKey: string): boolean {
    return databaseMetadata.has(databaseKey);
}

export function isValidForAggregation(columnName: string): boolean {
    return !invalidAggregationPatterns.test(columnName);
}

const ALLOWED_POSTGRES_OPTIONS = new Set([
    'type', 'host', 'port', 'username', 'password', 'database', 'schema',
    'ssl', 'applicationName', 'connectTimeoutMS', 'poolSize', 'parseInt8',
    'maxQueryExecutionTime', 'logNotifications', 'extra',
]);

const NUMERIC_POSTGRES_EXTRA_OPTIONS = new Set([
    'max', 'min', 'maxUses', 'maxLifetimeSeconds', 'idleTimeoutMillis',
    'connectionTimeoutMillis', 'keepAliveInitialDelayMillis', 'statement_timeout',
    'query_timeout', 'lock_timeout', 'idle_in_transaction_session_timeout',
]);

const BOOLEAN_POSTGRES_EXTRA_OPTIONS = new Set(['allowExitOnIdle', 'keepAlive']);

function isSafePostgresExtra(extra: unknown): boolean {
    if (!extra || typeof extra !== 'object' || Array.isArray(extra)) return false;
    return Object.entries(extra).every(([key, value]) =>
        (NUMERIC_POSTGRES_EXTRA_OPTIONS.has(key) &&
            typeof value === 'number' && Number.isFinite(value) && value >= 0) ||
        (BOOLEAN_POSTGRES_EXTRA_OPTIONS.has(key) && typeof value === 'boolean'),
    );
}

const BLOCKED_HOSTS = new Set([
    'localhost',
    'metadata.google.internal',
    'metadata.azure.com',
]);

const blockedAddresses = new BlockList();
const blockedIPv4Subnets: [string, number][] = [
    ['0.0.0.0', 8],
    ['10.0.0.0', 8],
    ['100.64.0.0', 10],
    ['127.0.0.0', 8],
    ['169.254.0.0', 16],
    ['172.16.0.0', 12],
    ['192.168.0.0', 16],
    ['224.0.0.0', 4],
    ['240.0.0.0', 4],
];
for (const [network, prefix] of blockedIPv4Subnets) {
    blockedAddresses.addSubnet(network, prefix, 'ipv4');
    const [a, b, c, d] = network.split('.').map(Number);
    const high = ((a << 8) | b).toString(16);
    const low = ((c << 8) | d).toString(16);
    blockedAddresses.addSubnet(`64:ff9b::${high}:${low}`, 96 + prefix, 'ipv6');
    blockedAddresses.addSubnet(`2002:${high}:${low}::`, 16 + prefix, 'ipv6');
    blockedAddresses.addSubnet(`::ffff:0:${high}:${low}`, 96 + prefix, 'ipv6');
}
blockedAddresses.addSubnet('::', 96, 'ipv6');
blockedAddresses.addSubnet('64:ff9b:1::', 48, 'ipv6');
blockedAddresses.addSubnet('2001::', 32, 'ipv6');
blockedAddresses.addSubnet('fc00::', 7, 'ipv6');
blockedAddresses.addSubnet('fe80::', 10, 'ipv6');
blockedAddresses.addSubnet('fec0::', 10, 'ipv6');
blockedAddresses.addSubnet('ff00::', 8, 'ipv6');

function isUnsafeAddress(address: string): boolean {
    const family = isIP(address);
    if (!family || address.includes('%')) return true;
    return blockedAddresses.check(address, family === 4 ? 'ipv4' : 'ipv6');
}

function sslForHostname(
    ssl: PostgresConnectionOptions['ssl'],
    hostname: string,
): PostgresConnectionOptions['ssl'] {
    if (ssl === false) return false;
    let options: Exclude<NonNullable<PostgresConnectionOptions['ssl']>, boolean> & { servername: string };
    if (ssl && typeof ssl === 'object') {
        options = { ...ssl, servername: hostname };
    } else if (ssl === true || ['prefer', 'require', 'verify-ca', 'verify-full'].includes(process.env.PGSSLMODE ?? '')) {
        options = { servername: hostname };
    } else if (process.env.PGSSLMODE === 'no-verify') {
        options = { rejectUnauthorized: false, servername: hostname };
    } else {
        return undefined;
    }
    return options;
}

export type PostgresConnectionValidation =
    | { ok: true; requestedHost: string; connectionInfos: PostgresConnectionOptions[] }
    | { ok: false; message: string };

export async function validateConnectionInfo(
    connectionInfo: PostgresConnectionOptions,
    lang: SupportedLanguage = 'en',
): Promise<PostgresConnectionValidation> {
    if (!connectionInfo) {
        return { ok: false, message: t('INVALID_CONNECTION_INFO', lang) };
    }
    const rawExtra = connectionInfo.extra;
    const extra = rawExtra && typeof rawExtra === 'object' && !Array.isArray(rawExtra)
        ? { ...rawExtra }
        : rawExtra;
    const rawSsl = connectionInfo.ssl;
    const ssl = rawSsl && typeof rawSsl === 'object' && !Array.isArray(rawSsl)
        ? { ...rawSsl }
        : rawSsl;
    const options = { ...connectionInfo, extra, ssl };
    if (
        options.type !== 'postgres' ||
        typeof options.host !== 'string' ||
        !options.host ||
        !Number.isInteger(options.port) ||
        options.port! < 1 ||
        options.port! > 65535 ||
        !options.username ||
        !options.password ||
        !options.schema ||
        Object.keys(options).some((key) => !ALLOWED_POSTGRES_OPTIONS.has(key)) ||
        (extra !== undefined && !isSafePostgresExtra(extra)) ||
        (ssl !== undefined &&
            typeof ssl !== 'boolean' &&
            (typeof ssl !== 'object' ||
                ssl === null ||
                Array.isArray(ssl) ||
                'socket' in ssl))
    ) {
        return { ok: false, message: t('INVALID_CONNECTION_INFO', lang) };
    }

    const requestedHost = options.host;
    let host = requestedHost;
    if (host.startsWith('[') || host.endsWith(']')) {
        if (!host.startsWith('[') || !host.endsWith(']') || isIP(host.slice(1, -1)) !== 6) {
            return { ok: false, message: t('INVALID_CONNECTION_INFO', lang) };
        }
        host = host.slice(1, -1);
    }

    const normalizedHost = host.toLowerCase().replace(/\.$/, '');
    if (BLOCKED_HOSTS.has(normalizedHost) || normalizedHost.endsWith('.localhost')) {
        return { ok: false, message: t('UNSAFE_CONNECTION_HOST', lang) };
    }

    const isLiteral = isIP(host) !== 0;
    const database = options.database || process.env.PGDATABASE || options.username;
    const resolvedSsl = isLiteral ? ssl : sslForHostname(ssl, requestedHost);
    let addresses: string[];
    if (isLiteral) {
        addresses = [host];
    } else {
        try {
            addresses = (await dns.promises.lookup(host, { all: true })).map((entry) => entry.address);
        } catch {
            return { ok: false, message: t('UNABLE_TO_CONNECT', lang) };
        }
    }

    if (addresses.length === 0) {
        return { ok: false, message: t('UNABLE_TO_CONNECT', lang) };
    }
    if (addresses.some(isUnsafeAddress)) {
        return { ok: false, message: t('UNSAFE_CONNECTION_HOST', lang) };
    }

    return {
        ok: true,
        requestedHost,
        connectionInfos: [...new Set(addresses)].map((address) => ({
            type: 'postgres',
            host: address,
            port: options.port,
            username: options.username,
            password: options.password,
            database,
            schema: options.schema,
            ssl: resolvedSsl,
            applicationName: options.applicationName,
            connectTimeoutMS: options.connectTimeoutMS,
            poolSize: options.poolSize,
            parseInt8: options.parseInt8,
            maxQueryExecutionTime: options.maxQueryExecutionTime,
            logNotifications: options.logNotifications,
            extra,
        })),
    };
}
