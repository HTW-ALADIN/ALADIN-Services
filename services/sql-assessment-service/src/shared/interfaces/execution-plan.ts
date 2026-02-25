// ---------------------------------------------------------------------------
// Parsed plan — the normalised structure produced by ExecutionPlanParser
// ---------------------------------------------------------------------------

export interface IParsedExecutionPlan {
    // ── Existing fields ──────────────────────────────────────────────────────
    groupKey?: string[];
    havingFilter?: string;
    sortKey?: string[];
    whereFilter?: string[];
    joinStatement?: JoinStatement;

    // ── DISTINCT ─────────────────────────────────────────────────────────────
    /** Whether the query uses SELECT DISTINCT (HashAggregate / Unique node). */
    distinct?: boolean;
    /**
     * How the planner chose to implement deduplication.
     * 'hash'  = HashAggregate with Strategy "Hashed" (no Group Key = pure DISTINCT)
     * 'sort'  = Unique node sitting on top of a Sort
     */
    distinctStrategy?: 'hash' | 'sort';

    // ── Subqueries ───────────────────────────────────────────────────────────
    /**
     * Scalar/correlated subqueries that appear as InitPlan or SubPlan child
     * nodes in the execution plan.  Each entry carries its own recursively
     * parsed IParsedExecutionPlan so the comparator can diff them.
     */
    subplans?: ParsedSubplan[];

    // ── CTEs ─────────────────────────────────────────────────────────────────
    /** Names of all CTEs scanned by this plan (from CTE Scan nodes). */
    cteNames?: string[];

    // ── LIMIT ────────────────────────────────────────────────────────────────
    /** Whether a Limit node is present at any level of the plan tree. */
    hasLimit?: boolean;

    // ── Window functions ─────────────────────────────────────────────────────
    /** PARTITION BY columns from the first WindowAgg node found. */
    windowPartitionKey?: string[];
    /** ORDER BY columns (Sort Key) from the first WindowAgg node found. */
    windowOrderKey?: string[];
}

/**
 * A single InitPlan or SubPlan child extracted from the execution plan.
 * The plan tree of the subquery is recursively parsed so comparators can
 * diff them using the same diffPlans() pipeline.
 */
export interface ParsedSubplan {
    /** Whether this is evaluated once (InitPlan) or per row (SubPlan). */
    type: 'InitPlan' | 'SubPlan';
    /** The `Subplan Name` label from the plan node, if present (e.g. "InitPlan 1"). */
    name?: string;
    /** The root plan node of this subplan (used for recursive parsing). */
    planNode: QueryPlanNode;
    /** Recursively parsed content of this subplan. */
    plan: IParsedExecutionPlan;
}

// ---------------------------------------------------------------------------
// Raw plan node — the JSON shape produced by PostgreSQL EXPLAIN (FORMAT JSON)
// ---------------------------------------------------------------------------

export interface JoinStatement {
    joinType?: string;
    tableName: string;
    joinedTable?: JoinStatement;
    joinCondition?: string;
}

export interface QueryPlanNode {
    "Node Type"?: string;
    "Strategy"?: string;
    "Partial Mode"?: string;
    "Parallel Aware"?: boolean;
    "Startup Cost"?: number;
    "Total Cost"?: number;
    "Plan Rows"?: number;
    "Plan Width"?: number;
    "Group Key"?: string[];
    "Filter"?: string;
    "Plans"?: QueryPlanNode[];
    "Parent Relationship"?: string;
    "Sort Key"?: string[];
    "Join Type"?: string;
    "Join Filter"?: string;
    "Inner Unique"?: boolean;
    "Hash Cond"?: string;
    "Alias"?: string;
    "Relation Name"?: string;
    "Index Cond"?: string;
    "Recheck Cond"?: string;
    // CTE / subplan
    "CTE Name"?: string;
    "Subplan Name"?: string;
    // Window functions
    "Part Key"?: string[];
}

export type QueryPlanKeys =
    | "Node Type"
    | "Strategy"
    | "Partial Mode"
    | "Parallel Aware"
    | "Startup Cost"
    | "Total Cost"
    | "Plan Rows"
    | "Plan Width"
    | "Group Key"
    | "Filter"
    | "Plans"
    | "Parent Relationship"
    | "Sort Key"
    | "Join Type"
    | "Join Filter"
    | "Inner Unique"
    | "Hash Cond"
    | "Alias"
    | "Relation Name"
    | "Index Cond"
    | "Recheck Cond"
    | "CTE Name"
    | "Subplan Name"
    | "Part Key";

export interface QueryPlan {
    "QUERY PLAN": Plan[];
}

export interface Plan {
    "Plan": QueryPlanNode;
}
