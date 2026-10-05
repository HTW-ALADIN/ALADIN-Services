/**
 * Integration tests verifying that the QueryExecutionController and
 * QueryExecutionService return correctly localised error messages when a
 * languageCode is supplied in the request.
 *
 * These tests use the pg-mem in-memory database so no real Postgres server
 * is needed, and lightweight Express mocks so no HTTP server is needed.
 */

import { describe, it, expect, beforeAll, beforeEach, afterAll, vi } from 'vitest';
import { Request, Response } from 'express';
import { IMemoryDb, IBackup } from 'pg-mem';
import { DataSource } from 'typeorm';
import { createTestDb } from '../helpers/pg-mem-factory';
import { QueryExecutionController } from '../../src/query/query-execution-controller';
import { QueryExecutionService } from '../../src/query/query-execution-service';
import { databaseMetadata } from '../../src/database/internal-memory';
import { t } from '../../src/shared/i18n';

// ---------------------------------------------------------------------------
// Express mock helpers
// ---------------------------------------------------------------------------

function mockReq(body: unknown): Request {
    return { body } as Request;
}

function mockRes() {
    const json = vi.fn().mockReturnThis();
    const status = vi.fn().mockReturnValue({ json });
    return { res: { status, json } as unknown as Response, status, json };
}

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------

const VALID_CONNECTION = {
    type: 'postgres' as const,
    // Use a public, non-loopback/private host: validateConnectionInfo() blocks
    // internal connection targets (SSRF protection), so 'localhost' would be
    // rejected before the request ever reaches the branch under test.
    host: 'db.example.com',
    port: 5432,
    username: 'user',
    password: 'pass',
    schema: 'northwind',
};
const DB_KEY = 'db.example.com:5432/northwind';

let db: IMemoryDb;
let backup: IBackup;
let dataSource: DataSource;
let service: QueryExecutionService;
let controller: QueryExecutionController;

beforeAll(async () => {
    ({ db, backup, dataSource } = await createTestDb());
});

beforeEach(() => {
    backup.restore();
    databaseMetadata.set(DB_KEY, []);
    service = new QueryExecutionService();
    controller = new QueryExecutionController(service);
});

afterAll(async () => {
    await dataSource.destroy();
});

// ---------------------------------------------------------------------------
// Controller — request-validation messages (no DB needed)
// ---------------------------------------------------------------------------

describe('QueryExecutionController i18n — request validation', () => {

    it('returns English "missing connectionInfo" when no languageCode given', async () => {
        const { res, status, json } = mockRes();
        await controller.executeQuery(mockReq({ query: 'SELECT 1' }), res);
        expect(status).toHaveBeenCalledWith(400);
        expect(json).toHaveBeenCalledWith(
            expect.objectContaining({ message: t('MISSING_CONNECTION_INFO', 'en') })
        );
    });

    it('returns German "missing connectionInfo" when languageCode is "de"', async () => {
        const { res, status, json } = mockRes();
        await controller.executeQuery(
            mockReq({ query: 'SELECT 1', languageCode: 'de' }),
            res
        );
        expect(status).toHaveBeenCalledWith(400);
        expect(json).toHaveBeenCalledWith(
            expect.objectContaining({ message: t('MISSING_CONNECTION_INFO', 'de') })
        );
    });

    it('returns English "missing or empty query" message in English', async () => {
        const { res, json } = mockRes();
        await controller.executeQuery(
            mockReq({ connectionInfo: VALID_CONNECTION, query: '', languageCode: 'en' }),
            res
        );
        expect(json).toHaveBeenCalledWith(
            expect.objectContaining({ message: t('MISSING_OR_EMPTY_QUERY', 'en') })
        );
    });

    it('returns German "missing or empty query" message when languageCode is "de"', async () => {
        const { res, json } = mockRes();
        await controller.executeQuery(
            mockReq({ connectionInfo: VALID_CONNECTION, query: '', languageCode: 'de' }),
            res
        );
        expect(json).toHaveBeenCalledWith(
            expect.objectContaining({ message: t('MISSING_OR_EMPTY_QUERY', 'de') })
        );
    });

    it('returns English "invalid connection info" for incomplete connectionInfo', async () => {
        const { res, json } = mockRes();
        await controller.executeQuery(
            mockReq({
                connectionInfo: { host: 'localhost' }, // missing port, username, password, schema
                query: 'SELECT 1',
                languageCode: 'en',
            }),
            res
        );
        expect(json).toHaveBeenCalledWith(
            expect.objectContaining({ message: t('INVALID_CONNECTION_INFO', 'en') })
        );
    });

    it('returns German "invalid connection info" for incomplete connectionInfo', async () => {
        const { res, json } = mockRes();
        await controller.executeQuery(
            mockReq({
                connectionInfo: { host: 'localhost' },
                query: 'SELECT 1',
                languageCode: 'de',
            }),
            res
        );
        expect(json).toHaveBeenCalledWith(
            expect.objectContaining({ message: t('INVALID_CONNECTION_INFO', 'de') })
        );
    });

    it('returns English "database not registered" when DB key is absent', async () => {
        databaseMetadata.delete(DB_KEY);
        const { res, json } = mockRes();
        await controller.executeQuery(
            mockReq({ connectionInfo: VALID_CONNECTION, query: 'SELECT 1', languageCode: 'en' }),
            res
        );
        expect(json).toHaveBeenCalledWith(
            expect.objectContaining({ message: t('DATABASE_NOT_REGISTERED', 'en') })
        );
    });

    it('returns German "database not registered" when DB key is absent and languageCode is "de"', async () => {
        databaseMetadata.delete(DB_KEY);
        const { res, json } = mockRes();
        await controller.executeQuery(
            mockReq({ connectionInfo: VALID_CONNECTION, query: 'SELECT 1', languageCode: 'de' }),
            res
        );
        expect(json).toHaveBeenCalledWith(
            expect.objectContaining({ message: t('DATABASE_NOT_REGISTERED', 'de') })
        );
    });

    it('falls back to English for an unknown language code', async () => {
        const { res, json } = mockRes();
        await controller.executeQuery(
            mockReq({ connectionInfo: VALID_CONNECTION, query: '', languageCode: 'fr' }),
            res
        );
        expect(json).toHaveBeenCalledWith(
            expect.objectContaining({ message: t('MISSING_OR_EMPTY_QUERY', 'en') })
        );
    });

    it('falls back to English when languageCode is absent', async () => {
        const { res, json } = mockRes();
        await controller.executeQuery(
            mockReq({ connectionInfo: VALID_CONNECTION, query: '' }),
            res
        );
        expect(json).toHaveBeenCalledWith(
            expect.objectContaining({ message: t('MISSING_OR_EMPTY_QUERY', 'en') })
        );
    });

});

// ---------------------------------------------------------------------------
// Service — localised error messages thrown directly
// ---------------------------------------------------------------------------

describe('QueryExecutionService i18n — thrown error messages', () => {

    it('throws English QUERY_EMPTY message for an empty string', async () => {
        await expect(service.executeQuery('', dataSource, 'en'))
            .rejects.toThrow(t('QUERY_EMPTY', 'en'));
    });

    it('throws German QUERY_EMPTY message for an empty string when lang is "de"', async () => {
        await expect(service.executeQuery('', dataSource, 'de'))
            .rejects.toThrow(t('QUERY_EMPTY', 'de'));
    });

    it('throws English QUERY_PARSE_ERROR for non-SQL text', async () => {
        await expect(service.executeQuery('this is not sql', dataSource, 'en'))
            .rejects.toThrow(t('QUERY_PARSE_ERROR', 'en'));
    });

    it('throws German QUERY_PARSE_ERROR for non-SQL text', async () => {
        await expect(service.executeQuery('this is not sql', dataSource, 'de'))
            .rejects.toThrow(t('QUERY_PARSE_ERROR', 'de'));
    });

    it('throws English QUERY_MULTIPLE_STATEMENTS for two statements', async () => {
        await expect(
            service.executeQuery(
                'SELECT * FROM northwind.products; SELECT * FROM northwind.orders',
                dataSource,
                'en'
            )
        ).rejects.toThrow(t('QUERY_MULTIPLE_STATEMENTS', 'en'));
    });

    it('throws German QUERY_MULTIPLE_STATEMENTS for two statements', async () => {
        await expect(
            service.executeQuery(
                'SELECT * FROM northwind.products; SELECT * FROM northwind.orders',
                dataSource,
                'de'
            )
        ).rejects.toThrow(t('QUERY_MULTIPLE_STATEMENTS', 'de'));
    });

    it('throws English NON_SELECT message for an INSERT', async () => {
        await expect(
            service.executeQuery(
                "INSERT INTO northwind.categories (category_name) VALUES ('X')",
                dataSource,
                'en'
            )
        ).rejects.toThrow('Only SELECT queries are permitted');
    });

    it('throws German NON_SELECT message for an INSERT', async () => {
        await expect(
            service.executeQuery(
                "INSERT INTO northwind.categories (category_name) VALUES ('X')",
                dataSource,
                'de'
            )
        ).rejects.toThrow('Nur SELECT-Abfragen');
    });

    it('throws English EXECUTION_FAILED for a SELECT on a non-existent table', async () => {
        await expect(
            service.executeQuery(
                'SELECT * FROM northwind.ghost_table',
                dataSource,
                'en'
            )
        ).rejects.toThrow('Query execution failed');
    });

    it('throws German EXECUTION_FAILED for a SELECT on a non-existent table', async () => {
        await expect(
            service.executeQuery(
                'SELECT * FROM northwind.ghost_table',
                dataSource,
                'de'
            )
        ).rejects.toThrow('Abfrageausführung fehlgeschlagen');
    });

    it('English and German error messages for the same error are different', async () => {
        let enMsg = '';
        let deMsg = '';
        try { await service.executeQuery('', dataSource, 'en'); } catch (e: any) { enMsg = e.message; }
        try { await service.executeQuery('', dataSource, 'de'); } catch (e: any) { deMsg = e.message; }
        expect(enMsg).not.toBe(deMsg);
    });

});
