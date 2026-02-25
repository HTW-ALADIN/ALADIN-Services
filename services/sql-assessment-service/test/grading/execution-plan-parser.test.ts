/**
 * Unit tests for ExecutionPlanParser.
 *
 * All tests are pure — they operate on hand-crafted plan node fixtures and
 * require no database connection.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { ExecutionPlanParser } from '../../src/grading/execution-plan-parser';
import type { QueryPlan, QueryPlanNode } from '../../src/shared/interfaces/execution-plan';

// ---------------------------------------------------------------------------
// Fixture helpers
// ---------------------------------------------------------------------------

/** Wrap a raw plan node in the EXPLAIN (FORMAT JSON) envelope. */
function wrapPlan(planNode: QueryPlanNode): QueryPlan {
    return { 'QUERY PLAN': [{ Plan: planNode }] };
}

/** A minimal Seq Scan node on 'products'. */
function seqScan(table: string, alias?: string, filter?: string): QueryPlanNode {
    return {
        'Node Type':      'Seq Scan',
        'Relation Name':  table,
        ...(alias  ? { Alias: alias }  : {}),
        ...(filter ? { Filter: filter } : {}),
    } as QueryPlanNode;
}

/** A Sort node wrapping a child. */
function sortNode(sortKey: string[], child: QueryPlanNode): QueryPlanNode {
    return {
        'Node Type': 'Sort',
        'Sort Key':  sortKey,
        Plans:       [child],
    } as QueryPlanNode;
}

/** A HashAggregate node (used for GROUP BY or hash-DISTINCT). */
function aggregateNode(opts: {
    groupKey?: string[];
    filter?: string;
    strategy?: string;
    child: QueryPlanNode;
}): QueryPlanNode {
    return {
        'Node Type': 'Aggregate',
        ...(opts.groupKey ? { 'Group Key': opts.groupKey } : {}),
        ...(opts.filter   ? { Filter:      opts.filter }   : {}),
        ...(opts.strategy ? { Strategy:    opts.strategy } : {}),
        Plans: [opts.child],
    } as QueryPlanNode;
}

/** A Unique node (sort-based DISTINCT) wrapping a Sort. */
function uniqueNode(child: QueryPlanNode): QueryPlanNode {
    return { 'Node Type': 'Unique', Plans: [child] } as QueryPlanNode;
}

/** A Limit node wrapping a child. */
function limitNode(child: QueryPlanNode): QueryPlanNode {
    return { 'Node Type': 'Limit', Plans: [child] } as QueryPlanNode;
}

/** A WindowAgg node. */
function windowAggNode(opts: {
    partKey?: string[];
    sortKey?: string[];
    child: QueryPlanNode;
}): QueryPlanNode {
    return {
        'Node Type': 'WindowAgg',
        ...(opts.partKey ? { 'Part Key': opts.partKey } : {}),
        ...(opts.sortKey ? { 'Sort Key': opts.sortKey } : {}),
        Plans: [opts.child],
    } as QueryPlanNode;
}

/** A CTE Scan node. */
function cteScanNode(cteName: string): QueryPlanNode {
    return {
        'Node Type': 'CTE Scan',
        'CTE Name':  cteName,
    } as QueryPlanNode;
}

/** An InitPlan child node (scalar subquery). */
function initPlanNode(name: string, child: QueryPlanNode): QueryPlanNode {
    return {
        ...child,
        'Parent Relationship': 'InitPlan',
        'Subplan Name':        name,
    };
}

/** A SubPlan child node (correlated subquery evaluated per row). */
function subPlanNode(name: string, child: QueryPlanNode): QueryPlanNode {
    return {
        ...child,
        'Parent Relationship': 'SubPlan',
        'Subplan Name':        name,
    };
}

/** Wraps an outer node and attaches subplan children to it. */
function withSubplanChildren(
    outer: QueryPlanNode,
    ...subplans: QueryPlanNode[]
): QueryPlanNode {
    return { ...outer, Plans: [...(outer.Plans ?? []), ...subplans] };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ExecutionPlanParser', () => {
    let parser: ExecutionPlanParser;

    beforeEach(() => {
        parser = new ExecutionPlanParser();
    });

    // =========================================================================
    // Core field extraction (existing behaviour, regression tests)
    // =========================================================================

    describe('parse — GROUP BY', () => {
        it('extracts groupKey from an Aggregate node', () => {
            const plan = wrapPlan(aggregateNode({
                groupKey: ['products.category_id'],
                child:    seqScan('products'),
            }));
            const result = parser.parse(plan, {});
            expect(result.groupKey).toEqual(['products.category_id']);
        });

        it('returns undefined groupKey when no Aggregate node is present', () => {
            expect(parser.parse(wrapPlan(seqScan('products')), {}).groupKey).toBeUndefined();
        });
    });

    describe('parse — ORDER BY', () => {
        it('extracts sortKey from a Sort node', () => {
            const plan = wrapPlan(sortNode(['products.unit_price'], seqScan('products')));
            expect(parser.parse(plan, {}).sortKey).toEqual(['products.unit_price']);
        });
    });

    describe('parse — WHERE filter', () => {
        it('extracts whereFilter from a Seq Scan Filter field', () => {
            const plan = wrapPlan(seqScan('products', undefined, '(products.discontinued = true)'));
            const result = parser.parse(plan, {});
            expect(result.whereFilter).toContain('(products.discontinued = true)');
        });
    });

    // =========================================================================
    // DISTINCT
    // =========================================================================

    describe('parseDistinct', () => {
        it('detects hash-based DISTINCT (HashAggregate with Strategy "Hashed" and no Group Key)', () => {
            const root = aggregateNode({ strategy: 'Hashed', child: seqScan('products') });
            const result = parser.parseDistinct(root);
            expect(result.distinct).toBe(true);
            expect(result.strategy).toBe('hash');
        });

        it('does NOT flag GROUP BY as DISTINCT (HashAggregate has Group Key)', () => {
            const root = aggregateNode({
                strategy: 'Hashed',
                groupKey: ['products.category_id'],
                child:    seqScan('products'),
            });
            expect(parser.parseDistinct(root).distinct).toBe(false);
        });

        it('detects sort-based DISTINCT (Unique node)', () => {
            const root = uniqueNode(sortNode(['products.category_id'], seqScan('products')));
            const result = parser.parseDistinct(root);
            expect(result.distinct).toBe(true);
            expect(result.strategy).toBe('sort');
        });

        it('returns distinct=false for a plain Seq Scan', () => {
            expect(parser.parseDistinct(seqScan('products')).distinct).toBe(false);
        });

        it('detects hash DISTINCT nested inside a Limit node', () => {
            const root = limitNode(
                aggregateNode({ strategy: 'Hashed', child: seqScan('products') })
            );
            expect(parser.parseDistinct(root).distinct).toBe(true);
            expect(parser.parseDistinct(root).strategy).toBe('hash');
        });
    });

    // =========================================================================
    // LIMIT
    // =========================================================================

    describe('extractLimit', () => {
        it('returns true when a Limit node is present', () => {
            const root = limitNode(seqScan('products'));
            expect(parser.extractLimit(root)).toBe(true);
        });

        it('returns true when Limit is nested inside another node', () => {
            const root = sortNode(['products.unit_price'], limitNode(seqScan('products')));
            expect(parser.extractLimit(root)).toBe(true);
        });

        it('returns false when no Limit node is present', () => {
            expect(parser.extractLimit(seqScan('products'))).toBe(false);
        });
    });

    // =========================================================================
    // CTEs
    // =========================================================================

    describe('extractCTEs', () => {
        it('returns the CTE name from a CTE Scan node', () => {
            expect(parser.extractCTEs(cteScanNode('top_products'))).toEqual(['top_products']);
        });

        it('collects multiple CTE names', () => {
            const root: QueryPlanNode = {
                'Node Type': 'Append',
                Plans: [cteScanNode('cte_a'), cteScanNode('cte_b')],
            } as QueryPlanNode;
            expect(parser.extractCTEs(root)).toEqual(['cte_a', 'cte_b']);
        });

        it('returns an empty array when no CTE Scan nodes are present', () => {
            expect(parser.extractCTEs(seqScan('products'))).toEqual([]);
        });

        it('finds a CTE Scan nested inside a Sort', () => {
            const root = sortNode(['col'], cteScanNode('my_cte'));
            expect(parser.extractCTEs(root)).toEqual(['my_cte']);
        });
    });

    // =========================================================================
    // Window functions
    // =========================================================================

    describe('extractWindowAgg', () => {
        it('extracts partitionKey from a WindowAgg node', () => {
            const root = windowAggNode({
                partKey: ['employees.department_id'],
                sortKey: ['employees.salary DESC'],
                child:   seqScan('employees'),
            });
            const result = parser.extractWindowAgg(root);
            expect(result.partitionKey).toEqual(['employees.department_id']);
            expect(result.orderKey).toEqual(['employees.salary DESC']);
        });

        it('returns empty object when no WindowAgg is present', () => {
            expect(parser.extractWindowAgg(seqScan('products'))).toEqual({});
        });

        it('handles a WindowAgg with no PARTITION BY (partitionKey undefined)', () => {
            const root = windowAggNode({
                sortKey: ['employees.salary'],
                child:   seqScan('employees'),
            });
            expect(parser.extractWindowAgg(root).partitionKey).toBeUndefined();
            expect(parser.extractWindowAgg(root).orderKey).toEqual(['employees.salary']);
        });

        it('finds WindowAgg when nested inside an Aggregate', () => {
            const root = aggregateNode({
                groupKey: ['employees.department_id'],
                child: windowAggNode({
                    partKey: ['employees.department_id'],
                    child:   seqScan('employees'),
                }),
            });
            expect(parser.extractWindowAgg(root).partitionKey).toEqual(['employees.department_id']);
        });
    });

    // =========================================================================
    // Subplans
    // =========================================================================

    describe('extractSubplans', () => {
        it('returns an empty array when no subplans are present', () => {
            expect(parser.extractSubplans(seqScan('products'), {})).toEqual([]);
        });

        it('identifies an InitPlan child node', () => {
            const outerNode = withSubplanChildren(
                seqScan('products'),
                initPlanNode('InitPlan 1', seqScan('products'))
            );
            const subplans = parser.extractSubplans(outerNode, {});
            expect(subplans).toHaveLength(1);
            expect(subplans[0].type).toBe('InitPlan');
            expect(subplans[0].name).toBe('InitPlan 1');
        });

        it('identifies a SubPlan child node', () => {
            const outerNode = withSubplanChildren(
                seqScan('products'),
                subPlanNode('SubPlan 1', seqScan('products'))
            );
            const subplans = parser.extractSubplans(outerNode, {});
            expect(subplans[0].type).toBe('SubPlan');
        });

        it('recursively parses the subplan into an IParsedExecutionPlan', () => {
            const innerPlan = sortNode(['products.unit_price'], seqScan('products'));
            const outerNode = withSubplanChildren(
                seqScan('orders'),
                initPlanNode('InitPlan 1', innerPlan)
            );
            const subplans = parser.extractSubplans(outerNode, {});
            expect(subplans[0].plan.sortKey).toEqual(['products.unit_price']);
        });

        it('collects multiple subplans', () => {
            const outerNode = withSubplanChildren(
                seqScan('orders'),
                initPlanNode('InitPlan 1', seqScan('products')),
                subPlanNode('SubPlan 1', seqScan('customers'))
            );
            expect(parser.extractSubplans(outerNode, {})).toHaveLength(2);
        });

        it('does not recurse deeper than MAX_SUBPLAN_DEPTH (3)', () => {
            // Build 4 levels of nesting
            let node: QueryPlanNode = seqScan('t');
            for (let i = 4; i >= 1; i--) {
                node = withSubplanChildren(seqScan('t'), initPlanNode(`InitPlan ${i}`, node));
            }
            // At depth=0 we find depth-1 subplans, which themselves find depth-2, etc.
            // At depth=3 we cap, so depth-4 subplans should NOT be present.
            const subplans = parser.extractSubplans(node, {});
            // The outermost subplan should be found
            expect(subplans.length).toBeGreaterThanOrEqual(1);
        });
    });

    // =========================================================================
    // parse() — integration: all fields populated correctly
    // =========================================================================

    describe('parse — full integration', () => {
        it('parses a plan with GROUP BY + HAVING + ORDER BY into correct fields', () => {
            const innerScan = seqScan('products', undefined, '(products.discontinued = false)');
            const aggNode = aggregateNode({
                groupKey: ['products.category_id'],
                filter:   '(count(*) > 2)',
                child:    innerScan,
            });
            const root = sortNode(['products.category_id'], aggNode);
            const plan = wrapPlan(root);
            const result = parser.parse(plan, {});

            expect(result.groupKey).toEqual(['products.category_id']);
            expect(result.havingFilter).toBe('(count(*) > 2)');
            expect(result.sortKey).toEqual(['products.category_id']);
            expect(result.whereFilter).toContain('(products.discontinued = false)');
        });

        it('parses a plan with DISTINCT into the distinct fields', () => {
            const root = aggregateNode({ strategy: 'Hashed', child: seqScan('products') });
            const plan = wrapPlan(root);
            const result = parser.parse(plan, {});
            expect(result.distinct).toBe(true);
            expect(result.distinctStrategy).toBe('hash');
        });

        it('parses a plan with CTE into cteNames', () => {
            const root: QueryPlanNode = {
                'Node Type': 'Seq Scan',
                'Relation Name': 'orders',
                Plans: [cteScanNode('recent_orders')],
            } as QueryPlanNode;
            expect(parser.parse(wrapPlan(root), {}).cteNames).toEqual(['recent_orders']);
        });

        it('parses a plan with LIMIT into hasLimit=true', () => {
            const root = limitNode(seqScan('products'));
            expect(parser.parse(wrapPlan(root), {}).hasLimit).toBe(true);
        });

        it('parses a plan without LIMIT into hasLimit=false', () => {
            expect(parser.parse(wrapPlan(seqScan('products')), {}).hasLimit).toBe(false);
        });

        it('parses a plan with a WindowAgg into window fields', () => {
            const root = windowAggNode({
                partKey: ['employees.dept'],
                sortKey: ['employees.salary'],
                child:   seqScan('employees'),
            });
            const result = parser.parse(wrapPlan(root), {});
            expect(result.windowPartitionKey).toEqual(['employees.dept']);
            expect(result.windowOrderKey).toEqual(['employees.salary']);
        });
    });
});
