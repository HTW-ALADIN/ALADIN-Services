import {
	describe,
	it,
	expect,
	beforeAll,
	beforeEach,
	afterEach,
	vi,
} from 'vitest';
import { PGlite } from '@electric-sql/pglite';
import type { Request, Response } from 'express';
import { DatabaseController } from '../../src/database/database-controller';
import { DatabaseAnalyzer } from '../../src/database/database-analyzer';
import {
	databaseMetadata,
	pgliteInstances,
} from '../../src/database/internal-memory';
import { generatePGliteKey } from '../../src/shared/utils/database-utils';
import { RelationshipType } from '../../src/shared/interfaces/domain';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/**
 * Minimal two-table schema (public schema — PGlite default) with a FK
 * relationship and a small seed dataset.
 */
const SIMPLE_DDL = `
CREATE TABLE products (
  id   SERIAL PRIMARY KEY,
  name TEXT          NOT NULL,
  price NUMERIC(10,2)
);
CREATE TABLE orders (
  id         SERIAL PRIMARY KEY,
  product_id INTEGER REFERENCES products(id),
  quantity   INTEGER NOT NULL
);
INSERT INTO products (name, price) VALUES ('Widget', 9.99), ('Gadget', 19.99);
INSERT INTO orders  (product_id, quantity) VALUES (1, 5), (2, 3);
`;

const VALID_PGLITE_INFO = {
	type: 'pglite' as const,
	databaseId: 'test-db',
	sqlContent: SIMPLE_DDL,
};

// ---------------------------------------------------------------------------
// Express mock helpers (same pattern as query-execution-controller.test.ts)
// ---------------------------------------------------------------------------

function mockReq(body: unknown): Request {
	return { body } as Request;
}

function mockRes() {
	const json = vi.fn().mockReturnThis();
	const status = vi.fn().mockReturnValue({ json });
	return { res: { status, json } as unknown as Response, status, json };
}

// Warm up PGlite WASM once per worker thread so individual tests don't pay
// the cold-start cost and hit the default timeout in CI.
beforeAll(async () => {
	const db = new PGlite();
	await db.close();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DatabaseController — PGlite path', () => {
	let controller: DatabaseController;

	beforeEach(() => {
		controller = new DatabaseController(new DatabaseAnalyzer());
		databaseMetadata.clear();
		pgliteInstances.clear();
	});

	afterEach(async () => {
		// Close any open PGlite instances to avoid resource leaks.
		for (const db of pgliteInstances.values()) {
			await db?.close?.();
		}
		pgliteInstances.clear();
		databaseMetadata.clear();
	});

	// -----------------------------------------------------------------------
	// Request validation
	// -----------------------------------------------------------------------

	describe('analyzeDatabase — PGlite request validation', () => {
		it('returns 400 when databaseId is missing', async () => {
			const { res, status } = mockRes();
			await controller.analyzeDatabase(
				mockReq({ connectionInfo: { type: 'pglite', sqlContent: SIMPLE_DDL } }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when sqlContent is missing', async () => {
			const { res, status } = mockRes();
			await controller.analyzeDatabase(
				mockReq({ connectionInfo: { type: 'pglite', databaseId: 'test-db' } }),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when sqlContent is not a string', async () => {
			const { res, status } = mockRes();
			await controller.analyzeDatabase(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: 'test-db',
						sqlContent: 42,
					},
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when sqlContent is an empty string', async () => {
			const { res, status } = mockRes();
			await controller.analyzeDatabase(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: 'test-db',
						sqlContent: '',
					},
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});

		it('returns 400 when databaseId is not a string', async () => {
			const { res, status } = mockRes();
			await controller.analyzeDatabase(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: 123,
						sqlContent: SIMPLE_DDL,
					},
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(400);
		});
	});

	// -----------------------------------------------------------------------
	// Integration (real PGlite)
	// -----------------------------------------------------------------------

	describe('analyzeDatabase — PGlite integration', () => {
		it('returns 200 for valid DDL', async () => {
			const { res, status } = mockRes();
			await controller.analyzeDatabase(
				mockReq({ connectionInfo: VALID_PGLITE_INFO }),
				res,
			);
			expect(status).toHaveBeenCalledWith(200);
		});

		it('registers database metadata under the PGlite key', async () => {
			const { res } = mockRes();
			await controller.analyzeDatabase(
				mockReq({ connectionInfo: VALID_PGLITE_INFO }),
				res,
			);
			expect(databaseMetadata.has(generatePGliteKey('test-db'))).toBe(true);
		});

		it('reflects table names into metadata', async () => {
			const { res } = mockRes();
			await controller.analyzeDatabase(
				mockReq({ connectionInfo: VALID_PGLITE_INFO }),
				res,
			);
			const tables = databaseMetadata.get(generatePGliteKey('test-db'));
			const names = tables!.map((t) => t.name);
			expect(names).toContain('products');
			expect(names).toContain('orders');
		});

		it('stores the PGlite instance for later query execution', async () => {
			const { res } = mockRes();
			await controller.analyzeDatabase(
				mockReq({ connectionInfo: VALID_PGLITE_INFO }),
				res,
			);
			expect(pgliteInstances.has('test-db')).toBe(true);
		});

		it('returns 500 when sqlContent contains invalid SQL', async () => {
			const { res, status } = mockRes();
			await controller.analyzeDatabase(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: 'bad-db',
						sqlContent: 'THIS IS NOT VALID SQL AT ALL !!!',
					},
				}),
				res,
			);
			expect(status).toHaveBeenCalledWith(500);
		});

		it('replaces an existing PGlite instance when databaseId is reused', async () => {
			// First call — products + orders schema
			await controller.analyzeDatabase(
				mockReq({ connectionInfo: VALID_PGLITE_INFO }),
				mockRes().res,
			);
			const firstInstance = pgliteInstances.get('test-db');

			// Second call — completely different schema, same databaseId
			const { res, status } = mockRes();
			await controller.analyzeDatabase(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: 'test-db',
						sqlContent:
							'CREATE TABLE categories (id SERIAL PRIMARY KEY, label TEXT NOT NULL);',
					},
				}),
				res,
			);

			expect(status).toHaveBeenCalledWith(200);
			const tables = databaseMetadata.get(generatePGliteKey('test-db'));
			expect(tables!.map((t) => t.name)).toContain('categories');
			expect(tables!.map((t) => t.name)).not.toContain('products');
			// A new PGlite instance must replace the old one
			expect(pgliteInstances.get('test-db')).not.toBe(firstInstance);
		});
	});

	// -----------------------------------------------------------------------
	// UNIQUE constraint cardinality classification
	// -----------------------------------------------------------------------

	describe('analyzeDatabase — UNIQUE constraint cardinality', () => {
		/**
		 * A composite UNIQUE(order_id, product_id) must NOT make either FK column
		 * look individually unique.  Both FK relationships should remain 1:N.
		 */
		it('classifies FK as 1:N when it participates in a composite UNIQUE constraint', async () => {
			const ddl = `
				CREATE TABLE products  (id SERIAL PRIMARY KEY, name TEXT NOT NULL);
				CREATE TABLE customers (id SERIAL PRIMARY KEY, name TEXT NOT NULL);
				CREATE TABLE orders (
					id          SERIAL  PRIMARY KEY,
					product_id  INTEGER NOT NULL REFERENCES products(id),
					customer_id INTEGER NOT NULL REFERENCES customers(id),
					UNIQUE (product_id, customer_id)
				);
			`;
			const { res } = mockRes();
			await controller.analyzeDatabase(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: 'uq-composite',
						sqlContent: ddl,
					},
				}),
				res,
			);

			const tables = databaseMetadata.get(generatePGliteKey('uq-composite'))!;
			const orders = tables.find((t) => t.name === 'orders')!;

			for (const rel of orders.relationships) {
				expect(rel.cardinality).toBe(RelationshipType.OneToMany);
			}
		});

		/**
		 * A single-column UNIQUE on a FK column IS a genuine 1:1 indicator and
		 * the relationship should be classified accordingly.
		 */
		it('classifies FK as 1:1 when it has a single-column UNIQUE constraint', async () => {
			const ddl = `
				CREATE TABLE users    (id SERIAL PRIMARY KEY, name TEXT NOT NULL);
				CREATE TABLE profiles (
					id      SERIAL  PRIMARY KEY,
					user_id INTEGER NOT NULL UNIQUE REFERENCES users(id)
				);
			`;
			const { res } = mockRes();
			await controller.analyzeDatabase(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: 'uq-single',
						sqlContent: ddl,
					},
				}),
				res,
			);

			const tables = databaseMetadata.get(generatePGliteKey('uq-single'))!;
			const profiles = tables.find((t) => t.name === 'profiles')!;
			const rel = profiles.relationships.find(
				(r) => r.referencedTable === 'users',
			)!;

			expect(rel.cardinality).toBe(RelationshipType.OneToOne);
		});

		/**
		 * A single-column CREATE UNIQUE INDEX on a FK column must be treated the
		 * same as a UNIQUE constraint: the relationship should be classified as 1:1.
		 */
		it('classifies FK as 1:1 when it has a single-column CREATE UNIQUE INDEX', async () => {
			const ddl = `
				CREATE TABLE users    (id SERIAL PRIMARY KEY, name TEXT NOT NULL);
				CREATE TABLE profiles (
					id      SERIAL  PRIMARY KEY,
					user_id INTEGER NOT NULL REFERENCES users(id)
				);
				CREATE UNIQUE INDEX profiles_user_id_idx ON profiles(user_id);
			`;
			const { res } = mockRes();
			await controller.analyzeDatabase(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: 'uq-idx-single',
						sqlContent: ddl,
					},
				}),
				res,
			);

			const tables = databaseMetadata.get(generatePGliteKey('uq-idx-single'))!;
			const profiles = tables.find((t) => t.name === 'profiles')!;
			const rel = profiles.relationships.find(
				(r) => r.referencedTable === 'users',
			)!;

			expect(rel.cardinality).toBe(RelationshipType.OneToOne);
		});

		/**
		 * A composite CREATE UNIQUE INDEX must NOT make either FK column
		 * individually unique.  Both FK relationships should remain 1:N.
		 */
		it('classifies FK as 1:N when it participates in a composite CREATE UNIQUE INDEX', async () => {
			const ddl = `
				CREATE TABLE products  (id SERIAL PRIMARY KEY, name TEXT NOT NULL);
				CREATE TABLE customers (id SERIAL PRIMARY KEY, name TEXT NOT NULL);
				CREATE TABLE orders (
					id          SERIAL  PRIMARY KEY,
					product_id  INTEGER NOT NULL REFERENCES products(id),
					customer_id INTEGER NOT NULL REFERENCES customers(id)
				);
				CREATE UNIQUE INDEX orders_composite_idx ON orders(product_id, customer_id);
			`;
			const { res } = mockRes();
			await controller.analyzeDatabase(
				mockReq({
					connectionInfo: {
						type: 'pglite',
						databaseId: 'uq-idx-composite',
						sqlContent: ddl,
					},
				}),
				res,
			);

			const tables = databaseMetadata.get(
				generatePGliteKey('uq-idx-composite'),
			)!;
			const orders = tables.find((t) => t.name === 'orders')!;

			for (const rel of orders.relationships) {
				expect(rel.cardinality).toBe(RelationshipType.OneToMany);
			}
		});
	});
});
