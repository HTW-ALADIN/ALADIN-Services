import { describe, it, expect, beforeEach } from 'vitest';
import { Parser } from 'node-sql-parser';
import { TemplateTaskDescriptionGenerationEngine } from '../../../src/generation/description/template-task-description-generation-engine';
import { EntityType, IParsedTable, Participation, RelationshipType } from '../../../src/shared/interfaces/domain';

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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TemplateTaskDescriptionGenerationEngine', () => {
    let engine: TemplateTaskDescriptionGenerationEngine;

    beforeEach(() => {
        engine = new TemplateTaskDescriptionGenerationEngine();
    });

    // -----------------------------------------------------------------------
    // Original / regression tests
    // -----------------------------------------------------------------------

    describe('generateTaskFromQuery — existing behaviour', () => {

        it('returns a description for a simple SELECT * query', () => {
            const ast = parse('SELECT * FROM northwind.employees');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve all information about the employees in the northwind database.'
            );
        });

        it('returns a description for a SELECT with named columns', () => {
            const ast = parse(
                'SELECT employees.first_name, employees.last_name FROM northwind.employees'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve the employees first name and the employees last name in the northwind database.'
            );
        });

        it('returns a description for a query with a WHERE clause', () => {
            const ast = parse(
                'SELECT * FROM northwind.products WHERE products.unit_price > 20'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve all information about the products in the northwind database.' +
                ' Filter the results where the products unit price is greater than 20.'
            );
        });

        it('returns a description for a query with GROUP BY and HAVING', () => {
            const ast = parse(
                'SELECT employees.region, COUNT(employees.employee_id)' +
                ' FROM northwind.employees' +
                ' GROUP BY employees.region' +
                ' HAVING COUNT(employees.employee_id) > 1'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve the employees region and the number of employee ids in the northwind database.' +
                ' Group the results based on the employees region.' +
                ' Filter the grouped results where the number of employee ids is greater than 1.'
            );
        });

        it('returns a description for a query with an INNER JOIN', () => {
            const ast = parse(
                'SELECT * FROM northwind.orders' +
                ' INNER JOIN northwind.order_details ON orders.order_id = order_details.order_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve all information about the following data combination in the northwind database.' +
                ' Combine the data from the orders table and the order details table.'
            );
        });

        it('returns a description for a query with a SELF JOIN', () => {
            const ast = parse(
                'SELECT e1.first_name, e2.first_name' +
                ' FROM northwind.employees e1' +
                ' INNER JOIN northwind.employees e2 ON e1.reports_to = e2.employee_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve the employees first name and the employees first name from the following data combination in the northwind database.' +
                ' Match records within the employees table where the employees reports to equals the employees employee id.'
            );
        });

        it('returns a description for a query with aggregate functions', () => {
            const ast = parse(
                'SELECT AVG(products.unit_price), MAX(products.units_in_stock)' +
                ' FROM northwind.products'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve the average of unit prices and the maximum units in stock in the northwind database.'
            );
        });

        it('returns a description for a query with ORDER BY', () => {
            const ast = parse(
                'SELECT * FROM northwind.products ORDER BY products.unit_price ASC'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve all information about the products in the northwind database.' +
                ' Sort the results by the products unit price in ascending order.'
            );
        });

    });

    // -----------------------------------------------------------------------
    // DISTINCT
    // -----------------------------------------------------------------------

    describe('DISTINCT', () => {

        it('uses the DISTINCT template for SELECT DISTINCT with columns', () => {
            const ast = parse(
                'SELECT DISTINCT employees.department FROM northwind.employees'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve unique the employees department in the northwind database.'
            );
        });

        it('uses the DISTINCT JOIN template when a JOIN is present', () => {
            const ast = parse(
                'SELECT DISTINCT orders.customer_id' +
                ' FROM northwind.orders' +
                ' INNER JOIN northwind.order_details ON orders.order_id = order_details.order_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('Retrieve unique');
            expect(result).toContain('following data combination');
        });

    });

    // -----------------------------------------------------------------------
    // LIMIT / OFFSET
    // -----------------------------------------------------------------------

    describe('LIMIT / OFFSET', () => {

        it('appends a LIMIT sentence', () => {
            const ast = parse(
                'SELECT * FROM northwind.products LIMIT 10'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve all information about the products in the northwind database.' +
                ' Limit the results to 10 record(s).'
            );
        });

        it('appends a LIMIT + OFFSET sentence', () => {
            const ast = parse(
                'SELECT * FROM northwind.products LIMIT 10 OFFSET 5'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toBe(
                'Retrieve all information about the products in the northwind database.' +
                ' Limit the results to 10 record(s), starting from record 5.'
            );
        });

    });

    // -----------------------------------------------------------------------
    // NOT IN bug fix
    // -----------------------------------------------------------------------

    describe('NOT IN (bug fix)', () => {

        it('correctly lists values for NOT IN', () => {
            const ast = parse(
                'SELECT employees.name FROM northwind.employees' +
                ' WHERE employees.salary NOT IN (1000, 2000, 3000)'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('is not one of 1000, 2000, 3000');
        });

        it('correctly lists values for IN (regression)', () => {
            const ast = parse(
                'SELECT employees.name FROM northwind.employees' +
                ' WHERE employees.salary IN (1000, 2000)'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('is one of 1000, 2000');
        });

    });

    // -----------------------------------------------------------------------
    // Set operations: UNION / UNION ALL / INTERSECT / EXCEPT
    // -----------------------------------------------------------------------

    describe('Set operations', () => {

        it('produces a combined description for UNION', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees UNION SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('Retrieve all information about the employees');
            expect(result).toContain('Additionally retrieve');
            expect(result).toContain('Retrieve all information about the managers');
        });

        it('produces a combined description for UNION ALL', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees UNION ALL SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('Additionally retrieve (including duplicates)');
        });

        it('produces a combined description for EXCEPT', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees EXCEPT SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('Excluding results that appear in');
        });

        it('produces a combined description for INTERSECT', () => {
            const ast = parse(
                'SELECT * FROM northwind.employees INTERSECT SELECT * FROM northwind.managers'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('Only include results that also appear in');
        });

    });

    // -----------------------------------------------------------------------
    // EXISTS / NOT EXISTS
    // -----------------------------------------------------------------------

    describe('EXISTS / NOT EXISTS', () => {

        it('describes an EXISTS subquery in WHERE', () => {
            const ast = parse(
                'SELECT orders.order_id FROM northwind.orders' +
                ' WHERE EXISTS (' +
                '   SELECT 1 FROM northwind.order_items' +
                '   WHERE order_items.order_id = orders.order_id' +
                ' )'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('there exists a related record where');
        });

    });

    // -----------------------------------------------------------------------
    // CASE expressions
    // -----------------------------------------------------------------------

    describe('CASE expressions', () => {

        it('describes a CASE WHEN expression in the SELECT list', () => {
            const ast = parse(
                'SELECT CASE' +
                '  WHEN employees.salary > 50000 THEN employees.name' +
                '  ELSE employees.department' +
                ' END' +
                ' FROM northwind.employees'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('a conditional value based on');
            expect(result).toContain('when');
            expect(result).toContain('then');
        });

    });

    // -----------------------------------------------------------------------
    // Non-aggregate scalar functions
    // -----------------------------------------------------------------------

    describe('Scalar functions', () => {

        it('describes COALESCE', () => {
            const ast = parse(
                'SELECT COALESCE(employees.name, employees.department) FROM northwind.employees'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('the first available value of');
        });

        it('describes UPPER', () => {
            const ast = parse(
                'SELECT UPPER(employees.last_name) FROM northwind.employees'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('in upper case');
        });

        it('describes LENGTH', () => {
            const ast = parse(
                'SELECT LENGTH(employees.last_name) FROM northwind.employees'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('the length of');
        });

    });

    // -----------------------------------------------------------------------
    // Weak / associative entity JOIN skipping
    // -----------------------------------------------------------------------

    describe('Weak entity JOIN simplification', () => {

        it('skips a weak bridge entity and uses WEAK_BRIDGE template', () => {
            // Schema: orders (strong) → order_item (weak) → products (strong)
            const tables: IParsedTable[] = [
                makeTable('orders',     EntityType.Strong),
                makeTable('order_item', EntityType.Weak),
                makeTable('products',   EntityType.Strong),
            ];

            const ast = parse(
                'SELECT * FROM northwind.orders' +
                ' INNER JOIN northwind.order_item ON orders.order_id = order_item.order_id' +
                ' INNER JOIN northwind.products ON order_item.product_id = products.product_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', tables });

            // The weak bridge entity (order_item) should be skipped.
            expect(result).not.toContain('order item table');
            // A WEAK_BRIDGE sentence should connect the two flanking strong entities.
            expect(result).toContain('Retrieve products data related to each orders.');
        });

        it('does NOT skip a weak entity that is the final JOIN target', () => {
            // When the weak entity is the last (and only) hop it is explicitly
            // being queried — it must appear in the description.
            const tables: IParsedTable[] = [
                makeTable('orders',     EntityType.Strong),
                makeTable('order_item', EntityType.Weak),
            ];

            const ast = parse(
                'SELECT * FROM northwind.orders' +
                ' INNER JOIN northwind.order_item ON orders.order_id = order_item.order_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', tables });

            expect(result).toContain('order item');
        });

        it('skips an associative (junction) entity the same as a weak entity', () => {
            // Schema: students (strong) → enrollment (associative) → courses (strong)
            const tables: IParsedTable[] = [
                makeTable('students',   EntityType.Strong),
                makeTable('enrollment', EntityType.Associative),
                makeTable('courses',    EntityType.Strong),
            ];

            const ast = parse(
                'SELECT * FROM northwind.students' +
                ' INNER JOIN northwind.enrollment ON students.student_id = enrollment.student_id' +
                ' INNER JOIN northwind.courses ON enrollment.course_id = courses.course_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', tables });

            expect(result).not.toContain('enrollment table');
            expect(result).toContain('Retrieve courses data related to each students.');
        });

        it('falls back to normal JOIN rendering when no tables metadata is provided', () => {
            // Without schema metadata every JOIN is rendered verbosely as before.
            const ast = parse(
                'SELECT * FROM northwind.orders' +
                ' INNER JOIN northwind.order_item ON orders.order_id = order_item.order_id' +
                ' INNER JOIN northwind.products ON order_item.product_id = products.product_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });

            expect(result).toContain('order item');
            expect(result).toContain('products');
        });

        it('preserves SELF JOIN rendering even with table metadata present', () => {
            const tables: IParsedTable[] = [
                makeTable('employees', EntityType.Strong),
            ];

            const ast = parse(
                'SELECT e1.first_name, e2.first_name' +
                ' FROM northwind.employees e1' +
                ' INNER JOIN northwind.employees e2 ON e1.reports_to = e2.employee_id'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', tables });

            expect(result).toContain('Match records within the employees table');
        });

    });

    // -----------------------------------------------------------------------
    // Compound WHERE conditions (AND / OR)
    // -----------------------------------------------------------------------

    describe('Compound WHERE conditions', () => {

        it('combines two conditions with AND', () => {
            const ast = parse(
                'SELECT * FROM northwind.products' +
                ' WHERE products.unit_price > 10 AND products.units_in_stock < 100'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('is greater than 10');
            expect(result).toContain('and');
            expect(result).toContain('is less than 100');
        });

        it('combines two conditions with OR', () => {
            const ast = parse(
                'SELECT * FROM northwind.products' +
                ' WHERE products.unit_price > 10 OR products.units_in_stock < 100'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('is greater than 10');
            expect(result).toContain('or');
            expect(result).toContain('is less than 100');
        });

    });

    // -----------------------------------------------------------------------
    // ORDER BY descending
    // -----------------------------------------------------------------------

    describe('ORDER BY', () => {

        it('marks a DESC sort correctly', () => {
            const ast = parse(
                'SELECT * FROM northwind.products ORDER BY products.unit_price DESC'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind' });
            expect(result).toContain('in descending order');
        });

    });

    // -----------------------------------------------------------------------
    // schemaAliasMap
    // -----------------------------------------------------------------------

    describe('schemaAliasMap', () => {

        it('applies table alias from schemaAliasMap', () => {
            const ast = parse('SELECT * FROM northwind.emp');
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: {
                tables: { emp: 'Employees' },
            } });
            // formatName lower-cases the alias; the word "employees" should appear
            // instead of the raw table name "emp".
            expect(result).toContain('employees');
            expect(result).not.toContain('emp ');
        });

        it('applies column alias from schemaAliasMap', () => {
            const ast = parse(
                'SELECT emp.sal FROM northwind.emp'
            );
            const result = engine.generateTaskFromQuery({ query: ast as any, schema: 'northwind', schemaAliasMap: {
                tables:  { emp: 'Employees' },
                columns: { emp: { sal: 'Salary' } },
            } });
            // formatName lower-cases the alias; "salary" should appear instead of "sal".
            expect(result).toContain('salary');
            expect(result).not.toContain(' sal ');
        });

    });

});
