import { describe, it, expect, beforeEach } from 'vitest';
import { Parser } from 'node-sql-parser';
import { TemplateTaskDescriptionGenerationEngine } from '../../../src/generation/description/template-task-description-generation-engine';
import { EntityType, IAliasMap, IParsedTable } from '../../../src/shared/interfaces/domain';
import northwindDe from '../../_manual/annotated_schemas/northwind/northwind_schema_annotation_de.json';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const parser = new Parser();

/** Parse a SQL string and return a single AST node (never an array). */
function parse(sql: string) {
    const ast = parser.astify(sql, { database: 'PostgreSQL' });
    return Array.isArray(ast) ? ast[0] : ast;
}

/**
 * Minimal IParsedTable factory — fills in all required fields with safe
 * defaults so individual tests only need to specify what they care about.
 */
function makeTable(name: string, entityType: EntityType = EntityType.Strong): IParsedTable {
    return {
        name,
        entityType,
        columns: [],
        relationships: [],
        joinPaths: [],
    };
}

/**
 * The northwind_schema_annotation_de.json file is shaped as an IAliasMap
 * (tables + columns) and is used to provide German display names.
 */
const deAliasMap: IAliasMap = northwindDe as IAliasMap;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TemplateTaskDescriptionGenerationEngine — German (lang="de")', () => {
    let engine: TemplateTaskDescriptionGenerationEngine;

    beforeEach(() => {
        engine = new TemplateTaskDescriptionGenerationEngine();
    });

    // -----------------------------------------------------------------------
    // SELECT — simple queries
    // -----------------------------------------------------------------------

    describe('SELECT — simple queries', () => {

        it('translates SELECT * correctly', () => {
            const ast = parse('SELECT * FROM northwind.employees');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Table alias "Mitarbeiter" is preserved with original casing (German nouns capitalised).
            expect(result).toBe(
                'Rufe alle Informationen über Mitarbeiter aus der northwind-Datenbank ab.'
            );
        });

        it('translates SELECT with named columns correctly — no article prefix in German', () => {
            const ast = parse(
                'SELECT employees.first_name, employees.last_name FROM northwind.employees'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // German COLUMN_PREFIX is empty so no table prefix is prepended.
            // Column aliases "Vorname" / "Nachname" keep their original casing.
            // AND_JOINER is 'und' instead of 'and'.
            expect(result).toBe(
                'Rufe Vorname und Nachname aus der northwind-Datenbank ab.'
            );
        });

        it('translates SELECT DISTINCT correctly — no article prefix in German', () => {
            const ast = parse(
                'SELECT DISTINCT customers.country FROM northwind.customers'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Column alias "Land" keeps its casing; no table prefix (COLUMN_PREFIX="").
            expect(result).toBe(
                'Rufe eindeutige Land aus der northwind-Datenbank ab.'
            );
        });

    });

    // -----------------------------------------------------------------------
    // WHERE clause
    // -----------------------------------------------------------------------

    describe('WHERE clause', () => {

        it('translates a simple WHERE with equality correctly', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers WHERE customers.country = 'Germany'"
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Table alias "Kunden", column alias "Land" — both keep original casing.
            // German COLUMN_PREFIX is empty: no article before column name.
            expect(result).toBe(
                'Rufe alle Informationen über Kunden aus der northwind-Datenbank ab.' +
                ' Filtere die Ergebnisse, bei denen Land ist gleich Germany.'
            );
        });

        it('translates a WHERE with greater-than comparison correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.products WHERE products.unit_price > 20'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Table alias "Produkte", column alias "Stückpreis".
            expect(result).toBe(
                'Rufe alle Informationen über Produkte aus der northwind-Datenbank ab.' +
                ' Filtere die Ergebnisse, bei denen Stückpreis ist größer als 20.'
            );
        });

        it('translates BETWEEN correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.products WHERE products.unit_price BETWEEN 10 AND 50'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('liegt zwischen');
        });

        it('translates LIKE correctly', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers WHERE customers.company_name LIKE 'A%'"
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('entspricht dem Muster');
        });

        it('translates NOT LIKE correctly', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers WHERE customers.company_name NOT LIKE 'A%'"
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('entspricht nicht dem Muster');
        });

        it('translates IN correctly', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers WHERE customers.country IN ('Germany', 'France')"
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('ist eines von');
        });

        it('translates NOT IN correctly', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers WHERE customers.country NOT IN ('Germany', 'France')"
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('ist keines von');
        });

        it('translates IS NULL correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees WHERE employees.region IS NULL'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('ist nicht definiert');
        });

        it('translates IS NOT NULL correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees WHERE employees.region IS NOT NULL'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('ist definiert');
        });

        it('translates AND correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.products WHERE products.unit_price > 10 AND products.units_in_stock < 100'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('ist größer als 10');
            expect(result).toContain('und');
            expect(result).toContain('ist kleiner als 100');
        });

        it('translates OR correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.products WHERE products.unit_price > 10 OR products.units_in_stock < 100'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('ist größer als 10');
            expect(result).toContain('oder');
            expect(result).toContain('ist kleiner als 100');
        });

    });

    // -----------------------------------------------------------------------
    // GROUP BY, HAVING
    // -----------------------------------------------------------------------

    describe('GROUP BY and HAVING', () => {

        it('translates GROUP BY correctly', () => {
            const ast = parse(
                'SELECT employees.region, COUNT(employees.employee_id)' +
                ' FROM northwind.employees' +
                ' GROUP BY employees.region'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('Gruppiere die Ergebnisse nach');
            // Column alias "Bundesland / Region" keeps its original casing.
            expect(result).toContain('Bundesland / Region');
        });

        it('translates GROUP BY with HAVING correctly', () => {
            const ast = parse(
                'SELECT employees.region, COUNT(employees.employee_id)' +
                ' FROM northwind.employees' +
                ' GROUP BY employees.region' +
                ' HAVING COUNT(employees.employee_id) > 1'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('Gruppiere die Ergebnisse nach');
            expect(result).toContain('Filtere die gruppierten Ergebnisse, bei denen');
        });

    });

    // -----------------------------------------------------------------------
    // ORDER BY — German direction labels
    // -----------------------------------------------------------------------

    describe('ORDER BY', () => {

        it('translates ORDER BY ASC using German direction label', () => {
            const ast = parse(
                'SELECT * FROM northwind.products ORDER BY products.unit_price ASC'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('Sortiere die Ergebnisse nach');
            expect(result).toContain('in aufsteigender Reihenfolge');
        });

        it('translates ORDER BY DESC using German direction label', () => {
            const ast = parse(
                'SELECT * FROM northwind.products ORDER BY products.unit_price DESC'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('Sortiere die Ergebnisse nach');
            expect(result).toContain('in absteigender Reihenfolge');
        });

    });

    // -----------------------------------------------------------------------
    // LIMIT / OFFSET
    // -----------------------------------------------------------------------

    describe('LIMIT / OFFSET', () => {

        it('translates LIMIT correctly', () => {
            const ast = parse('SELECT * FROM northwind.products LIMIT 10');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Table alias "Produkte" keeps its casing.
            expect(result).toBe(
                'Rufe alle Informationen über Produkte aus der northwind-Datenbank ab.' +
                ' Begrenze die Ergebnisse auf 10 Datensatz/Datensätze.'
            );
        });

        it('translates LIMIT with OFFSET correctly', () => {
            const ast = parse('SELECT * FROM northwind.products LIMIT 10 OFFSET 5');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toBe(
                'Rufe alle Informationen über Produkte aus der northwind-Datenbank ab.' +
                ' Begrenze die Ergebnisse auf 10 Datensatz/Datensätze, beginnend ab Datensatz 5.'
            );
        });

    });

    // -----------------------------------------------------------------------
    // JOIN types
    // -----------------------------------------------------------------------

    describe('JOIN types', () => {

        it('translates INNER JOIN correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.orders' +
                ' INNER JOIN northwind.order_details ON orders.order_id = order_details.order_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Table aliases "Bestellungen" / "Auftragspositionen" keep their casing.
            expect(result).toBe(
                'Rufe alle Informationen über die folgende Datenkombination aus der northwind-Datenbank ab.' +
                ' Kombiniere die Daten aus der Bestellungen-Tabelle und der Auftragspositionen-Tabelle.'
            );
        });

        it('translates LEFT JOIN correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees' +
                ' LEFT JOIN northwind.orders ON employees.employee_id = orders.employee_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain(
                'Schließe alle Daten aus der Mitarbeiter-Tabelle sowie die übereinstimmenden Daten aus der Bestellungen-Tabelle ein.'
            );
        });

        it('translates RIGHT JOIN correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees' +
                ' RIGHT JOIN northwind.orders ON employees.employee_id = orders.employee_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain(
                'Schließe alle Daten aus der Bestellungen-Tabelle sowie die übereinstimmenden Daten aus der Mitarbeiter-Tabelle ein.'
            );
        });

        it('translates FULL JOIN correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees' +
                ' FULL JOIN northwind.orders ON employees.employee_id = orders.employee_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain(
                'Schließe alle Datensätze aus der Mitarbeiter-Tabelle und der Bestellungen-Tabelle ein.'
            );
        });

        it('translates SELF JOIN correctly', () => {
            const ast = parse(
                'SELECT e1.first_name, e2.first_name' +
                ' FROM northwind.employees e1' +
                ' INNER JOIN northwind.employees e2 ON e1.reports_to = e2.employee_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Table alias "Mitarbeiter" keeps its casing.
            expect(result).toContain(
                'Verknüpfe Datensätze innerhalb der Mitarbeiter-Tabelle'
            );
        });

        it('translates SELECT DISTINCT with JOIN correctly', () => {
            const ast = parse(
                'SELECT DISTINCT orders.customer_id' +
                ' FROM northwind.orders' +
                ' INNER JOIN northwind.order_details ON orders.order_id = order_details.order_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('Rufe eindeutige');
            // The German template uses "folgenden Datenkombination" (with 'n')
            expect(result).toContain('folgenden Datenkombination');
        });

    });

    // -----------------------------------------------------------------------
    // Aggregate functions
    // -----------------------------------------------------------------------

    describe('Aggregate functions', () => {

        it('translates AVG correctly', () => {
            const ast = parse('SELECT AVG(products.unit_price) FROM northwind.products');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('der Durchschnitt von');
        });

        it('translates SUM correctly', () => {
            const ast = parse('SELECT SUM(order_details.quantity) FROM northwind.order_details');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('die Summe von');
        });

        it('translates COUNT correctly', () => {
            const ast = parse('SELECT COUNT(employees.employee_id) FROM northwind.employees');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('die Anzahl von');
        });

        it('translates MAX correctly', () => {
            const ast = parse('SELECT MAX(products.unit_price) FROM northwind.products');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('das Maximum von');
        });

        it('translates MIN correctly', () => {
            const ast = parse('SELECT MIN(products.unit_price) FROM northwind.products');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('das Minimum von');
        });

    });

    // -----------------------------------------------------------------------
    // Set operations
    // -----------------------------------------------------------------------

    describe('Set operations', () => {

        it('translates UNION correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees UNION SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Table alias "Mitarbeiter" keeps its casing.
            expect(result).toContain('Rufe alle Informationen über Mitarbeiter');
            expect(result).toContain('Rufe zusätzlich ab:');
        });

        it('translates UNION ALL correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees UNION ALL SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('Rufe zusätzlich ab (einschließlich Duplikaten):');
        });

        it('translates EXCEPT correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees EXCEPT SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('Ausgenommen Ergebnisse, die vorkommen in:');
        });

        it('translates INTERSECT correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees INTERSECT SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('Schließe nur Ergebnisse ein, die auch vorkommen in:');
        });

    });

    // -----------------------------------------------------------------------
    // EXISTS
    // -----------------------------------------------------------------------

    describe('EXISTS', () => {

        it('translates EXISTS correctly', () => {
            const ast = parse(
                'SELECT orders.order_id FROM northwind.orders' +
                ' WHERE EXISTS (' +
                '   SELECT 1 FROM northwind.order_details' +
                '   WHERE order_details.order_id = orders.order_id' +
                ' )'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('es gibt einen zugehörigen Datensatz, bei dem');
        });

    });

    // -----------------------------------------------------------------------
    // CASE expressions
    // -----------------------------------------------------------------------

    describe('CASE expressions', () => {

        it('translates CASE WHEN/THEN/ELSE structural words correctly', () => {
            const ast = parse(
                'SELECT CASE' +
                '  WHEN products.unit_price > 50 THEN products.product_name' +
                '  ELSE products.product_name' +
                ' END' +
                ' FROM northwind.products'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('ein bedingter Wert basierend auf');
            expect(result).toContain('wenn');
            expect(result).toContain('dann');
            expect(result).toContain('sonst');
        });

    });

    // -----------------------------------------------------------------------
    // Weak / associative entity JOIN skipping — German WEAK_BRIDGE template
    // -----------------------------------------------------------------------

    describe('Weak entity JOIN simplification (German)', () => {

        it('emits the German WEAK_BRIDGE sentence for a bridge entity', () => {
            const tables: IParsedTable[] = [
                makeTable('orders',        EntityType.Strong),
                makeTable('order_details', EntityType.Weak),
                makeTable('products',      EntityType.Strong),
            ];

            const ast = parse(
                'SELECT * FROM northwind.orders' +
                ' INNER JOIN northwind.order_details ON orders.order_id = order_details.order_id' +
                ' INNER JOIN northwind.products ON order_details.product_id = products.product_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, tables, lang: 'de' });

            // The bridge table (order_details / Auftragspositionen) should not appear separately.
            expect(result).not.toContain('Auftragspositionen-Tabelle');
            // German WEAK_BRIDGE with capitalised aliases.
            expect(result).toContain('Rufe Produkte-Daten ab, die zu jedem Bestellungen gehören.');
        });

        it('preserves SELF JOIN with German template even when table metadata is present', () => {
            const tables: IParsedTable[] = [
                makeTable('employees', EntityType.Strong),
            ];

            const ast = parse(
                'SELECT e1.first_name, e2.first_name' +
                ' FROM northwind.employees e1' +
                ' INNER JOIN northwind.employees e2 ON e1.reports_to = e2.employee_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, tables, lang: 'de' });
            // Table alias "Mitarbeiter" keeps its casing.
            expect(result).toContain('Verknüpfe Datensätze innerhalb der Mitarbeiter-Tabelle');
        });

    });

    // -----------------------------------------------------------------------
    // Schema alias map — German column names appear in output
    // -----------------------------------------------------------------------

    describe('German schema alias map — column display names', () => {

        it('uses the German column display name for employees.hire_date', () => {
            const ast = parse('SELECT employees.hire_date FROM northwind.employees');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Column alias "Einstellungsdatum" — casing preserved.
            expect(result).toContain('Einstellungsdatum');
        });

        it('uses the German column display name for orders.order_date', () => {
            const ast = parse('SELECT orders.order_date FROM northwind.orders');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // orders.order_date alias from the JSON — verify it resolves.
            expect(result).toContain('Bestelldatum');
        });

        it('uses the German column display name for products.unit_price in WHERE', () => {
            const ast = parse('SELECT * FROM northwind.products WHERE products.unit_price > 30');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Column alias "Stückpreis" — casing preserved.
            expect(result).toContain('Stückpreis');
        });

        it('uses German table display names in a JOIN description', () => {
            const ast = parse(
                'SELECT * FROM northwind.orders' +
                ' INNER JOIN northwind.order_details ON orders.order_id = order_details.order_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            expect(result).toContain('Bestellungen');
            expect(result).toContain('Auftragspositionen');
        });

    });

    // -----------------------------------------------------------------------
    // Language fallback: no lang argument defaults to English
    // -----------------------------------------------------------------------

    describe('Language fallback', () => {

        it('falls back to English when no lang is provided', () => {
            const ast = parse('SELECT * FROM northwind.employees');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('Retrieve all information about the employees');
        });

        it('uses English article prefix when lang="en" is explicitly passed', () => {
            const ast = parse(
                'SELECT employees.first_name FROM northwind.employees'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', lang: 'en' });
            // English COLUMN_PREFIX is "the " so the output uses "the employees first name"
            expect(result).toContain('the employees first name');
        });

        it('falls back to English LIMIT template when lang="en" is explicitly passed', () => {
            const ast = parse('SELECT * FROM northwind.products LIMIT 5');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', lang: 'en' });
            expect(result).toContain('Limit the results to 5 record(s).');
        });

    });

    // -----------------------------------------------------------------------
    // End-to-end German sentences
    // -----------------------------------------------------------------------

    describe('End-to-end German sentences', () => {

        it('produces the correct full description for a JOIN with WHERE and GROUP BY', () => {
            const ast = parse(
                "SELECT employees.region, COUNT(employees.employee_id)" +
                ' FROM northwind.employees' +
                ' INNER JOIN northwind.orders ON employees.employee_id = orders.employee_id' +
                " WHERE employees.country = 'Germany'" +
                ' GROUP BY employees.region'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });

            // SELECT part: starts with German SELECT_COLUMNS_JOIN
            expect(result).toContain('Rufe');
            expect(result).toContain('northwind-Datenbank ab.');
            // JOIN part uses German INNER_JOIN template with capitalised aliases.
            expect(result).toContain('Kombiniere die Daten aus der Mitarbeiter-Tabelle und der Bestellungen-Tabelle.');
            // WHERE part uses German WHERE template and operator.
            expect(result).toContain('Filtere die Ergebnisse, bei denen');
            expect(result).toContain('ist gleich Germany');
            // GROUP BY part uses German GROUP_BY template.
            expect(result).toContain('Gruppiere die Ergebnisse nach');
        });

        it('produces the correct full description for ORDER BY DESC with LIMIT', () => {
            const ast = parse(
                'SELECT products.product_name, products.unit_price' +
                ' FROM northwind.products' +
                ' ORDER BY products.unit_price DESC' +
                ' LIMIT 5'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Column aliases "Produktname" / "Stückpreis" — casing preserved.
            // COLUMN_PREFIX="" so no table prefix; AND_JOINER is "und".
            // ORDER_DESC is "absteigend" → ORDER_BY_COLUMN yields "in absteigender Reihenfolge".
            expect(result).toBe(
                'Rufe Produktname und Stückpreis aus der northwind-Datenbank ab.' +
                ' Sortiere die Ergebnisse nach Stückpreis in absteigender Reihenfolge.' +
                ' Begrenze die Ergebnisse auf 5 Datensatz/Datensätze.'
            );
        });

        it('produces the correct full description for SELECT * with WHERE and LIMIT', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers" +
                " WHERE customers.country = 'Germany'" +
                ' LIMIT 3'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: deAliasMap, lang: 'de' });
            // Table alias "Kunden", column alias "Land" — casing preserved.
            expect(result).toBe(
                'Rufe alle Informationen über Kunden aus der northwind-Datenbank ab.' +
                ' Filtere die Ergebnisse, bei denen Land ist gleich Germany.' +
                ' Begrenze die Ergebnisse auf 3 Datensatz/Datensätze.'
            );
        });

    });

});
