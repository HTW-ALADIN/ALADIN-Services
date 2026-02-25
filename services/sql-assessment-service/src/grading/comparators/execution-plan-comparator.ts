import { DataSource } from 'typeorm';
import { AST, Join } from 'node-sql-parser';
import { IParsedExecutionPlan, ParsedSubplan } from '../../shared/interfaces/execution-plan';
import { ExecutionPlanParser } from '../execution-plan-parser';
import { JoinComparator } from '../join-comparator';

// ---------------------------------------------------------------------------
// Result types
// ---------------------------------------------------------------------------

export interface ExecutionPlanComparisonResult {
    /**
     * True when all compared plan elements match (GROUP BY, HAVING, ORDER BY,
     * WHERE, JOIN, DISTINCT, subplans, CTEs, LIMIT, window functions).
     */
    plansMatch: boolean;
    feedback: string[];
    feedbackWithSolution: string[];
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
        const feedback: string[] = [];
        const feedbackWithSolution: string[] = [];

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
            feedback.push('Unable to retrieve execution plans.');
            return { plansMatch: false, feedback, feedbackWithSolution, penaltyPoints: 0 };
        }

        const parsedStudent   = this.executionPlanParser.parse(studentRawPlan[0],   studentAliasMap);
        const parsedReference = this.executionPlanParser.parse(referenceRawPlan[0], referenceAliasMap);

        if (!parsedStudent || !parsedReference) {
            throw new Error('Unable to parse execution plans.');
        }

        const [planFeedback, planFeedbackWithSolution, penaltyPoints] = this.diffPlans(
            parsedStudent,
            parsedReference,
            studentAST,
            referenceAST,
            studentAliasMap,
            referenceAliasMap
        );

        feedback.push(...planFeedback);
        feedbackWithSolution.push(...planFeedbackWithSolution);

        return {
            plansMatch: penaltyPoints === 0,
            feedback,
            feedbackWithSolution,
            penaltyPoints,
        };
    }

    // =========================================================================
    // Core plan diff
    // =========================================================================

    /**
     * Diffs all plan elements and returns [feedback, feedbackWithSolution, penaltyPoints].
     *
     * @param context - Optional prefix label for feedback messages, used when
     *   this method is called recursively for subplans (e.g. "In subquery 'InitPlan 1': ").
     */
    private diffPlans(
        studentPlan: IParsedExecutionPlan,
        referencePlan: IParsedExecutionPlan,
        studentAST: any,
        referenceAST: any,
        studentAliasMap: Record<string, string>,
        referenceAliasMap: Record<string, string>,
        context = '',
        depth = 0
    ): [string[], string[], number] {
        const feedback: string[] = [];
        const feedbackWithSolution: string[] = [];
        let penaltyPoints = 0;

        const prefix = context ? `${context}: ` : '';

        // ── GROUP BY ─────────────────────────────────────────────────────────
        if (!this.compareArrays(studentPlan.groupKey, referencePlan.groupKey, studentAliasMap, referenceAliasMap)) {
            feedback.push(`${prefix}Incorrect Group key.`);
            feedbackWithSolution.push(`${prefix}Expected ${referencePlan.groupKey}, got ${studentPlan.groupKey}.`);
            penaltyPoints++;
        }

        // ── HAVING ───────────────────────────────────────────────────────────
        if (
            this.joinComparator.normalizeFilter(studentPlan.havingFilter,   studentAliasMap) !==
            this.joinComparator.normalizeFilter(referencePlan.havingFilter, referenceAliasMap)
        ) {
            feedback.push(`${prefix}Incorrect Having filter.`);
            feedbackWithSolution.push(`${prefix}Expected ${referencePlan.havingFilter}, got ${studentPlan.havingFilter}.`);
            penaltyPoints++;
        }

        // ── ORDER BY ─────────────────────────────────────────────────────────
        if (!this.compareArrays(studentPlan.sortKey, referencePlan.sortKey, studentAliasMap, referenceAliasMap)) {
            feedback.push(`${prefix}Incorrect Order By sort key.`);
            feedbackWithSolution.push(`${prefix}Expected ${referencePlan.sortKey}, got ${studentPlan.sortKey}.`);
            penaltyPoints++;
        }

        // ── WHERE ────────────────────────────────────────────────────────────
        if (!this.compareArrays(studentPlan.whereFilter, referencePlan.whereFilter, studentAliasMap, referenceAliasMap)) {
            feedback.push(`${prefix}Incorrect Where filter.`);
            feedbackWithSolution.push(`${prefix}Expected ${referencePlan.whereFilter}, got ${studentPlan.whereFilter}.`);
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
                const [joinEqual, feedbackJoin, solution] = this.joinComparator.compareJoinAST(
                    referenceAST.from as Join[],
                    studentAST.from  as Join[],
                    studentAliasMap,
                    referenceAliasMap
                );
                feedback.push(...feedbackJoin.map(m => `${prefix}${m}`));
                feedbackWithSolution.push(...solution.map(m => `${prefix}${m}`));
                if (!joinEqual) penaltyPoints++;
            }
        } else if (studentPlan.joinStatement && !referencePlan.joinStatement) {
            feedback.push(`${prefix}Incorrect inclusion of Join statement.`);
        } else if (referencePlan.joinStatement && !studentPlan.joinStatement) {
            feedback.push(`${prefix}Join statement missing.`);
        }

        // ── DISTINCT ─────────────────────────────────────────────────────────
        const studentDistinct   = studentPlan.distinct   ?? false;
        const referenceDistinct = referencePlan.distinct ?? false;

        if (studentDistinct !== referenceDistinct) {
            if (referenceDistinct) {
                feedback.push(`${prefix}DISTINCT keyword is missing from the query.`);
                feedbackWithSolution.push(`${prefix}The query should use SELECT DISTINCT.`);
            } else {
                feedback.push(`${prefix}DISTINCT keyword should not be used in this query.`);
                feedbackWithSolution.push(`${prefix}The query should use plain SELECT without DISTINCT.`);
            }
            penaltyPoints++;
        } else if (
            studentDistinct &&
            referenceDistinct &&
            studentPlan.distinctStrategy !== referencePlan.distinctStrategy
        ) {
            // Same presence but different strategy — informational only, no penalty
            feedback.push(
                `${prefix}Note: different DISTINCT implementation strategy ` +
                `(student: ${studentPlan.distinctStrategy ?? 'unknown'}, ` +
                `reference: ${referencePlan.distinctStrategy ?? 'unknown'}).`
            );
        }

        // ── CTEs ─────────────────────────────────────────────────────────────
        const studentCTEs   = [...(studentPlan.cteNames   ?? [])].sort();
        const referenceCTEs = [...(referencePlan.cteNames ?? [])].sort();

        if (JSON.stringify(studentCTEs) !== JSON.stringify(referenceCTEs)) {
            feedback.push(`${prefix}Incorrect CTE usage.`);
            feedbackWithSolution.push(
                `${prefix}Expected CTEs: [${referenceCTEs.join(', ') || 'none'}], ` +
                `got: [${studentCTEs.join(', ') || 'none'}].`
            );
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
                feedback.push(`${prefix}LIMIT clause is missing.`);
                feedbackWithSolution.push(`${prefix}The query should include a LIMIT clause.`);
            } else {
                feedback.push(`${prefix}LIMIT clause should not be present in this query.`);
                feedbackWithSolution.push(`${prefix}Remove the LIMIT clause from the query.`);
            }
            penaltyPoints++;
        }

        // ── Window functions ─────────────────────────────────────────────────
        const hasStudentWindow   = (studentPlan.windowPartitionKey   ?? studentPlan.windowOrderKey)   !== undefined;
        const hasReferenceWindow = (referencePlan.windowPartitionKey ?? referencePlan.windowOrderKey) !== undefined;

        if (hasStudentWindow !== hasReferenceWindow) {
            if (hasReferenceWindow) {
                feedback.push(`${prefix}Window function (OVER) is missing.`);
                feedbackWithSolution.push(`${prefix}The query should use a window function with OVER.`);
            } else {
                feedback.push(`${prefix}Window function (OVER) should not be used in this query.`);
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
                feedback.push(`${prefix}Incorrect PARTITION BY in window function.`);
                feedbackWithSolution.push(
                    `${prefix}Expected PARTITION BY: [${(referencePlan.windowPartitionKey ?? []).join(', ')}], ` +
                    `got: [${(studentPlan.windowPartitionKey ?? []).join(', ')}].`
                );
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
                feedback.push(`${prefix}Incorrect ORDER BY in window function.`);
                feedbackWithSolution.push(
                    `${prefix}Expected window ORDER BY: [${(referencePlan.windowOrderKey ?? []).join(', ')}], ` +
                    `got: [${(studentPlan.windowOrderKey ?? []).join(', ')}].`
                );
                penaltyPoints++;
            }
        }

        // ── Subplans (recursive) ─────────────────────────────────────────────
        if (depth < ExecutionPlanComparator.MAX_RECURSION_DEPTH) {
            const [subFeedback, subFeedbackWithSolution, subPenalty] = this.diffSubplans(
                studentPlan.subplans  ?? [],
                referencePlan.subplans ?? [],
                studentAST,
                referenceAST,
                studentAliasMap,
                referenceAliasMap,
                depth
            );
            feedback.push(...subFeedback);
            feedbackWithSolution.push(...subFeedbackWithSolution);
            penaltyPoints += subPenalty;
        }

        return [feedback, feedbackWithSolution, penaltyPoints];
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
        depth: number
    ): [string[], string[], number] {
        const feedback: string[] = [];
        const feedbackWithSolution: string[] = [];
        let penaltyPoints = 0;

        if (studentSubplans.length !== referenceSubplans.length) {
            feedback.push(
                `Incorrect number of subqueries: expected ${referenceSubplans.length}, ` +
                `got ${studentSubplans.length}.`
            );
            feedbackWithSolution.push(
                `The query should contain exactly ${referenceSubplans.length} subquer` +
                `${referenceSubplans.length === 1 ? 'y' : 'ies'}.`
            );
            penaltyPoints++;
            return [feedback, feedbackWithSolution, penaltyPoints];
        }

        for (let i = 0; i < referenceSubplans.length; i++) {
            const refSubplan = referenceSubplans[i];
            const stuSubplan = studentSubplans[i];
            const subContext = refSubplan.name ?? `Subquery ${i + 1}`;

            // Check subplan type (InitPlan vs SubPlan)
            if (stuSubplan.type !== refSubplan.type) {
                feedback.push(
                    `In ${subContext}: expected a ${refSubplan.type}, ` +
                    `got a ${stuSubplan.type}.`
                );
                penaltyPoints++;
                continue;
            }

            // Recursively diff the subplan's own plan tree
            const [subFb, subFbSol, subPenalty] = this.diffPlans(
                stuSubplan.plan,
                refSubplan.plan,
                studentAST,
                referenceAST,
                studentAliasMap,
                referenceAliasMap,
                `In ${subContext}`,
                depth + 1
            );
            feedback.push(...subFb);
            feedbackWithSolution.push(...subFbSol);
            penaltyPoints += subPenalty;
        }

        return [feedback, feedbackWithSolution, penaltyPoints];
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
