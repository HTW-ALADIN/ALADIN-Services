import { describe, it, expect, beforeAll, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { PGlite } from '@electric-sql/pglite';
import { DatabaseAnalyzer } from '../../src/database/database-analyzer';
import { DatabaseService } from '../../src/database/database-service';
import {
	databaseMetadata,
	pgliteInstances,
} from '../../src/database/internal-memory';
import { generatePGliteKey } from '../../src/shared/utils/database-utils';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SIMPLE_DDL = `
CREATE TABLE items (
  id   SERIAL PRIMARY KEY,
  name TEXT NOT NULL
);
INSERT INTO items (name) VALUES ('alpha'), ('beta');
`;

const DB_ID = 'svc-test-db';
const DB_KEY = generatePGliteKey(DB_ID);

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

// Warm up PGlite WASM once per worker thread so individual tests don't pay
// the cold-start cost and hit the default 5 s timeout in CI.
beforeAll(async () => {
	const db = new PGlite();
	await db.close();
});

describe('DatabaseService — ensureAnalyzed', () => {
	let service: DatabaseService;

	beforeEach(() => {
		service = new DatabaseService(new DatabaseAnalyzer());
		databaseMetadata.clear();
		pgliteInstances.clear();
	});

	afterEach(async () => {
		for (const db of pgliteInstances.values()) {
			await db?.close?.();
		}
		pgliteInstances.clear();
		databaseMetadata.clear();
	});

	// ── PGlite ──────────────────────────────────────────────────────────────

	describe('PGlite', () => {
		it('creates instance and registers metadata when sqlContent is provided', async () => {
			const result = await service.ensureAnalyzed({
				type: 'pglite',
				databaseId: DB_ID,
				sqlContent: SIMPLE_DDL,
			});

			expect(result.ok).toBe(true);
			expect(databaseMetadata.has(DB_KEY)).toBe(true);
			expect(pgliteInstances.has(DB_ID)).toBe(true);
		});

		it('replaces an existing PGlite instance when called again with same databaseId', async () => {
			await service.ensureAnalyzed({
				type: 'pglite',
				databaseId: DB_ID,
				sqlContent: SIMPLE_DDL,
			});
			const firstDb = pgliteInstances.get(DB_ID);

			await service.ensureAnalyzed({
				type: 'pglite',
				databaseId: DB_ID,
				sqlContent: SIMPLE_DDL,
			});
			const secondDb = pgliteInstances.get(DB_ID);

			expect(secondDb).not.toBe(firstDb);
		});

		it('skips silently (ok:true) when sqlContent is absent and required=false', async () => {
			const result = await service.ensureAnalyzed({
				type: 'pglite',
				databaseId: DB_ID,
				// no sqlContent
			});

			expect(result.ok).toBe(true);
			expect(result.status).toBe(200);
			// Nothing was registered
			expect(databaseMetadata.has(DB_KEY)).toBe(false);
		});

		it('returns 400 when sqlContent is an empty string (required=false)', async () => {
			const result = await service.ensureAnalyzed({
				type: 'pglite',
				databaseId: DB_ID,
				sqlContent: '',
			});

			expect(result.ok).toBe(false);
			expect(result.status).toBe(400);
		});

		it('returns 400 when sqlContent is an empty string (required=true)', async () => {
			const result = await service.ensureAnalyzed(
				{ type: 'pglite', databaseId: DB_ID, sqlContent: '' },
				undefined,
				'en',
				true,
			);

			expect(result.ok).toBe(false);
			expect(result.status).toBe(400);
		});

		it('returns 400 when sqlContent is absent and required=true', async () => {
			const result = await service.ensureAnalyzed(
				{ type: 'pglite', databaseId: DB_ID },
				undefined,
				'en',
				true,
			);

			expect(result.ok).toBe(false);
			expect(result.status).toBe(400);
		});

		it('returns 400 when databaseId is missing', async () => {
			const result = await service.ensureAnalyzed({
				type: 'pglite',
				sqlContent: SIMPLE_DDL,
				// no databaseId
			});

			expect(result.ok).toBe(false);
			expect(result.status).toBe(400);
		});

		it('returns 500 when sqlContent contains invalid SQL', async () => {
			const result = await service.ensureAnalyzed({
				type: 'pglite',
				databaseId: DB_ID,
				sqlContent: 'THIS IS NOT SQL @@##!!',
			});

			expect(result.ok).toBe(false);
			expect(result.status).toBe(500);
		});
	});

	// ── Missing connectionInfo ───────────────────────────────────────────────

	it('returns 400 when connectionInfo is null/undefined', async () => {
		const result = await service.ensureAnalyzed(null);
		expect(result.ok).toBe(false);
		expect(result.status).toBe(400);
	});
});

// ---------------------------------------------------------------------------
// Init-SQL file feature
// ---------------------------------------------------------------------------

describe('DatabaseService — initSqlFilePath', () => {
	let tmpFile: string;
	let service: DatabaseService;

	beforeEach(() => {
		// Write SIMPLE_DDL to a temp file
		tmpFile = path.join(os.tmpdir(), `pglite-test-${Date.now()}.sql`);
		fs.writeFileSync(tmpFile, SIMPLE_DDL, 'utf-8');

		service = new DatabaseService(new DatabaseAnalyzer(), tmpFile);
		databaseMetadata.clear();
		pgliteInstances.clear();
	});

	afterEach(async () => {
		// Use a Set to avoid closing a shared instance more than once.
		for (const db of new Set(pgliteInstances.values())) {
			await db?.close?.();
		}
		pgliteInstances.clear();
		databaseMetadata.clear();
		try {
			fs.unlinkSync(tmpFile);
		} catch {
			/* ignore */
		}
	});

	it('uses the init SQL file when sqlContent is absent from the request', async () => {
		const result = await service.ensureAnalyzed({
			type: 'pglite',
			databaseId: DB_ID,
			// no sqlContent — should fall back to tmpFile
		});

		expect(result.ok).toBe(true);
		expect(databaseMetadata.has(DB_KEY)).toBe(true);
		expect(pgliteInstances.has(DB_ID)).toBe(true);
	});

	it('request-level sqlContent takes priority over the init SQL file', async () => {
		const overrideDDL = `
			CREATE TABLE override_table (id SERIAL PRIMARY KEY, val TEXT NOT NULL);
			INSERT INTO override_table (val) VALUES ('x');
		`;
		const result = await service.ensureAnalyzed({
			type: 'pglite',
			databaseId: DB_ID,
			sqlContent: overrideDDL,
		});

		expect(result.ok).toBe(true);
		// The schema should contain override_table, not items
		const tables = databaseMetadata.get(DB_KEY) ?? [];
		const tableNames = tables.map((t: any) => t.name ?? t.tableName ?? t.table);
		expect(tableNames.some((n: string) => n?.includes('override'))).toBe(true);
	});

	it('returns 500 when the configured file path does not exist', async () => {
		const badService = new DatabaseService(
			new DatabaseAnalyzer(),
			'/nonexistent/path/init.sql',
		);
		const result = await badService.ensureAnalyzed({
			type: 'pglite',
			databaseId: DB_ID,
		});

		expect(result.ok).toBe(false);
		expect(result.status).toBe(500);
	});

	it('skips the file when sqlContent is absent and required=true (file counts as content)', async () => {
		// With initSqlFilePath set, even required=true should succeed because
		// the file provides the sqlContent
		const result = await service.ensureAnalyzed(
			{ type: 'pglite', databaseId: DB_ID },
			undefined,
			'en',
			true,
		);
		expect(result.ok).toBe(true);
	});

	it('multiple databaseIds without sqlContent share a single PGlite instance', async () => {
		const r1 = await service.ensureAnalyzed({
			type: 'pglite',
			databaseId: 'db-a',
		});
		const r2 = await service.ensureAnalyzed({
			type: 'pglite',
			databaseId: 'db-b',
		});

		expect(r1.ok).toBe(true);
		expect(r2.ok).toBe(true);
		// Both databaseIds must resolve to the same in-memory PGlite object.
		expect(pgliteInstances.get('db-a')).toBe(pgliteInstances.get('db-b'));
	});

	it('concurrent calls without sqlContent create only one shared PGlite instance', async () => {
		// Fire both registrations concurrently — without the Promise-coalescing
		// fix the two calls would each pass the "!cachedInitSqlPGlite" guard
		// before either await chain completes, spawning two PGlite instances
		// and leaking the first one.
		const [r1, r2] = await Promise.all([
			service.ensureAnalyzed({ type: 'pglite', databaseId: 'db-concurrent-1' }),
			service.ensureAnalyzed({ type: 'pglite', databaseId: 'db-concurrent-2' }),
		]);

		expect(r1.ok).toBe(true);
		expect(r2.ok).toBe(true);
		// Both ids must point to the exact same PGlite object (shared singleton).
		expect(pgliteInstances.get('db-concurrent-1')).toBe(
			pgliteInstances.get('db-concurrent-2'),
		);
	});
});
