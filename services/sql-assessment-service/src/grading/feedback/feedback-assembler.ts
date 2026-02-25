import { ASTComparisonResult } from '../comparators/ast-comparator';
import { ExecutionPlanComparisonResult } from '../comparators/execution-plan-comparator';

export interface AssembledFeedback {
    feedback: string[];
    feedbackWithSolution: string[];
}

/**
 * Assembles the final user-facing feedback arrays from the individual comparison
 * results produced by ResultSetComparator, ASTComparator, and
 * ExecutionPlanComparator.
 *
 * This is a pure, stateless helper — it holds no shared state and performs no
 * I/O.  It can be tested in isolation without any database setup.
 */
export class FeedbackAssembler {

    /**
     * Builds the combined feedback and feedbackWithSolution arrays from all
     * three comparison stages.
     *
     * @param resultSetMatch  - Whether the two queries return the same rows.
     * @param astResult       - Output from ASTComparator.compare().
     * @param planResult      - Output from ExecutionPlanComparator.compare().
     *                          Pass null when the AST comparison determined that
     *                          the query structure is unsupported (execution-plan
     *                          comparison is skipped in that case).
     */
    public build(
        resultSetMatch: boolean,
        astResult: ASTComparisonResult,
        planResult: ExecutionPlanComparisonResult | null
    ): AssembledFeedback {
        const feedback: string[] = [];
        const feedbackWithSolution: string[] = [];

        // ── Result-set verdict ────────────────────────────────────────────────
        feedback.push(resultSetMatch ? 'Same result set of both queries.' : 'Result sets differ.');

        // ── AST-level feedback ────────────────────────────────────────────────
        feedback.push(...astResult.feedback);
        feedbackWithSolution.push(...astResult.feedbackWithSolution);

        // ── Execution-plan feedback (only when structure is supported) ────────
        if (planResult) {
            feedback.push(...planResult.feedback);
            feedbackWithSolution.push(...planResult.feedbackWithSolution);
        }

        return { feedback, feedbackWithSolution };
    }
}
