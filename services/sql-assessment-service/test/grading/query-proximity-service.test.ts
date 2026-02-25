import { describe, it, expect, beforeEach } from 'vitest';
import { Parser } from 'node-sql-parser';
import {
    QueryProximityService,
    ProximityHeuristic,
} from '../../src/grading/query-proximity-service';
import { ReferenceQuery } from '../../src/shared/interfaces/http';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const parser = new Parser();

function ref(query: string, stats?: ReferenceQuery['stats']): ReferenceQuery {
    return { query, stats };
}

const SCHEMA = 'northwind';

// ---------------------------------------------------------------------------
// SQL fixtures
// ---------------------------------------------------------------------------

/** Queries grouped by semantic intent to make the expected selection obvious. */
const SQL = {
    // --- Base query
    selectProductsAll:
        `SELECT p.product_name, p.unit_price FROM ${SCHEMA}.products p`,

    // --- Structurally identical, different alias name → same AST tokens
    selectProductsAliasQ:
        `SELECT q.product_name, q.unit_price FROM ${SCHEMA}.products q`,

    // --- Adds one extra column — close but not identical
    selectProductsThreeCols:
        `SELECT p.product_name, p.unit_price, p.units_in_stock FROM ${SCHEMA}.products p`,

    // --- Very different: GROUP BY + aggregate on a different table
    groupByCategory:
        `SELECT c.category_name, COUNT(p.product_id) FROM ${SCHEMA}.categories c ` +
        `INNER JOIN ${SCHEMA}.products p ON c.category_id = p.category_id ` +
        `GROUP BY c.category_name`,

    // --- Completely different: orders JOIN customers
    ordersWithCustomers:
        `SELECT o.order_id, c.company_name FROM ${SCHEMA}.orders o ` +
        `INNER JOIN ${SCHEMA}.customers c ON o.customer_id = c.customer_id`,

    // --- WHERE clause variant of base query
    selectProductsWhere:
        `SELECT p.product_name, p.unit_price FROM ${SCHEMA}.products p WHERE p.unit_price > 10`,

    // --- LIMIT variant
    selectProductsLimit:
        `SELECT p.product_name, p.unit_price FROM ${SCHEMA}.products p LIMIT 5`,

    // --- ORDER BY variant
    selectProductsOrderBy:
        `SELECT p.product_name, p.unit_price FROM ${SCHEMA}.products p ORDER BY p.unit_price DESC`,

    // --- Student query with a typo / extra filter — should match WHERE variant
    selectProductsWhereVariant:
        `SELECT p.product_name, p.unit_price FROM ${SCHEMA}.products p WHERE p.unit_price > 20`,

    // --- Unparseable SQL (triggers fallback to string tokenisation)
    unparseable: 'SELECT ??? FROM !!!',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('QueryProximityService', () => {
    let svc: QueryProximityService;

    beforeEach(() => {
        svc = new QueryProximityService();
    });

    // =========================================================================
    // selectClosest — basic selection
    // =========================================================================

    describe('selectClosest — basic selection', () => {
        it('returns the only candidate when the collection has one entry', () => {
            const candidates = [ref(SQL.selectProductsAll)];
            const result = svc.selectClosest(SQL.selectProductsAll, candidates);
            expect(result.referenceQuery).toBe(candidates[0]);
            expect(result.candidateIndex).toBe(0);
        });

        it('throws when candidates array is empty', () => {
            expect(() => svc.selectClosest(SQL.selectProductsAll, [])).toThrow();
        });

        it('selects the identical query when it is one of the candidates', () => {
            const candidates = [
                ref(SQL.groupByCategory),
                ref(SQL.selectProductsAll),
                ref(SQL.ordersWithCustomers),
            ];
            const result = svc.selectClosest(SQL.selectProductsAll, candidates);
            expect(result.referenceQuery.query).toBe(SQL.selectProductsAll);
            expect(result.distance).toBe(0);
        });

        it('selects the closest candidate, not the first', () => {
            // student = two-column products query
            // candidate[0] = orders+customers (very different)
            // candidate[1] = three-column products (one token more — close)
            const candidates = [
                ref(SQL.ordersWithCustomers),
                ref(SQL.selectProductsThreeCols),
            ];
            const result = svc.selectClosest(SQL.selectProductsAll, candidates);
            expect(result.referenceQuery.query).toBe(SQL.selectProductsThreeCols);
            expect(result.candidateIndex).toBe(1);
        });

        it('selects the WHERE variant when the student query has a similar WHERE clause', () => {
            const candidates = [
                ref(SQL.ordersWithCustomers),
                ref(SQL.groupByCategory),
                ref(SQL.selectProductsWhere),
            ];
            const result = svc.selectClosest(SQL.selectProductsWhereVariant, candidates);
            expect(result.referenceQuery.query).toBe(SQL.selectProductsWhere);
        });

        it('prefers the earlier candidate on a tie (stable tie-breaking)', () => {
            // Both candidates are identical copies — first should win
            const q1 = ref(SQL.selectProductsAll);
            const q2 = ref(SQL.selectProductsAll);
            const result = svc.selectClosest(SQL.selectProductsAll, [q1, q2]);
            expect(result.candidateIndex).toBe(0);
        });
    });

    // =========================================================================
    // selectClosest — heuristic selection
    // =========================================================================

    describe('selectClosest — heuristic parameter', () => {
        it('returns a result with the requested heuristic label', () => {
            const candidates = [ref(SQL.selectProductsAll), ref(SQL.groupByCategory)];

            const astResult = svc.selectClosest(
                SQL.selectProductsAll, candidates, ProximityHeuristic.ASTEditDistance
            );
            expect(astResult.heuristic).toBe(ProximityHeuristic.ASTEditDistance);

            const tokResult = svc.selectClosest(
                SQL.selectProductsAll, candidates, ProximityHeuristic.TokenLevenshtein
            );
            expect(tokResult.heuristic).toBe(ProximityHeuristic.TokenLevenshtein);
        });

        it('both heuristics agree on the closest query for structurally clear cases', () => {
            const candidates = [
                ref(SQL.ordersWithCustomers),   // very different
                ref(SQL.selectProductsThreeCols), // close
            ];
            const astResult = svc.selectClosest(SQL.selectProductsAll, candidates, ProximityHeuristic.ASTEditDistance);
            const tokResult = svc.selectClosest(SQL.selectProductsAll, candidates, ProximityHeuristic.TokenLevenshtein);
            // Both should prefer the products variant
            expect(astResult.referenceQuery.query).toBe(SQL.selectProductsThreeCols);
            expect(tokResult.referenceQuery.query).toBe(SQL.selectProductsThreeCols);
        });
    });

    // =========================================================================
    // selectClosest — stats field is preserved
    // =========================================================================

    describe('selectClosest — stats passthrough', () => {
        it('preserves the stats object on the returned reference query', () => {
            const stats = { timesFoundByStudents: 42, averageAttemptsToFind: 2.5 };
            const candidates = [
                ref(SQL.ordersWithCustomers, {}),
                ref(SQL.selectProductsAll, stats),
            ];
            const result = svc.selectClosest(SQL.selectProductsAll, candidates);
            expect(result.referenceQuery.stats).toEqual(stats);
        });
    });

    // =========================================================================
    // astEditDistance
    // =========================================================================

    describe('astEditDistance', () => {
        it('returns 0 for the exact same query string', () => {
            expect(svc.astEditDistance(SQL.selectProductsAll, SQL.selectProductsAll)).toBe(0);
        });

        it('returns 0 for alias-renamed but structurally identical queries', () => {
            // p.product_name and q.product_name resolve to the same token after alias normalisation
            expect(svc.astEditDistance(SQL.selectProductsAll, SQL.selectProductsAliasQ)).toBe(0);
        });

        it('returns a small positive distance for a one-column difference', () => {
            const d = svc.astEditDistance(SQL.selectProductsAll, SQL.selectProductsThreeCols);
            expect(d).toBeGreaterThan(0);
            expect(d).toBeLessThan(5);
        });

        it('returns a larger distance for semantically unrelated queries', () => {
            const dClose = svc.astEditDistance(SQL.selectProductsAll, SQL.selectProductsThreeCols);
            const dFar   = svc.astEditDistance(SQL.selectProductsAll, SQL.ordersWithCustomers);
            expect(dFar).toBeGreaterThan(dClose);
        });

        it('is commutative (distance(a,b) === distance(b,a))', () => {
            const d1 = svc.astEditDistance(SQL.selectProductsAll, SQL.groupByCategory);
            const d2 = svc.astEditDistance(SQL.groupByCategory, SQL.selectProductsAll);
            expect(d1).toBe(d2);
        });

        it('returns a finite distance when one query is unparseable (fallback)', () => {
            const d = svc.astEditDistance(SQL.unparseable, SQL.selectProductsAll);
            expect(Number.isFinite(d)).toBe(true);
        });

        it('orders variants by expected distance from the base query', () => {
            // The WHERE variant adds one predicate — further than the alias variant (distance 0)
            // but closer than the completely different GROUP BY query
            const dAlias   = svc.astEditDistance(SQL.selectProductsAll, SQL.selectProductsAliasQ);
            const dWhere   = svc.astEditDistance(SQL.selectProductsAll, SQL.selectProductsWhere);
            const dGroupBy = svc.astEditDistance(SQL.selectProductsAll, SQL.groupByCategory);

            expect(dAlias).toBe(0);
            expect(dWhere).toBeGreaterThan(dAlias);
            expect(dGroupBy).toBeGreaterThan(dWhere);
        });
    });

    // =========================================================================
    // tokenLevenshteinDistance
    // =========================================================================

    describe('tokenLevenshteinDistance', () => {
        it('returns 0 for identical strings', () => {
            expect(svc.tokenLevenshteinDistance('SELECT a FROM t', 'SELECT a FROM t')).toBe(0);
        });

        it('returns a positive value when tokens differ', () => {
            expect(
                svc.tokenLevenshteinDistance('SELECT a FROM t', 'SELECT b FROM t')
            ).toBeGreaterThan(0);
        });

        it('is case-insensitive', () => {
            const d = svc.tokenLevenshteinDistance('SELECT a FROM t', 'select a from t');
            expect(d).toBe(0);
        });
    });

    // =========================================================================
    // levenshtein (unit tests of the core algorithm)
    // =========================================================================

    describe('levenshtein', () => {
        it('returns 0 for two empty arrays', () => {
            expect(svc.levenshtein([], [])).toBe(0);
        });

        it('returns the length of b when a is empty', () => {
            expect(svc.levenshtein([], ['a', 'b', 'c'])).toBe(3);
        });

        it('returns the length of a when b is empty', () => {
            expect(svc.levenshtein(['a', 'b'], [])).toBe(2);
        });

        it('returns 0 for equal arrays', () => {
            expect(svc.levenshtein(['x', 'y'], ['x', 'y'])).toBe(0);
        });

        it('returns 1 for a single substitution', () => {
            expect(svc.levenshtein(['a', 'b', 'c'], ['a', 'X', 'c'])).toBe(1);
        });

        it('returns 1 for a single insertion', () => {
            expect(svc.levenshtein(['a', 'c'], ['a', 'b', 'c'])).toBe(1);
        });

        it('returns 1 for a single deletion', () => {
            expect(svc.levenshtein(['a', 'b', 'c'], ['a', 'c'])).toBe(1);
        });

        it('is symmetric', () => {
            const a = ['select', 'from', 'where'];
            const b = ['select', 'group_by', 'having'];
            expect(svc.levenshtein(a, b)).toBe(svc.levenshtein(b, a));
        });

        it('obeys the triangle inequality', () => {
            const a = ['a', 'b'];
            const b = ['a', 'c'];
            const c = ['x', 'y'];
            expect(svc.levenshtein(a, c)).toBeLessThanOrEqual(
                svc.levenshtein(a, b) + svc.levenshtein(b, c)
            );
        });
    });

    // =========================================================================
    // tokeniseAST — output shape
    // =========================================================================

    describe('tokeniseAST', () => {
        function parse(sql: string) {
            const ast = parser.astify(sql, { database: 'postgresql' });
            return Array.isArray(ast) ? ast[0] : ast;
        }

        it('always includes "select" as the first token for a SELECT query', () => {
            const tokens = svc.tokeniseAST(parse(SQL.selectProductsAll));
            expect(tokens[0]).toBe('select');
        });

        it('produces identical token sequences for alias-renamed equivalents', () => {
            const tokP = svc.tokeniseAST(parse(SQL.selectProductsAll));     // alias p
            const tokQ = svc.tokeniseAST(parse(SQL.selectProductsAliasQ));  // alias q
            expect(tokP).toEqual(tokQ);
        });

        it('includes "where" token for a query with a WHERE clause', () => {
            const tokens = svc.tokeniseAST(parse(SQL.selectProductsWhere));
            expect(tokens).toContain('where');
        });

        it('includes "group_by" token for a GROUP BY query', () => {
            const tokens = svc.tokeniseAST(parse(SQL.groupByCategory));
            expect(tokens).toContain('group_by');
        });

        it('includes "distinct" token for SELECT DISTINCT', () => {
            const sql = `SELECT DISTINCT p.category_id FROM ${SCHEMA}.products p`;
            const tokens = svc.tokeniseAST(parse(sql));
            expect(tokens).toContain('distinct');
        });

        it('includes "limit" token for a LIMIT clause', () => {
            const tokens = svc.tokeniseAST(parse(SQL.selectProductsLimit));
            expect(tokens).toContain('limit');
            expect(tokens).toContain('5');
        });

        it('includes "order_by" token for an ORDER BY clause', () => {
            const tokens = svc.tokeniseAST(parse(SQL.selectProductsOrderBy));
            expect(tokens).toContain('order_by');
        });

        it('produces a shorter token sequence for the simpler of two queries', () => {
            const tokSimple = svc.tokeniseAST(parse(SQL.selectProductsAll));
            const tokGroupBy = svc.tokeniseAST(parse(SQL.groupByCategory));
            // GROUP BY + JOIN + aggregate adds tokens
            expect(tokGroupBy.length).toBeGreaterThan(tokSimple.length);
        });

        it('column tokens are order-independent (sorted) so column-order variants are equal', () => {
            const q1 = `SELECT p.product_name, p.unit_price FROM ${SCHEMA}.products p`;
            const q2 = `SELECT p.unit_price, p.product_name FROM ${SCHEMA}.products p`;
            expect(svc.tokeniseAST(parse(q1))).toEqual(svc.tokeniseAST(parse(q2)));
        });
    });

    // =========================================================================
    // tokeniseSQLString
    // =========================================================================

    describe('tokeniseSQLString', () => {
        it('splits on whitespace', () => {
            expect(svc.tokeniseSQLString('SELECT a FROM t')).toEqual(['select', 'a', 'from', 't']);
        });

        it('splits on parentheses', () => {
            const tokens = svc.tokeniseSQLString('COUNT(a)');
            expect(tokens).toContain('count');
            expect(tokens).toContain('a');
        });

        it('lower-cases all tokens', () => {
            const tokens = svc.tokeniseSQLString('SELECT A FROM T');
            expect(tokens.every(t => t === t.toLowerCase())).toBe(true);
        });

        it('filters out empty tokens', () => {
            const tokens = svc.tokeniseSQLString('  SELECT  a  ');
            expect(tokens.every(t => t.length > 0)).toBe(true);
        });
    });

    // =========================================================================
    // End-to-end: multiple reference queries with stats
    // =========================================================================

    describe('end-to-end with stats', () => {
        it('selects the structurally closest reference query from a realistic cohort set', () => {
            // Simulate a cohort of three reference solutions for the same task:
            // - A simple join (unexpected shortcut by some students)
            // - A WHERE-filter query (the intended solution)
            // - A CTE-based solution (advanced variant)
            const cohort: ReferenceQuery[] = [
                {
                    query: SQL.ordersWithCustomers,
                    stats: { timesFoundByStudents: 5, averageAttemptsToFind: 8 },
                },
                {
                    query: SQL.selectProductsWhere,
                    stats: { timesFoundByStudents: 120, averageAttemptsToFind: 2.1 },
                },
                {
                    query: `WITH cte AS (SELECT * FROM ${SCHEMA}.products) SELECT cte.product_name, cte.unit_price FROM cte WHERE cte.unit_price > 10`,
                    stats: { timesFoundByStudents: 3, averageAttemptsToFind: 12 },
                },
            ];

            // Student wrote a WHERE variant — should match the second reference
            const result = svc.selectClosest(
                SQL.selectProductsWhereVariant,
                cohort,
                ProximityHeuristic.ASTEditDistance
            );

            expect(result.referenceQuery.query).toBe(SQL.selectProductsWhere);
            expect(result.referenceQuery.stats?.timesFoundByStudents).toBe(120);
        });

        it('selects the most structurally similar query regardless of stats values', () => {
            // Stats should never influence selection — only distance does
            const cohort: ReferenceQuery[] = [
                {
                    // Structurally distant but "popular"
                    query: SQL.groupByCategory,
                    stats: { timesFoundByStudents: 9999, averageAttemptsToFind: 1 },
                },
                {
                    // Closest structurally but "rare"
                    query: SQL.selectProductsThreeCols,
                    stats: { timesFoundByStudents: 1, averageAttemptsToFind: 20 },
                },
            ];

            const result = svc.selectClosest(SQL.selectProductsAll, cohort);
            // Distance — not popularity — must drive the decision
            expect(result.referenceQuery.query).toBe(SQL.selectProductsThreeCols);
        });
    });
});
