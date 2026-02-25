import { describe, it, expect, beforeEach } from 'vitest';
import { Parser } from 'node-sql-parser';
import { TemplateTaskDescriptionGenerationEngine } from '../../../src/generation/description/template-task-description-generation-engine';
import { EntityType, IAliasMap, IParsedTable } from '../../../src/shared/interfaces/domain';
import northwindDe from '../../_manual/northwind_schema_annotation_de.json';

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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toBe(
                'Rufe alle Informationen über mitarbeiter aus der northwind-Datenbank ab.'
            );
        });

        it('translates SELECT with named columns correctly — no article prefix in German', () => {
            const ast = parse(
                'SELECT employees.first_name, employees.last_name FROM northwind.employees'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            // German COLUMN_PREFIX is empty, so no article before table name.
            // AND_JOINER is 'und' instead of 'and'.
            expect(result).toBe(
                'Rufe mitarbeiter vorname und mitarbeiter nachname aus der northwind-Datenbank ab.'
            );
        });

        it('translates SELECT DISTINCT correctly — no article prefix in German', () => {
            const ast = parse(
                'SELECT DISTINCT customers.country FROM northwind.customers'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toBe(
                'Rufe eindeutige kunden land aus der northwind-Datenbank ab.'
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            // German COLUMN_PREFIX is empty: "kunden land" not "die kunden land"
            expect(result).toBe(
                'Rufe alle Informationen über kunden aus der northwind-Datenbank ab.' +
                ' Filtere die Ergebnisse, bei denen kunden land ist gleich Germany.'
            );
        });

        it('translates a WHERE with greater-than comparison correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.products WHERE products.unit_price > 20'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toBe(
                'Rufe alle Informationen über produkte aus der northwind-Datenbank ab.' +
                ' Filtere die Ergebnisse, bei denen produkte stückpreis ist größer als 20.'
            );
        });

        it('translates BETWEEN correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.products WHERE products.unit_price BETWEEN 10 AND 50'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('liegt zwischen');
        });

        it('translates LIKE correctly', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers WHERE customers.company_name LIKE 'A%'"
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('entspricht dem Muster');
        });

        it('translates NOT LIKE correctly', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers WHERE customers.company_name NOT LIKE 'A%'"
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('entspricht nicht dem Muster');
        });

        it('translates IN correctly', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers WHERE customers.country IN ('Germany', 'France')"
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('ist eines von');
        });

        it('translates NOT IN correctly', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers WHERE customers.country NOT IN ('Germany', 'France')"
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('ist keines von');
        });

        it('translates IS NULL correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees WHERE employees.region IS NULL'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('ist nicht definiert');
        });

        it('translates IS NOT NULL correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees WHERE employees.region IS NOT NULL'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('ist definiert');
        });

        it('translates AND correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.products WHERE products.unit_price > 10 AND products.units_in_stock < 100'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('ist größer als 10');
            expect(result).toContain('und');
            expect(result).toContain('ist kleiner als 100');
        });

        it('translates OR correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.products WHERE products.unit_price > 10 OR products.units_in_stock < 100'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('Gruppiere die Ergebnisse nach');
            expect(result).toContain('bundesland / region');
        });

        it('translates GROUP BY with HAVING correctly', () => {
            const ast = parse(
                'SELECT employees.region, COUNT(employees.employee_id)' +
                ' FROM northwind.employees' +
                ' GROUP BY employees.region' +
                ' HAVING COUNT(employees.employee_id) > 1'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('Sortiere die Ergebnisse nach');
            expect(result).toContain('in aufsteigend order');
        });

        it('translates ORDER BY DESC using German direction label', () => {
            const ast = parse(
                'SELECT * FROM northwind.products ORDER BY products.unit_price DESC'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('Sortiere die Ergebnisse nach');
            expect(result).toContain('in absteigend order');
        });

    });

    // -----------------------------------------------------------------------
    // LIMIT / OFFSET
    // -----------------------------------------------------------------------

    describe('LIMIT / OFFSET', () => {

        it('translates LIMIT correctly', () => {
            const ast = parse('SELECT * FROM northwind.products LIMIT 10');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toBe(
                'Rufe alle Informationen über produkte aus der northwind-Datenbank ab.' +
                ' Begrenze die Ergebnisse auf 10 Datensatz/Datensätze.'
            );
        });

        it('translates LIMIT with OFFSET correctly', () => {
            const ast = parse('SELECT * FROM northwind.products LIMIT 10 OFFSET 5');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toBe(
                'Rufe alle Informationen über produkte aus der northwind-Datenbank ab.' +
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toBe(
                'Rufe alle Informationen über die folgende Datenkombination aus der northwind-Datenbank ab.' +
                ' Kombiniere die Daten aus der bestellungen-Tabelle und der auftragspositionen-Tabelle.'
            );
        });

        it('translates LEFT JOIN correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees' +
                ' LEFT JOIN northwind.orders ON employees.employee_id = orders.employee_id'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain(
                'Schließe alle Daten aus der mitarbeiter-Tabelle sowie die übereinstimmenden Daten aus der bestellungen-Tabelle ein.'
            );
        });

        it('translates RIGHT JOIN correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees' +
                ' RIGHT JOIN northwind.orders ON employees.employee_id = orders.employee_id'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain(
                'Schließe alle Daten aus der bestellungen-Tabelle sowie die übereinstimmenden Daten aus der mitarbeiter-Tabelle ein.'
            );
        });

        it('translates FULL JOIN correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees' +
                ' FULL JOIN northwind.orders ON employees.employee_id = orders.employee_id'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain(
                'Schließe alle Datensätze aus der mitarbeiter-Tabelle und der bestellungen-Tabelle ein.'
            );
        });

        it('translates SELF JOIN correctly', () => {
            const ast = parse(
                'SELECT e1.first_name, e2.first_name' +
                ' FROM northwind.employees e1' +
                ' INNER JOIN northwind.employees e2 ON e1.reports_to = e2.employee_id'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain(
                'Verknüpfe Datensätze innerhalb der mitarbeiter-Tabelle'
            );
        });

        it('translates SELECT DISTINCT with JOIN correctly', () => {
            const ast = parse(
                'SELECT DISTINCT orders.customer_id' +
                ' FROM northwind.orders' +
                ' INNER JOIN northwind.order_details ON orders.order_id = order_details.order_id'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('der Durchschnitt von');
        });

        it('translates SUM correctly', () => {
            const ast = parse('SELECT SUM(order_details.quantity) FROM northwind.order_details');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('die Summe von');
        });

        it('translates COUNT correctly', () => {
            const ast = parse('SELECT COUNT(employees.employee_id) FROM northwind.employees');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('die Anzahl von');
        });

        it('translates MAX correctly', () => {
            const ast = parse('SELECT MAX(products.unit_price) FROM northwind.products');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('das Maximum von');
        });

        it('translates MIN correctly', () => {
            const ast = parse('SELECT MIN(products.unit_price) FROM northwind.products');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('Rufe alle Informationen über mitarbeiter');
            expect(result).toContain('Rufe zusätzlich ab:');
        });

        it('translates UNION ALL correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees UNION ALL SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('Rufe zusätzlich ab (einschließlich Duplikaten):');
        });

        it('translates EXCEPT correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees EXCEPT SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('Ausgenommen Ergebnisse, die vorkommen in:');
        });

        it('translates INTERSECT correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees INTERSECT SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, tables, 'de');

            // The bridge table (order_details / auftragspositionen) should not appear separately
            expect(result).not.toContain('auftragspositionen-Tabelle');
            // German WEAK_BRIDGE: "Rufe {table2} data related to each {table1}."
            expect(result).toContain('Rufe produkte-Daten ab, die zu jedem bestellungen gehören.');
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, tables, 'de');
            expect(result).toContain('Verknüpfe Datensätze innerhalb der mitarbeiter-Tabelle');
        });

    });

    // -----------------------------------------------------------------------
    // Schema alias map — German column names appear in output
    // -----------------------------------------------------------------------

    describe('German schema alias map — column display names', () => {

        it('uses the German column display name for employees.hire_date', () => {
            const ast = parse('SELECT employees.hire_date FROM northwind.employees');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('einstellungsdatum');
        });

        it('uses the German column display name for orders.order_date', () => {
            const ast = parse('SELECT orders.order_date FROM northwind.orders');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('bestelldatum');
        });

        it('uses the German column display name for products.unit_price in WHERE', () => {
            const ast = parse('SELECT * FROM northwind.products WHERE products.unit_price > 30');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('stückpreis');
        });

        it('uses German table display names in a JOIN description', () => {
            const ast = parse(
                'SELECT * FROM northwind.orders' +
                ' INNER JOIN northwind.order_details ON orders.order_id = order_details.order_id'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toContain('bestellungen');
            expect(result).toContain('auftragspositionen');
        });

    });

    // -----------------------------------------------------------------------
    // Language fallback: no lang argument defaults to English
    // -----------------------------------------------------------------------

    describe('Language fallback', () => {

        it('falls back to English when no lang is provided', () => {
            const ast = parse('SELECT * FROM northwind.employees');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind');
            expect(result).toContain('Retrieve all information about the employees');
        });

        it('uses English article prefix when lang="en" is explicitly passed', () => {
            const ast = parse(
                'SELECT employees.first_name FROM northwind.employees'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', undefined, undefined, 'en');
            // English COLUMN_PREFIX is "the " so the output uses "the employees first name"
            expect(result).toContain('the employees first name');
        });

        it('falls back to English LIMIT template when lang="en" is explicitly passed', () => {
            const ast = parse('SELECT * FROM northwind.products LIMIT 5');
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', undefined, undefined, 'en');
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
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');

            // SELECT part: starts with German SELECT_COLUMNS_JOIN
            expect(result).toContain('Rufe');
            expect(result).toContain('northwind-Datenbank ab.');
            // JOIN part uses German INNER_JOIN template
            expect(result).toContain('Kombiniere die Daten aus der mitarbeiter-Tabelle und der bestellungen-Tabelle.');
            // WHERE part uses German WHERE template and operator
            expect(result).toContain('Filtere die Ergebnisse, bei denen');
            expect(result).toContain('ist gleich Germany');
            // GROUP BY part uses German GROUP_BY template
            expect(result).toContain('Gruppiere die Ergebnisse nach');
        });

        it('produces the correct full description for ORDER BY DESC with LIMIT', () => {
            const ast = parse(
                'SELECT products.product_name, products.unit_price' +
                ' FROM northwind.products' +
                ' ORDER BY products.unit_price DESC' +
                ' LIMIT 5'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            // German COLUMN_PREFIX is empty: no article before table name
            // AND_JOINER is 'und'
            // ORDER_DESC is 'absteigend'
            expect(result).toBe(
                'Rufe produkte produktname und produkte stückpreis aus der northwind-Datenbank ab.' +
                ' Sortiere die Ergebnisse nach produkte stückpreis in absteigend order.' +
                ' Begrenze die Ergebnisse auf 5 Datensatz/Datensätze.'
            );
        });

        it('produces the correct full description for SELECT * with WHERE and LIMIT', () => {
            const ast = parse(
                "SELECT * FROM northwind.customers" +
                " WHERE customers.country = 'Germany'" +
                ' LIMIT 3'
            );
            const result = engine.generateTaskFromQuery(ast as any, 'northwind', deAliasMap, undefined, 'de');
            expect(result).toBe(
                'Rufe alle Informationen über kunden aus der northwind-Datenbank ab.' +
                ' Filtere die Ergebnisse, bei denen kunden land ist gleich Germany.' +
                ' Begrenze die Ergebnisse auf 3 Datensatz/Datensätze.'
            );
        });

    });

});
