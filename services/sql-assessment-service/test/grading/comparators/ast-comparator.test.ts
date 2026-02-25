import { describe, it, expect, beforeEach } from 'vitest';
import { Parser } from 'node-sql-parser';
import { AST, Select } from 'node-sql-parser';
import { ASTComparator } from '../../../src/grading/comparators/ast-comparator';
import { JoinComparator } from '../../../src/grading/join-comparator';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const parser = new Parser();

function parse(sql: string): AST {
    const ast = parser.astify(sql, { database: 'postgresql' });
    return Array.isArray(ast) ? ast[0] : ast;
}

const SCHEMA = 'northwind';

// ---------------------------------------------------------------------------
// Fixtures — kept in one place so test intent stays readable
// ---------------------------------------------------------------------------

const SQL = {
    selectAll:        `SELECT * FROM ${SCHEMA}.products`,
    selectCols:       `SELECT products.product_name, products.unit_price FROM ${SCHEMA}.products`,
    selectColsOther:  `SELECT products.unit_price, products.product_name FROM ${SCHEMA}.products`,
    selectWrongCol:   `SELECT products.product_name, products.units_in_stock FROM ${SCHEMA}.products`,
    selectFewCols:    `SELECT products.product_name FROM ${SCHEMA}.products`,
    selectMoreCols:   `SELECT products.product_name, products.unit_price, products.units_in_stock FROM ${SCHEMA}.products`,
    selectCount:      `SELECT COUNT(products.product_id) FROM ${SCHEMA}.products`,
    selectSum:        `SELECT SUM(order_details.quantity) FROM ${SCHEMA}.order_details`,
    selectDistinct:   `SELECT DISTINCT products.category_id FROM ${SCHEMA}.products`,
    withAlias:        `SELECT p.product_name FROM ${SCHEMA}.products p`,
    selfJoin:         `SELECT e1.first_name, e2.first_name FROM ${SCHEMA}.employees e1 INNER JOIN ${SCHEMA}.employees e2 ON e1.reports_to = e2.employee_id`,
    innerJoin:        `SELECT * FROM ${SCHEMA}.orders o INNER JOIN ${SCHEMA}.customers c ON o.customer_id = c.customer_id`,
    whereSubquery:    `SELECT * FROM ${SCHEMA}.products WHERE unit_price > (SELECT AVG(unit_price) FROM ${SCHEMA}.products)`,
    derivedTable:     `SELECT sub.product_name FROM (SELECT product_name FROM ${SCHEMA}.products) AS sub`,
    cte:              `WITH top_products AS (SELECT product_id FROM ${SCHEMA}.products WHERE unit_price > 20) SELECT * FROM top_products`,
    withLimit:        `SELECT * FROM ${SCHEMA}.products LIMIT 5`,
    withLimitOffset:  `SELECT * FROM ${SCHEMA}.products LIMIT 5 OFFSET 10`,
    withOffset:       `SELECT * FROM ${SCHEMA}.products LIMIT 10 OFFSET 3`,
    noLimit:          `SELECT * FROM ${SCHEMA}.products`,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ASTComparator', () => {
    let comparator: ASTComparator;

    beforeEach(() => {
        comparator = new ASTComparator(new JoinComparator());
    });

    // =========================================================================
    // compare — identical / matching queries
    // =========================================================================

    describe('compare — identical queries', () => {
        it('returns columnsMatch=true and supported=true for identical SELECT * queries', () => {
            const ast = parse(SQL.selectAll);
            const result = comparator.compare(ast, ast);
            expect(result.supported).toBe(true);
            expect(result.columnsMatch).toBe(true);
        });

        it('returns columnsMatch=true for identical named-column queries', () => {
            const ast = parse(SQL.selectCols);
            const result = comparator.compare(ast, ast);
            expect(result.columnsMatch).toBe(true);
        });

        it('returns columnsMatch=true when columns appear in a different order', () => {
            const student   = parse(SQL.selectColsOther); // price, name
            const reference = parse(SQL.selectCols);       // name, price
            const result = comparator.compare(student, reference);
            expect(result.columnsMatch).toBe(true);
        });
    });

    // =========================================================================
    // compare — column mismatches
    // =========================================================================

    describe('compare — column mismatches', () => {
        it('returns columnsMatch=false when the student selects a different column', () => {
            const result = comparator.compare(parse(SQL.selectWrongCol), parse(SQL.selectCols));
            expect(result.columnsMatch).toBe(false);
        });

        it('returns columnsMatch=false when the student selects fewer columns', () => {
            const result = comparator.compare(parse(SQL.selectFewCols), parse(SQL.selectCols));
            expect(result.columnsMatch).toBe(false);
        });

        it('returns columnsMatch=false when the student selects more columns', () => {
            const result = comparator.compare(parse(SQL.selectMoreCols), parse(SQL.selectCols));
            expect(result.columnsMatch).toBe(false);
        });

        it('includes ast.columns feedback when columns do not match', () => {
            const result = comparator.compare(parse(SQL.selectWrongCol), parse(SQL.selectCols));
            expect(result.ast?.columns).toBeDefined();
        });

        it('includes ast.columns.solution listing the required columns', () => {
            const result = comparator.compare(parse(SQL.selectFewCols), parse(SQL.selectCols));
            expect(result.ast?.columns?.solution).toBeDefined();
            expect(result.ast?.columns?.solution).toContain('columns');
        });
    });

    // =========================================================================
    // compare — aggregate functions
    // =========================================================================

    describe('compare — aggregate functions', () => {
        it('returns columnsMatch=true when aggregate function and column match', () => {
            const ast = parse(SQL.selectCount);
            expect(comparator.compare(ast, ast).columnsMatch).toBe(true);
        });

        it('returns columnsMatch=false when the aggregate function type differs (SUM vs COUNT)', () => {
            const result = comparator.compare(parse(SQL.selectSum), parse(SQL.selectCount));
            expect(result.columnsMatch).toBe(false);
        });
    });

    // =========================================================================
    // compare — alias resolution
    // =========================================================================

    describe('compare — alias resolution', () => {
        it('returns columnsMatch=true when aliases resolve to the same table', () => {
            const aliased  = parse(SQL.withAlias);   // p.product_name
            const unaliased = parse(SQL.selectFewCols); // products.product_name
            const result = comparator.compare(aliased, unaliased);
            expect(result.columnsMatch).toBe(true);
        });

        it('builds correct alias maps for a self-join query', () => {
            const ast = parse(SQL.selfJoin) as Select;
            const aliasMap = comparator.buildAliasMap(ast.from as any[]);
            // e1 and e2 should resolve to employees0 / employees1 (or vice-versa)
            expect(Object.values(aliasMap)).toContain('employees0');
            expect(Object.values(aliasMap)).toContain('employees1');
        });
    });

    // =========================================================================
    // Supported structures (no longer rejected)
    // =========================================================================

    describe('compare — structures now supported', () => {
        it('returns supported=true for SELECT DISTINCT (no longer rejected)', () => {
            const ast = parse(SQL.selectDistinct);
            const result = comparator.compare(ast, ast);
            expect(result.supported).toBe(true);
        });

        it('returns supported=true for a WHERE-clause scalar subquery', () => {
            const ast = parse(SQL.whereSubquery);
            const result = comparator.compare(ast, ast);
            expect(result.supported).toBe(true);
        });

        it('returns supported=true for a CTE query', () => {
            const ast = parse(SQL.cte);
            const result = comparator.compare(ast, ast);
            expect(result.supported).toBe(true);
        });
    });

    // =========================================================================
    // FROM-clause derived-table subqueries (still unsupported)
    // =========================================================================

    describe('compare — FROM-clause derived-table subquery (still unsupported)', () => {
        it('returns supported=false for a FROM-clause derived-table subquery', () => {
            const ast = parse(SQL.derivedTable);
            const result = comparator.compare(ast, ast);
            expect(result.supported).toBe(false);
        });

        it('returns supported=true for a plain SELECT without subqueries', () => {
            const ast = parse(SQL.selectCols);
            expect(comparator.compare(ast, ast).supported).toBe(true);
        });
    });

    // =========================================================================
    // compare — non-SELECT statements
    // =========================================================================

    describe('compare — non-SELECT statements', () => {
        it('returns supported=false when student AST type is not "select"', () => {
            const selectAST = parse(SQL.selectAll);
            // Fake a non-select AST by mutating the type
            const nonSelect = { ...selectAST, type: 'insert' } as unknown as AST;
            expect(comparator.compare(nonSelect, selectAST).supported).toBe(false);
        });
    });

    // =========================================================================
    // hasDerivedTableSubquery
    // =========================================================================

    describe('hasDerivedTableSubquery', () => {
        it('returns true for a FROM-clause derived table', () => {
            expect(comparator.hasDerivedTableSubquery(parse(SQL.derivedTable))).toBe(true);
        });

        it('returns false for a plain SELECT', () => {
            expect(comparator.hasDerivedTableSubquery(parse(SQL.selectAll))).toBe(false);
        });

        it('returns false for a WHERE-clause scalar subquery', () => {
            expect(comparator.hasDerivedTableSubquery(parse(SQL.whereSubquery))).toBe(false);
        });
    });

    // =========================================================================
    // hasDistinct
    // =========================================================================

    describe('hasDistinct', () => {
        it('returns true for SELECT DISTINCT', () => {
            expect(comparator.hasDistinct(parse(SQL.selectDistinct))).toBe(true);
        });

        it('returns false for a plain SELECT', () => {
            expect(comparator.hasDistinct(parse(SQL.selectAll))).toBe(false);
        });
    });

    // =========================================================================
    // hasCTE
    // =========================================================================

    describe('hasCTE', () => {
        it('returns true for a query with a WITH clause', () => {
            expect(comparator.hasCTE(parse(SQL.cte))).toBe(true);
        });

        it('returns false for a plain SELECT without CTEs', () => {
            expect(comparator.hasCTE(parse(SQL.selectAll))).toBe(false);
        });
    });

    // =========================================================================
    // hasScalarSubquery
    // =========================================================================

    describe('hasScalarSubquery', () => {
        it('returns true for a WHERE-clause scalar subquery', () => {
            expect(comparator.hasScalarSubquery(parse(SQL.whereSubquery))).toBe(true);
        });

        it('returns false for a plain SELECT', () => {
            expect(comparator.hasScalarSubquery(parse(SQL.selectAll))).toBe(false);
        });

        it('returns false for a FROM-clause derived table (not a scalar subquery)', () => {
            // hasDerivedTableSubquery handles this case; hasScalarSubquery should not
            // double-count it
            expect(comparator.hasScalarSubquery(parse(SQL.derivedTable))).toBe(false);
        });
    });

    // =========================================================================
    // buildAliasMap
    // =========================================================================

    describe('buildAliasMap', () => {
        it('returns an empty map when no aliases are present', () => {
            const ast = parse(SQL.selectAll) as Select;
            expect(comparator.buildAliasMap(ast.from as any[])).toEqual({});
        });

        it('maps a single alias to its real table name', () => {
            const ast = parse(SQL.withAlias) as Select;
            const map = comparator.buildAliasMap(ast.from as any[]);
            expect(map['p']).toBe('products');
        });

        it('maps multiple aliases in a JOIN to their real table names', () => {
            const ast = parse(SQL.innerJoin) as Select;
            const map = comparator.buildAliasMap(ast.from as any[]);
            expect(map['o']).toBe('orders');
            expect(map['c']).toBe('customers');
        });

        it('suffixes self-join aliases with 0 and 1', () => {
            const ast = parse(SQL.selfJoin) as Select;
            const map = comparator.buildAliasMap(ast.from as any[]);
            const values = Object.values(map);
            expect(values).toContain('employees0');
            expect(values).toContain('employees1');
        });
    });

    // =========================================================================
    // compareLimitOffset
    // =========================================================================

    describe('compareLimitOffset', () => {
        it('returns match=true when both queries have the same LIMIT', () => {
            const s = parse(SQL.withLimit) as Select;
            const result = comparator.compareLimitOffset(s, s);
            expect(result.match).toBe(true);
        });

        it('returns match=false when LIMIT values differ', () => {
            const s5  = parse(SQL.withLimit)  as Select;  // LIMIT 5
            const s10 = parse(SQL.withOffset) as Select;  // LIMIT 10 OFFSET 3
            const result = comparator.compareLimitOffset(s5, s10);
            expect(result.match).toBe(false);
            expect(result.ast?.limit?.message).toContain('LIMIT');
        });

        it('returns match=false when OFFSET values differ', () => {
            const withOffset    = parse(SQL.withLimitOffset) as Select; // LIMIT 5 OFFSET 10
            const withoutOffset = parse(SQL.withLimit)       as Select; // LIMIT 5
            const result = comparator.compareLimitOffset(withOffset, withoutOffset);
            expect(result.match).toBe(false);
            expect(result.ast?.offset?.message).toContain('OFFSET');
        });

        it('returns match=true when neither query has LIMIT', () => {
            const s = parse(SQL.noLimit) as Select;
            expect(comparator.compareLimitOffset(s, s).match).toBe(true);
        });

        it('includes ast.limit.solution when LIMIT differs', () => {
            const s5  = parse(SQL.withLimit)  as Select;
            const s10 = parse(SQL.withOffset) as Select;
            const result = comparator.compareLimitOffset(s5, s10);
            expect(result.ast?.limit?.solution).toBeDefined();
        });
    });

    // =========================================================================
    // compare — limitMatch propagation
    // =========================================================================

    describe('compare — limitMatch field', () => {
        it('sets limitMatch=true when LIMIT clauses match', () => {
            const ast = parse(SQL.withLimit);
            expect(comparator.compare(ast, ast).limitMatch).toBe(true);
        });

        it('sets limitMatch=false and adds ast.limit feedback when LIMIT clauses differ', () => {
            const s5  = parse(SQL.withLimit);  // LIMIT 5
            const s10 = parse(SQL.withOffset); // LIMIT 10 OFFSET 3
            const result = comparator.compare(s5, s10);
            expect(result.limitMatch).toBe(false);
            expect(result.ast?.limit?.message).toContain('LIMIT');
        });
    });
});
