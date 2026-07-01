/**
 * Unit tests for the PGlite-backed {@link RowQueryFn} and the grading
 * comparators when driven by it.
 *
 * These verify the two shape-alignment invariants that make the grading
 * pipeline backend-agnostic:
 *
 *   1. `makePGliteRowQueryFn` unwraps PGlite's `{ rows }` envelope so callers
 *      receive a plain row array — identical to the TypeORM `makeRowQueryFn`.
 *   2. PGlite's `EXPLAIN (FORMAT JSON)` rows are shaped so `rawPlan[0]` equals
 *      `{ 'QUERY PLAN': [...] }`, exactly what ExecutionPlanParser expects.
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { PGlite } from '@electric-sql/pglite';
import { makePGliteRowQueryFn } from '../../src/shared/utils/database-utils';
import { ResultSetComparator } from '../../src/grading/result-set-comparator';
import { ExecutionPlanComparator } from '../../src/grading/comparators/execution-plan-comparator';
import { ExecutionPlanParser } from '../../src/grading/execution-plan-parser';
import { JoinComparator } from '../../src/grading/join-comparator';
import { Parser, AST } from 'node-sql-parser';

const DDL = `
CREATE TABLE products (
  id    SERIAL PRIMARY KEY,
  name  TEXT NOT NULL,
  price NUMERIC(10,2)
);
INSERT INTO products (name, price) VALUES ('Widget', 9.99), ('Gadget', 19.99);
`;

let db: PGlite;

beforeAll(async () => {
	db = new PGlite();
	await db.exec(DDL);
});

afterAll(async () => {
	await db.close();
});

describe('makePGliteRowQueryFn', () => {
	it('returns a plain array of rows (unwrapping the { rows } envelope)', async () => {
		const runQuery = makePGliteRowQueryFn(db);
		const rows = await runQuery('SELECT name FROM products ORDER BY name');
		expect(Array.isArray(rows)).toBe(true);
		expect(rows).toEqual([{ name: 'Gadget' }, { name: 'Widget' }]);
	});

	it('produces EXPLAIN rows whose [0] entry has a "QUERY PLAN" key', async () => {
		const runQuery = makePGliteRowQueryFn(db);
		const rawPlan = await runQuery(
			'EXPLAIN (FORMAT JSON) SELECT name FROM products',
		);
		expect(Array.isArray(rawPlan)).toBe(true);
		expect(rawPlan[0]).toHaveProperty('QUERY PLAN');
		expect(Array.isArray(rawPlan[0]['QUERY PLAN'])).toBe(true);
	});

	it('propagates database errors as thrown Errors', async () => {
		const runQuery = makePGliteRowQueryFn(db);
		await expect(runQuery('SELECT * FROM missing_table')).rejects.toThrow();
	});

	it('does not close the shared instance', async () => {
		const runQuery = makePGliteRowQueryFn(db);
		await runQuery('SELECT 1');
		// Still usable afterwards.
		const rows = await runQuery('SELECT 2 AS v');
		expect((rows[0] as any).v).toBe(2);
	});
});

describe('ResultSetComparator driven by PGlite RowQueryFn', () => {
	const comparator = new ResultSetComparator();
	const runQuery = () => makePGliteRowQueryFn(db);

	it('reports equal result sets', async () => {
		const [match, feedback] = await comparator.compare(
			'SELECT name FROM products ORDER BY name',
			'SELECT name FROM products ORDER BY name',
			runQuery(),
		);
		expect(match).toBe(true);
		expect(feedback).toEqual([]);
	});

	it('reports unequal result sets', async () => {
		const [match] = await comparator.compare(
			'SELECT name FROM products WHERE price > 15',
			'SELECT name FROM products',
			runQuery(),
		);
		expect(match).toBe(false);
	});

	it('isExecutable populates feedback from a plain Error message', async () => {
		const [ok, feedback] = await comparator.isExecutable(
			'SELECT * FROM missing_table',
			runQuery(),
		);
		expect(ok).toBe(false);
		// Second feedback entry is the extracted DB error message — must not be
		// undefined (regression guard for PGlite plain Error objects).
		expect(feedback[1]).toBeTruthy();
		expect(typeof feedback[1]).toBe('string');
	});
});

describe('ExecutionPlanComparator driven by PGlite RowQueryFn', () => {
	const comparator = new ExecutionPlanComparator(
		new ExecutionPlanParser(),
		new JoinComparator(),
	);
	const parser = new Parser();

	function astOf(sql: string): AST {
		return parser.astify(sql, { database: 'postgresql' }) as AST;
	}

	it('returns plansMatch=true for identical queries', async () => {
		const q = 'SELECT name FROM products WHERE price > 15 ORDER BY name';
		const result = await comparator.compare(
			astOf(q),
			astOf(q),
			{},
			{},
			makePGliteRowQueryFn(db),
			q,
			q,
		);
		expect(result.plansMatch).toBe(true);
		expect(result.penaltyPoints).toBe(0);
	});

	it('detects a missing WHERE clause and adds penalty points', async () => {
		const ref = 'SELECT name FROM products WHERE price > 15 ORDER BY name';
		const student = 'SELECT name FROM products ORDER BY name';
		const result = await comparator.compare(
			astOf(student),
			astOf(ref),
			{},
			{},
			makePGliteRowQueryFn(db),
			student,
			ref,
		);
		expect(result.plansMatch).toBe(false);
		expect(result.penaltyPoints).toBeGreaterThan(0);
	});
});
