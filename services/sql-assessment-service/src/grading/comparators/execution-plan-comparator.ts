import { DataSource } from 'typeorm';
import { AST, Join } from 'node-sql-parser';
import { IParsedExecutionPlan, ParsedSubplan } from '../../shared/interfaces/execution-plan';
import { ExecutionPlanParser } from '../execution-plan-parser';
import { JoinComparator } from '../join-comparator';
import { AssembledFeedback, ExecutionPlanFeedback, SubplanFeedback } from '../../shared/interfaces/feedback';

// ---------------------------------------------------------------------------
// Result types
// ---------------------------------------------------------------------------

export interface ExecutionPlanComparisonResult {
    /**
     * True when all compared plan elements match (GROUP BY, HAVING, ORDER BY,
     * WHERE, JOIN, DISTINCT, subplans, CTEs, LIMIT, window functions).
     */
    plansMatch: boolean;
    executionPlan: ExecutionPlanFeedback;
    /** Number of grade points to deduct (one per differing plan element). */
    penaltyPoints: number;
}

// ---------------------------------------------------------------------------
// ExecutionPlanComparator
// ---------------------------------------------------------------------------

/**
 * Compares two SQL queries at the execution-plan level.
 *
 * Supported constructs:
 *  - GROUP BY / HAVING / ORDER BY / WHERE   (pre-existing)
 *  - JOIN                                   (pre-existing)
 *  - SELECT DISTINCT                        (new)
 *  - Subqueries (InitPlan / SubPlan)         (new, recursive up to MAX_RECURSION_DEPTH)
 *  - CTEs (WITH … AS …)                    (new)
 *  - LIMIT                                  (new, presence check)
 *  - Window functions (OVER)               (new)
 */
export class ExecutionPlanComparator {

    /** Maximum depth for recursive subplan comparison. */
    private static readonly MAX_RECURSION_DEPTH = 3;

    constructor(
        private readonly executionPlanParser: ExecutionPlanParser,
        private readonly joinComparator: JoinComparator
    ) {}

    /**
     * Fetches and compares the execution plans of two SQL queries.
     */
    public async compare(
        studentAST: AST,
        referenceAST: AST,
        studentAliasMap: Record<string, string>,
        referenceAliasMap: Record<string, string>,
        dataSource: DataSource,
        studentQuery: string,
        referenceQuery: string
    ): Promise<ExecutionPlanComparisonResult> {
        const executionPlan: ExecutionPlanFeedback = {};

        const queryRunner = dataSource.createQueryRunner();
        let studentRawPlan: any;
        let referenceRawPlan: any;

        try {
            studentRawPlan   = await queryRunner.query(`EXPLAIN (FORMAT JSON) ${studentQuery}`);
            referenceRawPlan = await queryRunner.query(`EXPLAIN (FORMAT JSON) ${referenceQuery}`);
        } finally {
            await queryRunner.release();
        }

        if (!studentRawPlan || !referenceRawPlan) {
            executionPlan.planRetrieval = { message: 'Unable to retrieve execution plans.' };
            return { plansMatch: false, executionPlan, penaltyPoints: 0 };
        }

        const parsedStudent   = this.executionPlanParser.parse(studentRawPlan[0],   studentAliasMap);
        const parsedReference = this.executionPlanParser.parse(referenceRawPlan[0], referenceAliasMap);

        if (!parsedStudent || !parsedReference) {
            throw new Error('Unable to parse execution plans.');
        }

        const penaltyPoints = this.diffPlans(
            parsedStudent,
            parsedReference,
            studentAST,
            referenceAST,
            studentAliasMap,
            referenceAliasMap,
            executionPlan
        );

        return {
            plansMatch: penaltyPoints === 0,
            executionPlan,
            penaltyPoints,
        };
    }

    // =========================================================================
    // Core plan diff
    // =========================================================================

    /**
     * Diffs all plan elements and writes results into `target`.
     * Returns the total penalty points for this level.
     *
     * @param target  - The object to write feedback entries into (either the
     *   top-level executionPlan block or a SubplanFeedback entry).
     * @param depth   - Current recursion depth; diffing stops at MAX_RECURSION_DEPTH.
     */
    private diffPlans(
        studentPlan: IParsedExecutionPlan,
        referencePlan: IParsedExecutionPlan,
        studentAST: any,
        referenceAST: any,
        studentAliasMap: Record<string, string>,
        referenceAliasMap: Record<string, string>,
        target: ExecutionPlanFeedback | SubplanFeedback,
        depth = 0
    ): number {
        let penaltyPoints = 0;

        // ── GROUP BY ─────────────────────────────────────────────────────────
        if (!this.compareArrays(studentPlan.groupKey, referencePlan.groupKey, studentAliasMap, referenceAliasMap)) {
            target.groupKey = {
                message:  'Incorrect Group key.',
                solution: `Expected ${referencePlan.groupKey}, got ${studentPlan.groupKey}.`,
            };
            penaltyPoints++;
        }

        // ── HAVING ───────────────────────────────────────────────────────────
        if (
            this.joinComparator.normalizeFilter(studentPlan.havingFilter,   studentAliasMap) !==
            this.joinComparator.normalizeFilter(referencePlan.havingFilter, referenceAliasMap)
        ) {
            target.having = {
                message:  'Incorrect Having filter.',
                solution: `Expected ${referencePlan.havingFilter}, got ${studentPlan.havingFilter}.`,
            };
            penaltyPoints++;
        }

        // ── ORDER BY ─────────────────────────────────────────────────────────
        if (!this.compareArrays(studentPlan.sortKey, referencePlan.sortKey, studentAliasMap, referenceAliasMap)) {
            target.orderBy = {
                message:  'Incorrect Order By sort key.',
                solution: `Expected ${referencePlan.sortKey}, got ${studentPlan.sortKey}.`,
            };
            penaltyPoints++;
        }

        // ── WHERE ────────────────────────────────────────────────────────────
        if (!this.compareArrays(studentPlan.whereFilter, referencePlan.whereFilter, studentAliasMap, referenceAliasMap)) {
            target.where = {
                message:  'Incorrect Where filter.',
                solution: `Expected ${referencePlan.whereFilter}, got ${studentPlan.whereFilter}.`,
            };
            penaltyPoints++;
        }

        // ── JOIN ─────────────────────────────────────────────────────────────
        if (studentPlan.joinStatement && referencePlan.joinStatement) {
            const joinStatementsEqual = this.joinComparator.compareJoinStatements(
                studentPlan.joinStatement,
                referencePlan.joinStatement,
                studentAliasMap,
                referenceAliasMap
            );
            if (!joinStatementsEqual) {
                const [joinEqual, joinEntry] = this.joinComparator.compareJoinAST(
                    referenceAST.from as Join[],
                    studentAST.from  as Join[],
                    studentAliasMap,
                    referenceAliasMap
                );
                if (joinEntry) target.join = joinEntry;
                if (!joinEqual) penaltyPoints++;
            }
        } else if (studentPlan.joinStatement && !referencePlan.joinStatement) {
            target.join = { message: 'Incorrect inclusion of Join statement.' };
        } else if (referencePlan.joinStatement && !studentPlan.joinStatement) {
            target.join = { message: 'Join statement missing.' };
        }

        // ── DISTINCT ─────────────────────────────────────────────────────────
        const studentDistinct   = studentPlan.distinct   ?? false;
        const referenceDistinct = referencePlan.distinct ?? false;

        if (studentDistinct !== referenceDistinct) {
            if (referenceDistinct) {
                target.distinct = {
                    message:  'DISTINCT keyword is missing from the query.',
                    solution: 'The query should use SELECT DISTINCT.',
                };
            } else {
                target.distinct = {
                    message:  'DISTINCT keyword should not be used in this query.',
                    solution: 'The query should use plain SELECT without DISTINCT.',
                };
            }
            penaltyPoints++;
        } else if (
            studentDistinct &&
            referenceDistinct &&
            studentPlan.distinctStrategy !== referencePlan.distinctStrategy
        ) {
            // Same presence but different strategy — informational only, no penalty
            target.distinctStrategy = {
                message: `Note: different DISTINCT implementation strategy ` +
                    `(student: ${studentPlan.distinctStrategy ?? 'unknown'}, ` +
                    `reference: ${referencePlan.distinctStrategy ?? 'unknown'}).`,
            };
        }

        // ── CTEs ─────────────────────────────────────────────────────────────
        const studentCTEs   = [...(studentPlan.cteNames   ?? [])].sort();
        const referenceCTEs = [...(referencePlan.cteNames ?? [])].sort();

        if (JSON.stringify(studentCTEs) !== JSON.stringify(referenceCTEs)) {
            target.cte = {
                message:  'Incorrect CTE usage.',
                solution: `Expected CTEs: [${referenceCTEs.join(', ') || 'none'}], ` +
                    `got: [${studentCTEs.join(', ') || 'none'}].`,
            };
            penaltyPoints++;
        }

        // ── LIMIT (presence) ─────────────────────────────────────────────────
        // Value comparison is done by ASTComparator.compareLimitOffset(); here
        // we only check that the student includes / omits a Limit node when
        // the reference does the same.
        const studentHasLimit   = studentPlan.hasLimit   ?? false;
        const referenceHasLimit = referencePlan.hasLimit ?? false;

        if (studentHasLimit !== referenceHasLimit) {
            if (referenceHasLimit) {
                target.limit = {
                    message:  'LIMIT clause is missing.',
                    solution: 'The query should include a LIMIT clause.',
                };
            } else {
                target.limit = {
                    message:  'LIMIT clause should not be present in this query.',
                    solution: 'Remove the LIMIT clause from the query.',
                };
            }
            penaltyPoints++;
        }

        // ── Window functions ─────────────────────────────────────────────────
        const hasStudentWindow   = (studentPlan.windowPartitionKey   ?? studentPlan.windowOrderKey)   !== undefined;
        const hasReferenceWindow = (referencePlan.windowPartitionKey ?? referencePlan.windowOrderKey) !== undefined;

        if (hasStudentWindow !== hasReferenceWindow) {
            if (hasReferenceWindow) {
                target.window = {
                    message:  'Window function (OVER) is missing.',
                    solution: 'The query should use a window function with OVER.',
                };
            } else {
                target.window = {
                    message: 'Window function (OVER) should not be used in this query.',
                };
            }
            penaltyPoints++;
        } else if (hasStudentWindow && hasReferenceWindow) {
            if (
                !this.compareArrays(
                    studentPlan.windowPartitionKey,
                    referencePlan.windowPartitionKey,
                    studentAliasMap,
                    referenceAliasMap
                )
            ) {
                target.windowPartition = {
                    message:  'Incorrect PARTITION BY in window function.',
                    solution: `Expected PARTITION BY: [${(referencePlan.windowPartitionKey ?? []).join(', ')}], ` +
                        `got: [${(studentPlan.windowPartitionKey ?? []).join(', ')}].`,
                };
                penaltyPoints++;
            }

            if (
                !this.compareArrays(
                    studentPlan.windowOrderKey,
                    referencePlan.windowOrderKey,
                    studentAliasMap,
                    referenceAliasMap
                )
            ) {
                target.windowOrderBy = {
                    message:  'Incorrect ORDER BY in window function.',
                    solution: `Expected window ORDER BY: [${(referencePlan.windowOrderKey ?? []).join(', ')}], ` +
                        `got: [${(studentPlan.windowOrderKey ?? []).join(', ')}].`,
                };
                penaltyPoints++;
            }
        }

        // ── Subplans (recursive) ─────────────────────────────────────────────
        if (depth < ExecutionPlanComparator.MAX_RECURSION_DEPTH) {
            // Only top-level executionPlan block carries subplans
            const topLevelTarget = target as ExecutionPlanFeedback;
            penaltyPoints += this.diffSubplans(
                studentPlan.subplans  ?? [],
                referencePlan.subplans ?? [],
                studentAST,
                referenceAST,
                studentAliasMap,
                referenceAliasMap,
                topLevelTarget,
                depth
            );
        }

        return penaltyPoints;
    }

    // =========================================================================
    // Subplan diffing (recursive)
    // =========================================================================

    private diffSubplans(
        studentSubplans: ParsedSubplan[],
        referenceSubplans: ParsedSubplan[],
        studentAST: any,
        referenceAST: any,
        studentAliasMap: Record<string, string>,
        referenceAliasMap: Record<string, string>,
        topLevelTarget: ExecutionPlanFeedback,
        depth: number
    ): number {
        let penaltyPoints = 0;

        if (studentSubplans.length !== referenceSubplans.length) {
            topLevelTarget!.subqueryCount = {
                message:  `Incorrect number of subqueries: expected ${referenceSubplans.length}, got ${studentSubplans.length}.`,
                solution: `The query should contain exactly ${referenceSubplans.length} subquer` +
                    `${referenceSubplans.length === 1 ? 'y' : 'ies'}.`,
            };
            penaltyPoints++;
            return penaltyPoints;
        }

        for (let i = 0; i < referenceSubplans.length; i++) {
            const refSubplan = referenceSubplans[i];
            const stuSubplan = studentSubplans[i];
            const subContext = refSubplan.name ?? `Subquery ${i + 1}`;

            // Initialise the subplan bucket
            if (!topLevelTarget!.subplans) topLevelTarget!.subplans = {};
            const subTarget: SubplanFeedback = {};
            topLevelTarget!.subplans[subContext] = subTarget;

            // Check subplan type (InitPlan vs SubPlan)
            if (stuSubplan.type !== refSubplan.type) {
                subTarget.type = {
                    message: `In ${subContext}: expected a ${refSubplan.type}, got a ${stuSubplan.type}.`,
                };
                penaltyPoints++;
                continue;
            }

            // Recursively diff the subplan's own plan tree
            penaltyPoints += this.diffPlans(
                stuSubplan.plan,
                refSubplan.plan,
                studentAST,
                referenceAST,
                studentAliasMap,
                referenceAliasMap,
                subTarget,
                depth + 1
            );

            // Remove empty subplan entries (no issues found)
            if (Object.keys(subTarget).length === 0) {
                delete topLevelTarget!.subplans[subContext];
            }
        }

        // Remove the subplans key entirely if it ended up empty
        if (topLevelTarget!.subplans && Object.keys(topLevelTarget!.subplans).length === 0) {
            delete topLevelTarget!.subplans;
        }

        return penaltyPoints;
    }

    // =========================================================================
    // Utilities
    // =========================================================================

    private compareArrays(
        studentArray:   string[] = [],
        referenceArray: string[] = [],
        studentAliasMap?:   Record<string, string>,
        referenceAliasMap?: Record<string, string>
    ): boolean {
        if (studentArray.length !== referenceArray.length) return false;

        const normalizedStudent   = studentArray.map(
            g => this.joinComparator.normalizeFilter(g, studentAliasMap)
        );
        const normalizedReference = referenceArray.map(
            g => this.joinComparator.normalizeFilter(g, referenceAliasMap)
        );

        return [...normalizedStudent].sort().every(
            (val, i) => val === [...normalizedReference].sort()[i]
        );
    }
}
