/**
 * Generation against a fixture database with case-sensitive (quoted
 * uppercase) identifiers, e.g. the KE2 teaching database shape
 * (`"ANGNR"`, `"GEHALT"`, …).
 *
 * Regression coverage for the identifier-quoting change: internally
 * constructed probe statements and the final generated query must quote
 * identifiers so predicate-bearing configurations generate successfully and
 * the generated query executes with non-empty results. Lowercase schemas must
 * keep working unchanged.
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { PGlite } from '@electric-sql/pglite';
import { SQLQueryGenerationService } from '../../../src/generation/query/sql-query-generation-service';
import { SelectQueryGenerationDirector } from '../../../src/generation/query/select-query-generation-director';
import { DatabaseAnalyzer } from '../../../src/database/database-analyzer';
import {
	databaseMetadata,
	pgliteInstances,
} from '../../../src/database/internal-memory';
import { makePGliteRowQueryFn } from '../../../src/shared/utils/database-utils';
import type { ITaskConfiguration } from '../../../src/shared/interfaces/domain';

const UPPERCASE_DDL = /* sql */ `
CREATE TABLE "Mitarbeiter" (
	"ANGNR" INTEGER PRIMARY KEY,
	"NAME" VARCHAR(40),
	"GEHALT" NUMERIC(10,2),
	"CHEFNR" INTEGER REFERENCES "Mitarbeiter"("ANGNR"),
	"ABTNR" INTEGER
);
CREATE TABLE "Abteilung" (
	"ABTNR" INTEGER PRIMARY KEY,
	"BEZEICHNUNG" VARCHAR(40),
	"LEITERNR" INTEGER REFERENCES "Mitarbeiter"("ANGNR")
);
ALTER TABLE "Mitarbeiter" ADD CONSTRAINT "mit_abt_fk" FOREIGN KEY ("ABTNR") REFERENCES "Abteilung"("ABTNR");
INSERT INTO "Mitarbeiter" ("ANGNR", "NAME", "GEHALT", "CHEFNR") VALUES
	(1, 'Ada',  5000.00, 1),
	(2, 'Bob',  6000.00, 1),
	(3, 'Cyd',  7000.00, 2),
	(4, 'Dana', 8000.00, 2),
	(5, 'Emil', 9000.00, 3);
INSERT INTO "Abteilung" VALUES
	(1, 'IT', 1),
	(2, 'HR', 2);
UPDATE "Mitarbeiter" SET "ABTNR" = 1 WHERE "ANGNR" IN (1, 2, 5);
UPDATE "Mitarbeiter" SET "ABTNR" = 2 WHERE "ANGNR" IN (3, 4);
`;

const LOWERCASE_DDL = /* sql */ `
CREATE TABLE products (
	id SERIAL PRIMARY KEY,
	name TEXT NOT NULL,
	price NUMERIC(10,2)
);
INSERT INTO products (name, price) VALUES ('Widget', 9.99), ('Gadget', 19.99), ('Gizmo', 29.99);
`;

const UPPER_KEY = 'pglite:uppercase-ke2';
const LOWER_KEY = 'pglite:lowercase';

function predicateConfig(operationTypes: string[]): ITaskConfiguration {
	return {
		aggregation: false,
		orderby: true,
		joinDepth: 1,
		joinTypes: ['INNER JOIN'],
		predicateCount: operationTypes.length,
		groupby: false,
		having: false,
		columnCount: 1,
		operationTypes: operationTypes as ITaskConfiguration['operationTypes'],
	};
}

describe('SQL query generation with case-sensitive identifiers', () => {
	let upperDb: PGlite;
	let lowerDb: PGlite;
	let service: SQLQueryGenerationService;

	beforeAll(async () => {
		upperDb = new PGlite();
		await upperDb.exec(UPPERCASE_DDL);
		pgliteInstances.set('uppercase-ke2', upperDb);
		const analyzer = new DatabaseAnalyzer();
		const analyzed = await analyzer.extractSchemaFromPGlite(
			upperDb,
			UPPER_KEY,
		);
		expect(analyzed).toBe(true);

		lowerDb = new PGlite();
		await lowerDb.exec(LOWERCASE_DDL);
		pgliteInstances.set('lowercase', lowerDb);
		const analyzedLower = await analyzer.extractSchemaFromPGlite(
			lowerDb,
			LOWER_KEY,
		);
		expect(analyzedLower).toBe(true);

		service = new SQLQueryGenerationService(
			new SelectQueryGenerationDirector(),
		);
	});

	afterAll(async () => {
		await upperDb.close();
		await lowerDb.close();
		pgliteInstances.clear();
		databaseMetadata.clear();
	});

	it('generates a predicate-bearing task against quoted uppercase identifiers', async () => {
		const [query] = await service.generateContextBasedQuery(
			predicateConfig(['EQUAL', 'IN']),
			UPPER_KEY,
			makePGliteRowQueryFn(upperDb),
			'public',
		);

		expect(query).toMatch(/SELECT/i);
		// generated query quotes the case-sensitive identifiers
		expect(query).toMatch(/"ANGNR"|"NAME"|"GEHALT"|"BEZEICHNUNG"/);
		expect(query).toMatch(/"Mitarbeiter"/);
	});

	it('generated queries execute with non-empty results', async () => {
		const [query] = await service.generateContextBasedQuery(
			predicateConfig(['BETWEEN']),
			UPPER_KEY,
			makePGliteRowQueryFn(upperDb),
			'public',
		);
		const rows = await upperDb.query(query);
		expect(rows.rows.length).toBeGreaterThan(0);
	});

	it('aggregation/HAVING generation works against quoted uppercase identifiers', async () => {
		const config: ITaskConfiguration = {
			aggregation: true,
			orderby: true,
			joinDepth: 1,
			joinTypes: ['INNER JOIN'],
			predicateCount: 1,
			groupby: true,
			having: true,
			columnCount: 1,
			operationTypes: ['EQUAL'],
		};
		const [query] = await service.generateContextBasedQuery(
			config,
			UPPER_KEY,
			makePGliteRowQueryFn(upperDb),
			'public',
		);
		expect(query).toMatch(/HAVING/i);
		const rows = await upperDb.query(query);
		expect(rows.rows.length).toBeGreaterThan(0);
	});

	it('lowercase fixtures behave as before', async () => {
		const config: ITaskConfiguration = {
			aggregation: false,
			orderby: false,
			joinDepth: 0,
			joinTypes: [],
			predicateCount: 1,
			groupby: false,
			having: false,
			columnCount: 1,
			operationTypes: ['EQUAL'],
		};
		const [query] = await service.generateContextBasedQuery(
			config,
			LOWER_KEY,
			makePGliteRowQueryFn(lowerDb),
			'public',
		);
		expect(query).toMatch(/SELECT/i);
		const rows = await lowerDb.query(query);
		expect(rows.rows.length).toBeGreaterThan(0);
	});
});
