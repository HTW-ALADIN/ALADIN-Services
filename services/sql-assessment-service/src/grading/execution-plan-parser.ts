import {
    IParsedExecutionPlan,
    JoinStatement,
    ParsedSubplan,
    QueryPlan,
    QueryPlanKeys,
    QueryPlanNode,
} from '../shared/interfaces/execution-plan';

/**
 * Parses a raw PostgreSQL EXPLAIN (FORMAT JSON) execution plan into a
 * normalised IParsedExecutionPlan structure suitable for comparison.
 *
 * Supports extraction of:
 *  - GROUP BY  (Aggregate / Group Key)
 *  - HAVING    (Aggregate / Filter)
 *  - ORDER BY  (Sort / Sort Key)
 *  - WHERE     (Seq Scan, Hash Join, Bitmap Heap Scan, Index Scan / Filter, Join Filter)
 *  - JOIN      (recursive JoinStatement tree)
 *  - DISTINCT  (HashAggregate with Strategy "Hashed" and no Group Key, or Unique node)
 *  - Subqueries (InitPlan / SubPlan child nodes, recursively parsed)
 *  - CTEs      (CTE Scan / CTE Name)
 *  - LIMIT     (Limit node presence)
 *  - Window functions (WindowAgg / Part Key + Sort Key)
 */
export class ExecutionPlanParser {

    /**
     * Parses the top-level EXPLAIN JSON into an IParsedExecutionPlan.
     *
     * @param executionPlan - The raw EXPLAIN (FORMAT JSON) output.
     * @param aliasMap      - Alias→table map used to normalise table references.
     */
    public parse(executionPlan: QueryPlan, aliasMap: Record<string, string>): IParsedExecutionPlan {
        const root = executionPlan['QUERY PLAN'][0]['Plan'];
        return this.parseNode(root, aliasMap);
    }

    /**
     * Parses a single plan node (and its children) into an IParsedExecutionPlan.
     * Called recursively for subplan nodes.
     */
    public parseNode(root: QueryPlanNode, aliasMap: Record<string, string>): IParsedExecutionPlan {
        const parsed: IParsedExecutionPlan = {};

        parsed.groupKey    = this.extractKeyForNodeType(root, 'Aggregate', 'Group Key');
        parsed.havingFilter = this.extractKeyForNodeType(root, 'Aggregate', 'Filter');
        parsed.sortKey     = this.extractKeyForNodeType(root, 'Sort', 'Sort Key');
        parsed.whereFilter = this.extractAllKeysForNodeType(
            root,
            ['Seq Scan', 'Hash Join', 'Bitmap Heap Scan', 'Index Scan'],
            ['Filter', 'Join Filter', 'Recheck Cond']
        );
        parsed.joinStatement = this.parseQueryPlanToJoinOrFromStatement(root, aliasMap);

        // New extractions
        const distinctInfo = this.parseDistinct(root);
        parsed.distinct         = distinctInfo.distinct;
        parsed.distinctStrategy = distinctInfo.strategy;

        parsed.subplans = this.extractSubplans(root, aliasMap);
        parsed.cteNames = this.extractCTEs(root);
        parsed.hasLimit = this.extractLimit(root);

        const windowInfo = this.extractWindowAgg(root);
        parsed.windowPartitionKey = windowInfo.partitionKey;
        parsed.windowOrderKey     = windowInfo.orderKey;

        return parsed;
    }

    // =========================================================================
    // DISTINCT
    // =========================================================================

    /**
     * Detects whether the plan implements SELECT DISTINCT.
     *
     * Postgres may use:
     *   - HashAggregate with Strategy "Hashed" and no "Group Key"  (hash-based DISTINCT)
     *   - Unique node sitting on top of a Sort node                (sort-based DISTINCT)
     *
     * Note: HashAggregate with a Group Key represents GROUP BY, not DISTINCT.
     */
    public parseDistinct(root: QueryPlanNode): { distinct: boolean; strategy?: 'hash' | 'sort' } {
        const hashDistinctNode = this.findNode(
            root,
            n =>
                n['Node Type'] === 'Aggregate' &&
                n['Strategy'] === 'Hashed' &&
                (!n['Group Key'] || n['Group Key'].length === 0)
        );
        if (hashDistinctNode) {
            return { distinct: true, strategy: 'hash' };
        }

        const sortDistinctNode = this.findNode(root, n => n['Node Type'] === 'Unique');
        if (sortDistinctNode) {
            return { distinct: true, strategy: 'sort' };
        }

        return { distinct: false };
    }

    // =========================================================================
    // Subqueries (InitPlan / SubPlan)
    // =========================================================================

    /**
     * Collects all child plan nodes whose Parent Relationship is "InitPlan" or
     * "SubPlan" and recursively parses each into a ParsedSubplan.
     *
     * Depth is capped at MAX_SUBPLAN_DEPTH to prevent infinite recursion on
     * pathological inputs.
     */
    private static readonly MAX_SUBPLAN_DEPTH = 3;

    public extractSubplans(
        root: QueryPlanNode,
        aliasMap: Record<string, string>,
        depth = 0
    ): ParsedSubplan[] {
        if (depth >= ExecutionPlanParser.MAX_SUBPLAN_DEPTH) return [];

        const results: ParsedSubplan[] = [];
        const children = root['Plans'] ?? [];

        for (const child of children) {
            const rel = child['Parent Relationship'];
            if (rel === 'InitPlan' || rel === 'SubPlan') {
                results.push({
                    type:     rel,
                    name:     child['Subplan Name'],
                    planNode: child,
                    plan:     this.parseNode(child, aliasMap),
                });
                // Do NOT recurse into the subplan's own children here — parseNode
                // handles that internally via its own extractSubplans call.
            } else {
                // Recurse into non-subplan children to find deeper subplans
                results.push(...this.extractSubplans(child, aliasMap, depth + 1));
            }
        }

        return results;
    }

    // =========================================================================
    // CTEs
    // =========================================================================

    /**
     * Collects the CTE Name from every CTE Scan node in the plan tree.
     * Returns an array of CTE names in the order they are first encountered
     * (typically depth-first).
     */
    public extractCTEs(root: QueryPlanNode): string[] {
        const names: string[] = [];
        this.walkNodes(root, node => {
            if (node['Node Type'] === 'CTE Scan' && node['CTE Name']) {
                names.push(node['CTE Name']);
            }
        });
        return names;
    }

    // =========================================================================
    // LIMIT
    // =========================================================================

    /**
     * Returns true when a Limit node appears anywhere in the plan tree.
     */
    public extractLimit(root: QueryPlanNode): boolean {
        return this.findNode(root, n => n['Node Type'] === 'Limit') !== null;
    }

    // =========================================================================
    // Window functions
    // =========================================================================

    /**
     * Extracts PARTITION BY and ORDER BY information from the first WindowAgg
     * node found in the plan tree.
     *
     * PostgreSQL stores:
     *   "Part Key"  — the PARTITION BY column expressions
     *   "Sort Key"  — the ORDER BY column expressions within the window
     */
    public extractWindowAgg(root: QueryPlanNode): {
        partitionKey?: string[];
        orderKey?: string[];
    } {
        const winNode = this.findNode(root, n => n['Node Type'] === 'WindowAgg');
        if (!winNode) return {};
        return {
            partitionKey: winNode['Part Key'],
            orderKey:     winNode['Sort Key'],
        };
    }

    // =========================================================================
    // Existing join / from statement parser (unchanged)
    // =========================================================================

    private parseQueryPlanToJoinOrFromStatement(
        planNode: QueryPlanNode,
        aliasMap: Record<string, string>
    ): JoinStatement | undefined {
        const nodeType = planNode['Node Type'];

        if (nodeType === 'Seq Scan' || nodeType === 'Bitmap Heap Scan') {
            const tableName =
                aliasMap[planNode['Alias'] || planNode['Relation Name'] || ''] ||
                planNode['Relation Name'] || '';
            return { tableName };
        }

        if (nodeType === 'Index Scan' || nodeType === 'Index Only Scan') {
            const tableName =
                aliasMap[planNode['Alias'] || planNode['Relation Name'] || ''] ||
                planNode['Relation Name'] || '';
            const condition = planNode['Index Cond'] || '';
            return { tableName, joinCondition: condition };
        }

        if (planNode['Join Type']) {
            const joinType      = planNode['Join Type'];
            const joinCondition = planNode['Hash Cond'] || planNode['Index Cond'] || '';
            const [outerPlan, innerPlan] = planNode['Plans'] || [];

            const outerJoinStatement = outerPlan
                ? this.parseQueryPlanToJoinOrFromStatement(outerPlan, aliasMap)
                : { tableName: '' };
            const innerJoinStatement = innerPlan
                ? this.parseQueryPlanToJoinOrFromStatement(innerPlan, aliasMap)
                : { tableName: '' };

            return outerPlan?.['Plans']
                ? {
                    joinType,
                    tableName: innerJoinStatement?.tableName || '',
                    joinedTable: {
                        tableName:     outerJoinStatement?.tableName || '',
                        joinType:      outerJoinStatement?.joinType,
                        joinedTable:   outerJoinStatement?.joinedTable,
                        joinCondition: outerJoinStatement?.joinCondition,
                    },
                    joinCondition: joinCondition || innerJoinStatement?.joinCondition,
                }
                : {
                    joinType,
                    tableName: outerJoinStatement?.tableName || '',
                    joinedTable: {
                        tableName:     innerJoinStatement?.tableName || '',
                        joinType:      innerJoinStatement?.joinType,
                        joinedTable:   innerJoinStatement?.joinedTable,
                        joinCondition: innerJoinStatement?.joinCondition,
                    },
                    joinCondition: joinCondition || outerJoinStatement?.joinCondition,
                };
        }

        const nestedPlans = planNode['Plans'];
        if (nestedPlans && nestedPlans.length > 0) {
            // Skip subplan children (InitPlan / SubPlan) when looking for the main join tree
            const mainChildren = nestedPlans.filter(
                p => p['Parent Relationship'] !== 'InitPlan' && p['Parent Relationship'] !== 'SubPlan'
            );
            if (mainChildren.length > 0) {
                return this.parseQueryPlanToJoinOrFromStatement(mainChildren[0], aliasMap);
            }
        }

        return undefined;
    }

    // =========================================================================
    // Generic node-tree utilities
    // =========================================================================

    private extractKeyForNodeType(
        plan: QueryPlanNode,
        nodeType: string,
        keyToExtract: QueryPlanKeys
    ): any {
        if (plan['Node Type'] === nodeType) {
            return plan[keyToExtract];
        }
        if (plan.Plans) {
            for (const subPlan of plan.Plans) {
                const result = this.extractKeyForNodeType(subPlan, nodeType, keyToExtract);
                if (result !== undefined) return result;
            }
        }
        return undefined;
    }

    private extractAllKeysForNodeType(
        plan: QueryPlanNode,
        nodeType: string[],
        keysToExtract: QueryPlanKeys[],
        results: any[] = []
    ): any[] {
        keysToExtract.forEach((keyToExtract) => {
            if (plan['Node Type'] && nodeType.includes(plan['Node Type'])) {
                if (plan[keyToExtract] !== undefined) {
                    results.push(plan[keyToExtract]);
                }
            }
            if (plan.Plans) {
                for (const subPlan of plan.Plans) {
                    this.extractAllKeysForNodeType(subPlan, nodeType, [keyToExtract], results);
                }
            }
        });
        return results;
    }

    /**
     * Returns the first node in a depth-first walk for which `predicate` returns
     * true, or null if no such node exists.
     */
    private findNode(
        node: QueryPlanNode,
        predicate: (n: QueryPlanNode) => boolean
    ): QueryPlanNode | null {
        if (predicate(node)) return node;
        for (const child of node['Plans'] ?? []) {
            const found = this.findNode(child, predicate);
            if (found) return found;
        }
        return null;
    }

    /**
     * Visits every node in the plan tree depth-first, calling `visitor` for each.
     */
    private walkNodes(node: QueryPlanNode, visitor: (n: QueryPlanNode) => void): void {
        visitor(node);
        for (const child of node['Plans'] ?? []) {
            this.walkNodes(child, visitor);
        }
    }
}
