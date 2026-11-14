import { afterEach, describe, it, expect, vi } from 'vitest';
import dns from 'dns';
import { readFile } from 'fs/promises';
import { Socket } from 'net';
import { DataSource } from 'typeorm';
import { PostgresConnectionOptions } from 'typeorm/driver/postgres/PostgresConnectionOptions';
import type { Request, Response } from 'express';
import { createControllers } from '../../src/bootstrap';
import { DatabaseAnalyzer } from '../../src/database/database-analyzer';
import { QueryExecutionService } from '../../src/query/query-execution-service';
import { QueryExecutionController } from '../../src/query/query-execution-controller';
import { SQLQueryGenerationService } from '../../src/generation/query/sql-query-generation-service';
import { TaskDescriptionGenerationService } from '../../src/generation/description/task-description-generation-service';
import { SQLQueryGradingService } from '../../src/grading/query-grading-service';
import { ResultSetComparator } from '../../src/grading/result-set-comparator';
import { connectToPostgresCandidates, generatePostgresDatabaseKey } from '../../src/shared/utils/database-utils';
import { databaseMetadata } from '../../src/database/internal-memory';
import { t } from '../../src/shared/i18n';
import { validateConnectionInfo } from '../../src/shared/utils/validation';

const validConnection = {
    type: 'postgres' as const,
    host: 'db.example.com',
    port: 5432,
    username: 'user',
    password: 'secret',
    schema: 'public',
};

function mockLookup(addresses: { address: string; family: number }[]) {
    return vi.spyOn(dns.promises, 'lookup').mockResolvedValue(addresses as never);
}

function mockReadyDataSource() {
    return vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
        (this as any).isInitialized = true;
        return this;
    });
}

function mockDataSourceDestroy() {
    return vi.spyOn(DataSource.prototype, 'destroy').mockImplementation(async function (this: DataSource) {
        (this as any).isInitialized = false;
    });
}

function mockSchemaAnalysis() {
    return vi.spyOn(DatabaseAnalyzer.prototype, 'extractDatabaseSchema').mockImplementation(async (_source, _schema, key) => {
        databaseMetadata.set(key, []);
        return true;
    });
}

afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    databaseMetadata.clear();
});

describe('validateConnectionInfo', () => {
    it.each(['host', 'port', 'username', 'password', 'schema'])(
        'rejects a missing %s',
        async (field) => {
            const result = await validateConnectionInfo({
                ...validConnection,
                [field]: undefined,
            });
            expect(result).toEqual({ ok: false, message: t('INVALID_CONNECTION_INFO', 'en') });
        },
    );

    it.each([
        'localhost',
        'service.localhost.',
        '127.0.0.1',
        '10.0.0.5',
        '172.16.0.5',
        '192.168.1.5',
        '169.254.169.254',
        '100.100.100.200',
        'metadata.google.internal.',
        '::1',
        '[0:0:0:0:0:0:0:1]',
        '::ffff:7f00:1',
        '::ffff:192.168.1.5',
        '64:ff9b::a00:1',
        '64:ff9b:1::808:808',
        '2001:0::1',
        '2002:a00:1::1',
        '::ffff:0:c0a8:105',
        'fe90::1',
        'fc00::1',
        'ff02::1',
    ])('rejects unsafe connection target %s', async (host) => {
        const result = await validateConnectionInfo({ ...validConnection, host });
        expect(result).toEqual({ ok: false, message: t('UNSAFE_CONNECTION_HOST', 'en') });
    });

    it('rejects a hostname resolving to a private address', async () => {
        const lookup = mockLookup([{ address: '127.0.0.1', family: 4 }]);
        const result = await validateConnectionInfo(validConnection);
        expect(result).toEqual({ ok: false, message: t('UNSAFE_CONNECTION_HOST', 'en') });
        expect(lookup).toHaveBeenCalledWith('db.example.com', { all: true });
    });

    it('returns all distinct public addresses with the original TLS hostname', async () => {
        const lookup = mockLookup([
            { address: '2001:4860:4860::8888', family: 6 },
            { address: '8.8.8.8', family: 4 },
            { address: '8.8.8.8', family: 4 },
        ]);
        const result = await validateConnectionInfo({ ...validConnection, ssl: true });
        expect(result.ok).toBe(true);
        if (!result.ok) throw new Error(result.message);
        expect(result.requestedHost).toBe('db.example.com');
        expect(result.connectionInfos.map((info) => info.host))
            .toEqual(['2001:4860:4860::8888', '8.8.8.8']);
        expect(result.connectionInfos.map((info) => info.ssl))
            .toEqual([{ servername: 'db.example.com' }, { servername: 'db.example.com' }]);
        expect(lookup).toHaveBeenCalledTimes(1);
    });

    it('rejects mixed public and private DNS answers', async () => {
        mockLookup([
            { address: '8.8.8.8', family: 4 },
            { address: 'fd00::1', family: 6 },
        ]);
        const result = await validateConnectionInfo(validConnection);
        expect(result).toEqual({ ok: false, message: t('UNSAFE_CONNECTION_HOST', 'en') });
    });

    it('rejects invalid DNS answers', async () => {
        mockLookup([{ address: 'not-an-ip', family: 4 }]);
        const result = await validateConnectionInfo(validConnection);
        expect(result).toEqual({ ok: false, message: t('UNSAFE_CONNECTION_HOST', 'en') });
    });

    it('fails closed when DNS lookup fails', async () => {
        vi.spyOn(dns.promises, 'lookup').mockRejectedValue(new Error('DNS unavailable'));
        const result = await validateConnectionInfo(validConnection, 'de');
        expect(result).toEqual({ ok: false, message: t('UNABLE_TO_CONNECT', 'de') });
    });

    it('fails closed when DNS returns no addresses', async () => {
        mockLookup([]);
        const result = await validateConnectionInfo(validConnection);
        expect(result).toEqual({ ok: false, message: t('UNABLE_TO_CONNECT', 'en') });
    });

    it('pins a public DNS answer and retains the requested TLS hostname', async () => {
        const lookup = mockLookup([{ address: '8.8.8.8', family: 4 }]);
        const result = await validateConnectionInfo({
            ...validConnection,
            ssl: { ca: 'test-ca' },
        });
        expect(result.ok).toBe(true);
        if (!result.ok) throw new Error(result.message);
        expect(result.connectionInfos[0].host).toBe('8.8.8.8');
        expect(result.connectionInfos[0].ssl).toEqual({ ca: 'test-ca', servername: 'db.example.com' });
        expect(validConnection.host).toBe('db.example.com');
        expect(lookup).toHaveBeenCalledTimes(1);
    });

    it('preserves the hostname for TLS enabled by PGSSLMODE', async () => {
        vi.stubEnv('PGSSLMODE', 'require');
        mockLookup([{ address: '8.8.8.8', family: 4 }]);
        const result = await validateConnectionInfo(validConnection);
        expect(result.ok).toBe(true);
        if (!result.ok) throw new Error(result.message);
        expect(result.connectionInfos[0].ssl).toEqual({ servername: 'db.example.com' });
    });

    it.each([
        ['no-verify', undefined, { rejectUnauthorized: false, servername: 'db.example.com' }],
        ['require', false, false],
        ['no-verify', true, { servername: 'db.example.com' }],
        ['disable', undefined, undefined],
    ])('preserves TLS settings for PGSSLMODE %s', async (mode, ssl, expected) => {
        vi.stubEnv('PGSSLMODE', mode as string);
        mockLookup([{ address: '8.8.8.8', family: 4 }]);
        const result = await validateConnectionInfo({ ...validConnection, ssl });
        expect(result.ok).toBe(true);
        if (!result.ok) throw new Error(result.message);
        expect(result.connectionInfos[0].ssl).toEqual(expected);
    });

    it('allows and pins a public IPv6 DNS answer', async () => {
        mockLookup([{ address: '2001:4860:4860::8888', family: 6 }]);
        const result = await validateConnectionInfo(validConnection);
        expect(result.ok).toBe(true);
        if (!result.ok) throw new Error(result.message);
        expect(result.connectionInfos[0].host).toBe('2001:4860:4860::8888');
    });

    it.each([
        '8.8.8.8',
        '64:ff9b::808:808',
        '2002:808:808::1',
        '::ffff:0:808:808',
    ])('does not resolve a public literal IP address %s', async (host) => {
        const lookup = vi.spyOn(dns.promises, 'lookup');
        const result = await validateConnectionInfo({ ...validConnection, host });
        expect(result.ok).toBe(true);
        if (!result.ok) throw new Error(result.message);
        expect(result.connectionInfos[0].host).toBe(host);
        expect(lookup).not.toHaveBeenCalled();
    });

    it('preserves allowed PostgreSQL pool options', async () => {
        mockLookup([{ address: '8.8.8.8', family: 4 }]);
        const extra = { max: 1, connectionTimeoutMillis: 1000, keepAlive: true };
        const result = await validateConnectionInfo({ ...validConnection, extra });
        expect(result.ok).toBe(true);
        if (!result.ok) throw new Error(result.message);
        expect(result.connectionInfos[0].extra).toEqual(extra);
        expect(result.connectionInfos[0].extra).not.toBe(extra);
    });

    it('snapshots TLS and pool options before awaiting DNS', async () => {
        let resolveLookup!: (addresses: { address: string; family: number }[]) => void;
        const answer = new Promise<{ address: string; family: number }[]>((resolve) => {
            resolveLookup = resolve;
        });
        vi.spyOn(dns.promises, 'lookup').mockImplementation(() => answer as never);
        const ssl = { ca: 'test-ca' };
        const extra: { max: number; host?: string } = { max: 1 };
        const info = { ...validConnection, ssl, extra, database: 'initial' };
        const pending = validateConnectionInfo(info);
        info.host = '127.0.0.1';
        info.database = 'other';
        info.username = 'other';
        info.schema = 'other';
        extra.host = '127.0.0.1';
        Object.assign(ssl, { socket: {} });
        resolveLookup([{ address: '8.8.8.8', family: 4 }]);

        const result = await pending;
        expect(result.ok).toBe(true);
        if (!result.ok) throw new Error(result.message);
        expect(result.requestedHost).toBe('db.example.com');
        expect(result.connectionInfos[0]).toMatchObject({
            host: '8.8.8.8', database: 'initial', username: 'user', schema: 'public',
        });
        expect(result.connectionInfos[0].extra).toEqual({ max: 1 });
        expect(result.connectionInfos[0].ssl).toEqual({ ca: 'test-ca', servername: 'db.example.com' });
    });

    it.each([
        { url: 'postgres://user:pass@127.0.0.1/db' },
        { extra: { host: '127.0.0.1' } },
        { extra: { connectionString: 'postgres://127.0.0.1/db' } },
        { extra: { max: 'invalid' } },
        { driver: {} },
        { nativeDriver: {} },
        { ssl: { socket: {} } },
        { replication: { master: { host: '127.0.0.1' }, slaves: [] } },
        { cache: { type: 'redis', options: { host: '127.0.0.1' } } },
    ])('rejects unsupported connection options %j', async (overrides) => {
        const lookup = vi.spyOn(dns.promises, 'lookup');
        const result = await validateConnectionInfo({
            ...validConnection,
            ...overrides,
        } as PostgresConnectionOptions);
        expect(result).toEqual({ ok: false, message: t('INVALID_CONNECTION_INFO', 'en') });
        expect(lookup).not.toHaveBeenCalled();
    });

    it('connects using the pinned address even if DNS subsequently changes', async () => {
        vi.stubEnv('PGSSLMODE', '');
        const lookup = mockLookup([{ address: '8.8.8.8', family: 4 }]);
        lookup.mockResolvedValueOnce([{ address: '8.8.8.8', family: 4 }] as never);
        lookup.mockResolvedValueOnce([{ address: '127.0.0.1', family: 4 }] as never);
        const result = await validateConnectionInfo(validConnection);
        expect(result.ok).toBe(true);
        if (!result.ok) throw new Error(result.message);

        let connectedHost: unknown;
        vi.spyOn(Socket.prototype, 'connect').mockImplementation(function (this: Socket, ...args: any[]) {
            connectedHost = args[1];
            process.nextTick(() => this.emit('error', new Error('test connection stopped')));
            return this;
        } as typeof Socket.prototype.connect);

        const dataSource = new DataSource(result.connectionInfos[0]);
        await expect(dataSource.initialize()).rejects.toThrow('test connection stopped');
        expect(connectedHost).toBe('8.8.8.8');
        expect(lookup).toHaveBeenCalledTimes(1);
    });

    it.skipIf(!process.env.SQL_ASSESSMENT_TEST_POSTGRES_PIN_URL)(
        'connects to PostgreSQL using a pinned DNS answer',
        async () => {
            const target = new URL(process.env.SQL_ASSESSMENT_TEST_POSTGRES_PIN_URL!);
            const targetHost = target.hostname.replace(/^\[|\]$/g, '');
            const targetPort = Number(target.port || 5432);
            const lookup = mockLookup([{ address: '8.8.8.8', family: 4 }]);
            lookup.mockResolvedValueOnce([{ address: '8.8.8.8', family: 4 }] as never);
            lookup.mockResolvedValueOnce([{ address: '127.0.0.1', family: 4 }] as never);
            const result = await validateConnectionInfo({
                ...validConnection,
                port: targetPort,
                username: decodeURIComponent(target.username) || validConnection.username,
                password: decodeURIComponent(target.password) || process.env.PGPASSWORD || validConnection.password,
                database: decodeURIComponent(target.pathname.slice(1)),
                ssl: false,
                extra: { max: 1 },
            });
            expect(result.ok).toBe(true);
            if (!result.ok) throw new Error(result.message);

            const connect = Socket.prototype.connect;
            let connectedHost: unknown;
            vi.spyOn(Socket.prototype, 'connect').mockImplementation(function (this: Socket, ...args: any[]) {
                if (args[0] === targetPort && args[1] === '8.8.8.8') {
                    connectedHost = args[1];
                    return (connect as any).call(this, targetPort, targetHost);
                }
                return (connect as any).apply(this, args);
            } as typeof Socket.prototype.connect);

            const dataSource = new DataSource(result.connectionInfos[0]);
            try {
                await dataSource.initialize();
                expect(await dataSource.query('SELECT 42 AS answer')).toEqual([{ answer: 42 }]);
                expect(connectedHost).toBe('8.8.8.8');
                expect(lookup).toHaveBeenCalledTimes(1);
            } finally {
                if (dataSource.isInitialized) await dataSource.destroy();
            }
        },
    );

    it.skipIf(!process.env.SQL_ASSESSMENT_TEST_POSTGRES_PIN_URL)(
        'analyzes and executes through a live failover connection',
        async () => {
            const target = new URL(process.env.SQL_ASSESSMENT_TEST_POSTGRES_PIN_URL!);
            const targetHost = target.hostname.replace(/^\[|\]$/g, '');
            const targetPort = Number(target.port || 5432);
            const username = decodeURIComponent(target.username) || validConnection.username;
            const password = decodeURIComponent(target.password) || process.env.PGPASSWORD || validConnection.password;
            const database = decodeURIComponent(target.pathname.slice(1));
            const table = `assessment_failover_${process.pid}_${Date.now()}`;
            const setup = new DataSource({
                type: 'postgres', host: targetHost, port: targetPort, username, password, database, ssl: false,
            });
            await setup.initialize();
            try {
                await setup.query(`CREATE TABLE "${table}" (id integer PRIMARY KEY)`);
                await setup.query(`INSERT INTO "${table}" VALUES (7)`);
                const lookup = mockLookup([
                    { address: '2001:4860:4860::8888', family: 6 },
                    { address: '8.8.8.8', family: 4 },
                ]);
                const connect = Socket.prototype.connect;
                const attempted: string[] = [];
                vi.spyOn(Socket.prototype, 'connect').mockImplementation(function (this: Socket, ...args: any[]) {
                    if (args[0] === targetPort && args[1] === '2001:4860:4860::8888') {
                        attempted.push(args[1]);
                        process.nextTick(() => this.emit('error', new Error('unreachable')));
                        return this;
                    }
                    if (args[0] === targetPort && args[1] === '8.8.8.8') {
                        attempted.push(args[1]);
                        return (connect as any).call(this, targetPort, targetHost);
                    }
                    return (connect as any).apply(this, args);
                } as typeof Socket.prototype.connect);
                const analyze = vi.spyOn(DatabaseAnalyzer.prototype, 'extractDatabaseSchema');
                const execute = vi.spyOn(QueryExecutionService.prototype, 'executeQuery');
                const { req, res, status, json } = mockHttp();
                req.body.connectionInfo = {
                    ...validConnection, port: targetPort, username, password, database, ssl: false,
                };
                req.body.query = `SELECT id FROM "${table}"`;

                await createControllers().queryExecutionController.executeQuery(req, res);

                expect(status).toHaveBeenCalledWith(200);
                expect(json).toHaveBeenCalledWith({ rows: [{ id: 7 }], rowCount: 1 });
                expect(attempted.slice(0, 2)).toEqual(['2001:4860:4860::8888', '8.8.8.8']);
                expect(analyze).toHaveBeenCalledTimes(1);
                expect(execute.mock.calls[0][1]).toBe(analyze.mock.calls[0][0]);
                expect(lookup).toHaveBeenCalledTimes(1);
            } finally {
                await setup.query(`DROP TABLE IF EXISTS "${table}"`);
                await setup.destroy();
            }
        },
    );

    it.skipIf(!process.env.SQL_ASSESSMENT_TEST_POSTGRES_PIN_URL || !process.env.SQL_ASSESSMENT_TEST_POSTGRES_TLS_CA)(
        'verifies the original TLS hostname after pinning',
        async () => {
            const target = new URL(process.env.SQL_ASSESSMENT_TEST_POSTGRES_PIN_URL!);
            const targetHost = target.hostname.replace(/^\[|\]$/g, '');
            const targetPort = Number(target.port || 5432);
            const configuredCa = process.env.SQL_ASSESSMENT_TEST_POSTGRES_TLS_CA!;
            const ca = configuredCa.includes('-----BEGIN CERTIFICATE-----')
                ? configuredCa
                : await readFile(configuredCa, 'utf8');
            const lookup = mockLookup([
                { address: '2001:4860:4860::8888', family: 6 },
                { address: '8.8.8.8', family: 4 },
            ]);
            const options = {
                ...validConnection,
                host: process.env.SQL_ASSESSMENT_TEST_POSTGRES_TLS_HOST || 'db.example.com',
                port: targetPort,
                username: decodeURIComponent(target.username) || validConnection.username,
                password: decodeURIComponent(target.password) || process.env.PGPASSWORD || validConnection.password,
                database: decodeURIComponent(target.pathname.slice(1)),
                ssl: { ca },
                extra: { connectionTimeoutMillis: 1000 },
            };
            const result = await validateConnectionInfo(options);
            expect(result.ok).toBe(true);
            if (!result.ok) throw new Error(result.message);

            const connect = Socket.prototype.connect;
            const attempted: string[] = [];
            vi.spyOn(Socket.prototype, 'connect').mockImplementation(function (this: Socket, ...args: any[]) {
                if (args[0] === targetPort && args[1] === '2001:4860:4860::8888') {
                    attempted.push(args[1]);
                    return this;
                }
                if (args[0] === targetPort && args[1] === '8.8.8.8') {
                    attempted.push(args[1]);
                    return (connect as any).call(this, targetPort, targetHost);
                }
                return (connect as any).apply(this, args);
            } as typeof Socket.prototype.connect);

            const connection = await connectToPostgresCandidates(result.connectionInfos);
            expect(connection).not.toBeNull();
            if (!connection) throw new Error('Unable to connect to PostgreSQL');
            const dataSource = connection.dataSource;
            try {
                expect(await dataSource.query('SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()'))
                    .toEqual([{ ssl: true }]);
                expect(attempted).toEqual(['2001:4860:4860::8888', '8.8.8.8']);
            } finally {
                if (dataSource.isInitialized) await dataSource.destroy();
            }

            const mismatch = await validateConnectionInfo({ ...options, host: 'invalid.invalid' });
            expect(mismatch.ok).toBe(true);
            if (!mismatch.ok) throw new Error(mismatch.message);
            const invalidDataSource = new DataSource(mismatch.connectionInfos[1]);
            try {
                await expect(invalidDataSource.initialize()).rejects.toThrow(/hostname\/ip does not match/i);
            } finally {
                if (invalidDataSource.isInitialized) await invalidDataSource.destroy();
            }
            expect(lookup).toHaveBeenCalledTimes(2);
        },
    );
});

type Controllers = ReturnType<typeof createControllers>;
type ControllerHandler = (controllers: Controllers, req: Request, res: Response) => Promise<Response>;

const connectionHandlers: [string, ControllerHandler][] = [
    ['database analysis', (controllers, req, res) => controllers.connectionController.analyzeDatabase(req, res)],
    ['query execution', (controllers, req, res) => controllers.queryExecutionController.executeQuery(req, res)],
    ['task generation', (controllers, req, res) => controllers.taskGenerationController.generateTaskForRequest(req, res)],
    ['grading', (controllers, req, res) => controllers.gradingController.gradeQuery(req, res)],
    ['result comparison', (controllers, req, res) => controllers.gradingController.compareResultSet(req, res)],
];

function mockHttp() {
    const body = {
        connectionInfo: { ...validConnection, ssl: true },
        query: 'SELECT 1',
        studentQuery: 'SELECT 1',
        referenceQuery: 'SELECT 1',
        gradingRequest: { studentQuery: 'SELECT 1', referenceQuery: 'SELECT 1' },
    };
    const status = vi.fn().mockReturnThis();
    const json = vi.fn().mockReturnThis();
    return {
        req: { body } as Request,
        res: { status, json } as unknown as Response,
        status,
        json,
    };
}

describe('Postgres controller DNS validation', () => {
    it.each(connectionHandlers)('%s uses the pinned address', async (_name, handler) => {
        vi.stubEnv('PGSSLMODE', '');
        mockLookup([{ address: '8.8.8.8', family: 4 }]);
        let options: DataSource['options'] | undefined;
        vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            options = this.options;
            throw new Error('test connection stopped');
        });
        vi.spyOn(DataSource.prototype, 'destroy');
        const log = vi.spyOn(console, 'log');
        const { req, res, status } = mockHttp();

        await handler(createControllers(), req, res);

        expect(status).toHaveBeenCalledWith(400);
        expect(options).toMatchObject({
            host: '8.8.8.8',
            ssl: { servername: 'db.example.com' },
        });
        expect(log).not.toHaveBeenCalledWith('Received connection info:', expect.anything());
    });

    it.each(connectionHandlers)('%s rejects mixed DNS answers without connecting', async (_name, handler) => {
        const lookup = mockLookup([
            { address: '8.8.8.8', family: 4 },
            { address: '127.0.0.1', family: 4 },
        ]);
        const initialize = vi.spyOn(DataSource.prototype, 'initialize');
        const { req, res, status, json } = mockHttp();

        await handler(createControllers(), req, res);

        expect(status).toHaveBeenCalledWith(400);
        expect(json).toHaveBeenCalledWith({ message: t('UNSAFE_CONNECTION_HOST', 'en') });
        expect(initialize).not.toHaveBeenCalled();
        expect(lookup).toHaveBeenCalledTimes(1);
    });

    it.each(connectionHandlers.slice(1))('%s uses one pinned DNS answer', async (_name, handler) => {
        const lookup = mockLookup([{ address: '127.0.0.1', family: 4 }]);
        lookup.mockResolvedValueOnce([{ address: '8.8.8.8', family: 4 }] as never);
        const key = generatePostgresDatabaseKey(validConnection.host, { ...validConnection, host: '8.8.8.8' });
        databaseMetadata.set(key, []);
        let connectedHost: string | undefined;
        const initialize = vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            connectedHost = (this.options as PostgresConnectionOptions).host;
            (this as any).isInitialized = true;
            return this;
        });
        const destroy = mockDataSourceDestroy();
        vi.spyOn(QueryExecutionService.prototype, 'executeQuery').mockResolvedValue({ rows: [], rowCount: 0 });
        vi.spyOn(SQLQueryGenerationService.prototype, 'validateConfiguration').mockReturnValue([false, 'invalid']);
        vi.spyOn(SQLQueryGradingService.prototype, 'gradeQuery').mockResolvedValue({
            equivalent: true, grade: 7, supportedQueryType: true, feedbackDetails: {},
        });
        vi.spyOn(ResultSetComparator.prototype, 'compare').mockResolvedValue([true, []]);
        const { req, res } = mockHttp();

        await handler(createControllers(), req, res);

        expect(connectedHost).toBe('8.8.8.8');
        expect(initialize).toHaveBeenCalledTimes(1);
        expect(destroy).toHaveBeenCalledTimes(1);
        expect(lookup).toHaveBeenCalledTimes(1);
    });

    it.each(connectionHandlers.slice(1))('%s retains the analyzed connection', async (_name, handler) => {
        const lookup = mockLookup([{ address: '8.8.8.8', family: 4 }]);
        const initialize = mockReadyDataSource();
        const destroy = mockDataSourceDestroy();
        const analyze = mockSchemaAnalysis();
        vi.spyOn(QueryExecutionService.prototype, 'executeQuery').mockResolvedValue({ rows: [], rowCount: 0 });
        vi.spyOn(SQLQueryGenerationService.prototype, 'validateConfiguration').mockReturnValue([false, 'invalid']);
        vi.spyOn(SQLQueryGradingService.prototype, 'gradeQuery').mockResolvedValue({
            equivalent: true, grade: 7, supportedQueryType: true, feedbackDetails: {},
        });
        vi.spyOn(ResultSetComparator.prototype, 'compare').mockResolvedValue([true, []]);
        const { req, res } = mockHttp();

        await handler(createControllers(), req, res);

        expect(analyze).toHaveBeenCalledTimes(1);
        expect(initialize).toHaveBeenCalledTimes(1);
        expect(initialize.mock.contexts[0]).toBe(analyze.mock.calls[0][0]);
        expect(destroy).toHaveBeenCalledTimes(1);
        expect(lookup).toHaveBeenCalledTimes(1);
    });

    it('description uses metadata for the single validated DNS answer', async () => {
        const lookup = mockLookup([{ address: '127.0.0.1', family: 4 }]);
        lookup.mockResolvedValueOnce([{ address: '8.8.8.8', family: 4 }] as never);
        const key = generatePostgresDatabaseKey(validConnection.host, { ...validConnection, host: '8.8.8.8' });
        databaseMetadata.set(key, []);
        mockReadyDataSource();
        mockDataSourceDestroy();
        vi.spyOn(TaskDescriptionGenerationService.prototype, 'generateTaskFromQuery').mockResolvedValue('description');
        const { req, res, status } = mockHttp();

        await createControllers().descriptionController.generateTemplateDescription(req, res);

        expect(status).toHaveBeenCalledWith(200);
        expect(lookup).toHaveBeenCalledTimes(1);
    });
});

const timeoutCases: [string, Partial<PostgresConnectionOptions>, number][] = [
    ['missing', {}, 5000],
    ['zero', { connectTimeoutMS: 0 }, 5000],
    ['negative', { connectTimeoutMS: -1 }, 5000],
    ['non-finite', { connectTimeoutMS: Infinity }, 5000],
    ['not-a-number', { connectTimeoutMS: NaN }, 5000],
    ['non-finite extra', { extra: { connectionTimeoutMillis: Infinity } }, 5000],
    ['configured', { connectTimeoutMS: 321 }, 321],
    ['extra override', { connectTimeoutMS: 321, extra: { connectionTimeoutMillis: 654, max: 2 } }, 654],
    ['zero extra override', { connectTimeoutMS: 321, extra: { connectionTimeoutMillis: 0 } }, 5000],
];

describe('Postgres connection timeouts', () => {
    it.each(timeoutCases)('bounds a single address with %s timeout', async (_name, overrides, expected) => {
        const initialize = vi.spyOn(DataSource.prototype, 'initialize').mockRejectedValue(new Error('unreachable'));
        const candidate = { ...validConnection, host: '8.8.8.8', ...overrides };
        const originalExtra = candidate.extra ? { ...candidate.extra } : undefined;

        expect(await connectToPostgresCandidates([candidate])).toBeNull();

        const options = (initialize.mock.contexts[0] as DataSource).options as PostgresConnectionOptions;
        expect(options.connectTimeoutMS).toBe(expected);
        expect(options.extra).toEqual({ ...originalExtra, connectionTimeoutMillis: expected });
        expect(candidate.extra).toEqual(originalExtra);
    });

    it('times out a stalled single-address connection', async () => {
        vi.useFakeTimers();
        try {
            const originalConnect = Socket.prototype.connect;
            let attempts = 0;
            vi.spyOn(Socket.prototype, 'connect').mockImplementation(function (this: Socket, ...args: any[]) {
                if (args[0] === 5432 && args[1] === '8.8.8.8') {
                    attempts++;
                    return this;
                }
                return (originalConnect as any).apply(this, args);
            } as typeof Socket.prototype.connect);
            let settled = false;
            const pending = connectToPostgresCandidates([{ ...validConnection, host: '8.8.8.8', ssl: false }])
                .then((result) => {
                    settled = true;
                    return result;
                });

            await vi.advanceTimersByTimeAsync(4999);
            expect(attempts).toBe(1);
            expect(settled).toBe(false);
            await vi.advanceTimersByTimeAsync(1);
            await expect(pending).resolves.toBeNull();
        } finally {
            vi.useRealTimers();
        }
    });
});

describe('Postgres analysis and execution identity', () => {
    it('analyzes and executes using the same connection after one DNS lookup', async () => {
        const lookup = mockLookup([{ address: '1.1.1.1', family: 4 }]);
        lookup.mockResolvedValueOnce([{ address: '8.8.8.8', family: 4 }] as never);
        const initialize = mockReadyDataSource();
        const destroy = mockDataSourceDestroy();
        const analyze = mockSchemaAnalysis();
        const execute = vi.spyOn(QueryExecutionService.prototype, 'executeQuery')
            .mockResolvedValue({ rows: [{ value: 1 }], rowCount: 1 });
        const { req, res, status } = mockHttp();

        await createControllers().queryExecutionController.executeQuery(req, res);

        expect(status).toHaveBeenCalledWith(200);
        expect(lookup).toHaveBeenCalledTimes(1);
        expect(initialize).toHaveBeenCalledTimes(1);
        expect(execute.mock.calls[0][1]).toBe(analyze.mock.calls[0][0]);
        expect((analyze.mock.calls[0][0].options as PostgresConnectionOptions).connectTimeoutMS).toBe(5000);
        expect(destroy).toHaveBeenCalledTimes(1);
    });

    it('falls back from an unreachable IPv6 address before analyzing', async () => {
        const lookup = mockLookup([
            { address: '2001:4860:4860::8888', family: 6 },
            { address: '8.8.8.8', family: 4 },
        ]);
        const attempted: string[] = [];
        const timeouts: number[] = [];
        const tls: unknown[] = [];
        vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            const options = this.options as PostgresConnectionOptions;
            const host = options.host!;
            attempted.push(host);
            timeouts.push(options.extra.connectionTimeoutMillis);
            tls.push(options.ssl);
            if (host.includes(':')) throw new Error('unreachable');
            (this as any).isInitialized = true;
            return this;
        });
        mockDataSourceDestroy();
        const analyze = mockSchemaAnalysis();
        const execute = vi.spyOn(QueryExecutionService.prototype, 'executeQuery')
            .mockResolvedValue({ rows: [{ value: 1 }], rowCount: 1 });
        const { req, res, status } = mockHttp();

        await createControllers().queryExecutionController.executeQuery(req, res);

        expect(status).toHaveBeenCalledWith(200);
        expect(attempted).toEqual(['2001:4860:4860::8888', '8.8.8.8']);
        expect(timeouts).toEqual([5000, 5000]);
        expect(tls).toEqual([{ servername: 'db.example.com' }, { servername: 'db.example.com' }]);
        expect(lookup).toHaveBeenCalledTimes(1);
        expect(execute.mock.calls[0][1]).toBe(analyze.mock.calls[0][0]);
    });

    it('reuses cached metadata only for the selected address and database', async () => {
        const lookup = mockLookup([{ address: '1.1.1.1', family: 4 }]);
        lookup.mockResolvedValueOnce([{ address: '8.8.8.8', family: 4 }] as never);
        lookup.mockResolvedValueOnce([{ address: '8.8.8.8', family: 4 }] as never);
        mockReadyDataSource();
        const destroy = mockDataSourceDestroy();
        const analyze = mockSchemaAnalysis();
        vi.spyOn(QueryExecutionService.prototype, 'executeQuery').mockImplementation(async (_query, source) => ({
            rows: [{ host: (source.options as PostgresConnectionOptions).host }], rowCount: 1,
        }));
        const controller = createControllers().queryExecutionController;
        const first = mockHttp();
        const second = mockHttp();
        const third = mockHttp();

        await controller.executeQuery(first.req, first.res);
        await controller.executeQuery(second.req, second.res);
        await controller.executeQuery(third.req, third.res);

        expect(first.json).toHaveBeenCalledWith({ rows: [{ host: '8.8.8.8' }], rowCount: 1 });
        expect(second.json).toHaveBeenCalledWith({ rows: [{ host: '8.8.8.8' }], rowCount: 1 });
        expect(third.json).toHaveBeenCalledWith({ rows: [{ host: '1.1.1.1' }], rowCount: 1 });
        expect(analyze).toHaveBeenCalledTimes(2);
        expect(analyze.mock.calls[0][2]).not.toBe(analyze.mock.calls[1][2]);
        expect(databaseMetadata.size).toBe(2);
        expect(lookup).toHaveBeenCalledTimes(3);
        expect(destroy).toHaveBeenCalledTimes(3);
    });

    it('keeps concurrent analyses for different resolved addresses separate', async () => {
        const lookup = mockLookup([{ address: '1.1.1.1', family: 4 }]);
        lookup.mockResolvedValueOnce([{ address: '8.8.8.8', family: 4 }] as never);
        mockReadyDataSource();
        mockDataSourceDestroy();
        let releaseFirst!: () => void;
        const firstMayFinish = new Promise<void>((resolve) => { releaseFirst = resolve; });
        const analyze = vi.spyOn(DatabaseAnalyzer.prototype, 'extractDatabaseSchema').mockImplementation(async (source, _schema, key) => {
            if ((source.options as PostgresConnectionOptions).host === '8.8.8.8') {
                await firstMayFinish;
            } else {
                releaseFirst();
            }
            databaseMetadata.set(key, []);
            return true;
        });
        const execute = vi.spyOn(QueryExecutionService.prototype, 'executeQuery').mockResolvedValue({ rows: [], rowCount: 0 });
        const controller = createControllers().queryExecutionController;
        const first = mockHttp();
        const second = mockHttp();

        await Promise.all([
            controller.executeQuery(first.req, first.res),
            controller.executeQuery(second.req, second.res),
        ]);

        expect(first.status).toHaveBeenCalledWith(200);
        expect(second.status).toHaveBeenCalledWith(200);
        expect(analyze).toHaveBeenCalledTimes(2);
        expect(analyze.mock.calls[0][2]).not.toBe(analyze.mock.calls[1][2]);
        expect(execute.mock.calls.map((call) => call[1])).toEqual(expect.arrayContaining([
            analyze.mock.calls[0][0], analyze.mock.calls[1][0],
        ]));
        expect(databaseMetadata.size).toBe(2);
        expect(lookup).toHaveBeenCalledTimes(2);
    });

    it.each(['database', 'username'])('does not reuse metadata across different %s values', async (field) => {
        mockLookup([{ address: '8.8.8.8', family: 4 }]);
        mockReadyDataSource();
        mockDataSourceDestroy();
        const analyze = mockSchemaAnalysis();
        vi.spyOn(QueryExecutionService.prototype, 'executeQuery').mockResolvedValue({ rows: [], rowCount: 0 });
        const controller = createControllers().queryExecutionController;
        const first = mockHttp();
        const second = mockHttp();
        first.req.body.connectionInfo.database = 'shared';
        second.req.body.connectionInfo.database = 'shared';
        first.req.body.connectionInfo[field] = 'one';
        second.req.body.connectionInfo[field] = 'two';

        await controller.executeQuery(first.req, first.res);
        await controller.executeQuery(second.req, second.res);

        expect(analyze).toHaveBeenCalledTimes(2);
        expect(analyze.mock.calls[0][2]).not.toBe(analyze.mock.calls[1][2]);
    });

    it('honors a configured connection timeout across fallback candidates', async () => {
        mockLookup([
            { address: '2001:4860:4860::8888', family: 6 },
            { address: '8.8.8.8', family: 4 },
        ]);
        const timeouts: number[] = [];
        vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            timeouts.push((this.options as PostgresConnectionOptions).extra.connectionTimeoutMillis);
            throw new Error('unreachable');
        });
        const { req, res, status } = mockHttp();
        req.body.connectionInfo.extra = { connectionTimeoutMillis: 321 };

        await createControllers().queryExecutionController.executeQuery(req, res);

        expect(status).toHaveBeenCalledWith(400);
        expect(timeouts).toEqual([321, 321]);
    });

    it('closes a partially initialized candidate before trying the next one', async () => {
        mockLookup([
            { address: '2001:4860:4860::8888', family: 6 },
            { address: '8.8.8.8', family: 4 },
        ]);
        const events: string[] = [];
        vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            const host = (this.options as PostgresConnectionOptions).host!;
            events.push(`connect:${host}`);
            (this as any).isInitialized = true;
            if (host.includes(':')) throw new Error('failed after connecting');
            return this;
        });
        vi.spyOn(DataSource.prototype, 'destroy').mockImplementation(async function (this: DataSource) {
            events.push(`close:${(this.options as PostgresConnectionOptions).host}`);
            (this as any).isInitialized = false;
        });
        mockSchemaAnalysis();
        vi.spyOn(QueryExecutionService.prototype, 'executeQuery').mockResolvedValue({ rows: [], rowCount: 0 });
        const { req, res, status } = mockHttp();

        await createControllers().queryExecutionController.executeQuery(req, res);

        expect(status).toHaveBeenCalledWith(200);
        expect(events).toEqual([
            'connect:2001:4860:4860::8888',
            'close:2001:4860:4860::8888',
            'connect:8.8.8.8',
            'close:8.8.8.8',
        ]);
    });

    it('closes a partially created pool before trying another address', async () => {
        mockLookup([
            { address: '2001:4860:4860::8888', family: 6 },
            { address: '8.8.8.8', family: 4 },
        ]);
        const events: string[] = [];
        vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            const host = (this.options as PostgresConnectionOptions).host!;
            events.push(`connect:${host}`);
            if (host.includes(':')) {
                const driver = this.driver as any;
                driver.master = {};
                vi.spyOn(driver, 'disconnect').mockImplementation(async () => {
                    events.push(`disconnect:${host}`);
                    driver.master = undefined;
                });
                throw new Error('driver initialization failed');
            }
            (this as any).isInitialized = true;
            return this;
        });
        vi.spyOn(DataSource.prototype, 'destroy').mockImplementation(async function (this: DataSource) {
            events.push(`close:${(this.options as PostgresConnectionOptions).host}`);
            (this as any).isInitialized = false;
        });
        mockSchemaAnalysis();
        vi.spyOn(QueryExecutionService.prototype, 'executeQuery').mockResolvedValue({ rows: [], rowCount: 0 });
        const { req, res, status } = mockHttp();

        await createControllers().queryExecutionController.executeQuery(req, res);

        expect(status).toHaveBeenCalledWith(200);
        expect(events).toEqual([
            'connect:2001:4860:4860::8888',
            'disconnect:2001:4860:4860::8888',
            'connect:8.8.8.8',
            'close:8.8.8.8',
        ]);
    });

    it('reports failure after every validated address is unreachable', async () => {
        const lookup = mockLookup([
            { address: '2001:4860:4860::8888', family: 6 },
            { address: '8.8.8.8', family: 4 },
        ]);
        const attempted: string[] = [];
        vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            attempted.push((this.options as PostgresConnectionOptions).host!);
            throw new Error('unreachable');
        });
        const analyze = vi.spyOn(DatabaseAnalyzer.prototype, 'extractDatabaseSchema');
        const { req, res, status, json } = mockHttp();

        await createControllers().queryExecutionController.executeQuery(req, res);

        expect(status).toHaveBeenCalledWith(400);
        expect(json).toHaveBeenCalledWith({ message: t('UNABLE_TO_CONNECT', 'en') });
        expect(attempted).toEqual(['2001:4860:4860::8888', '8.8.8.8']);
        expect(analyze).not.toHaveBeenCalled();
        expect(lookup).toHaveBeenCalledTimes(1);
    });

    it('only retries registered addresses when auto-analysis is unavailable', async () => {
        const lookup = mockLookup([
            { address: '2001:4860:4860::8888', family: 6 },
            { address: '8.8.8.8', family: 4 },
            { address: '1.1.1.1', family: 4 },
        ]);
        for (const host of ['2001:4860:4860::8888', '8.8.8.8']) {
            databaseMetadata.set(generatePostgresDatabaseKey(validConnection.host, { ...validConnection, host }), []);
        }
        const attempted: string[] = [];
        vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            const host = (this.options as PostgresConnectionOptions).host!;
            attempted.push(host);
            if (host.includes(':')) throw new Error('unreachable');
            (this as any).isInitialized = true;
            return this;
        });
        const destroy = mockDataSourceDestroy();
        const service = new QueryExecutionService();
        const execute = vi.spyOn(service, 'executeQuery').mockResolvedValue({ rows: [], rowCount: 0 });
        const { req, res, status } = mockHttp();

        await new QueryExecutionController(service).executeQuery(req, res);

        expect(status).toHaveBeenCalledWith(200);
        expect(attempted).toEqual(['2001:4860:4860::8888', '8.8.8.8']);
        expect((execute.mock.calls[0][1].options as PostgresConnectionOptions).host).toBe('8.8.8.8');
        expect(lookup).toHaveBeenCalledTimes(1);
        expect(destroy).toHaveBeenCalledTimes(1);
    });

    it('never connects to an unregistered fallback without auto-analysis', async () => {
        mockLookup([
            { address: '8.8.8.8', family: 4 },
            { address: '1.1.1.1', family: 4 },
        ]);
        databaseMetadata.set(generatePostgresDatabaseKey(validConnection.host, { ...validConnection, host: '8.8.8.8' }), []);
        const attempted: string[] = [];
        vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            attempted.push((this.options as PostgresConnectionOptions).host!);
            throw new Error('unreachable');
        });
        const service = new QueryExecutionService();
        const execute = vi.spyOn(service, 'executeQuery');
        const { req, res, status, json } = mockHttp();

        await new QueryExecutionController(service).executeQuery(req, res);

        expect(status).toHaveBeenCalledWith(400);
        expect(json).toHaveBeenCalledWith({ message: t('UNABLE_TO_CONNECT', 'en') });
        expect(attempted).toEqual(['8.8.8.8']);
        expect(execute).not.toHaveBeenCalled();
    });

    it('does not retry another server after execution begins', async () => {
        const lookup = mockLookup([
            { address: '8.8.8.8', family: 4 },
            { address: '1.1.1.1', family: 4 },
        ]);
        const attempted: string[] = [];
        vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            attempted.push((this.options as PostgresConnectionOptions).host!);
            (this as any).isInitialized = true;
            return this;
        });
        const destroy = mockDataSourceDestroy();
        mockSchemaAnalysis();
        vi.spyOn(QueryExecutionService.prototype, 'executeQuery').mockRejectedValue(new Error('query failed'));
        const { req, res, status } = mockHttp();

        await createControllers().queryExecutionController.executeQuery(req, res);

        expect(status).toHaveBeenCalledWith(500);
        expect(attempted).toEqual(['8.8.8.8']);
        expect(destroy).toHaveBeenCalledTimes(1);
        expect(lookup).toHaveBeenCalledTimes(1);
    });

    it('does not switch servers after schema extraction fails', async () => {
        mockLookup([
            { address: '8.8.8.8', family: 4 },
            { address: '1.1.1.1', family: 4 },
        ]);
        const attempted: string[] = [];
        vi.spyOn(DataSource.prototype, 'initialize').mockImplementation(async function (this: DataSource) {
            attempted.push((this.options as PostgresConnectionOptions).host!);
            (this as any).isInitialized = true;
            return this;
        });
        const destroy = mockDataSourceDestroy();
        vi.spyOn(DatabaseAnalyzer.prototype, 'extractDatabaseSchema').mockResolvedValue(false);
        const execute = vi.spyOn(QueryExecutionService.prototype, 'executeQuery');
        const { req, res, status } = mockHttp();

        await createControllers().queryExecutionController.executeQuery(req, res);

        expect(status).toHaveBeenCalledWith(500);
        expect(attempted).toEqual(['8.8.8.8']);
        expect(destroy).toHaveBeenCalledTimes(1);
        expect(execute).not.toHaveBeenCalled();
    });
});
