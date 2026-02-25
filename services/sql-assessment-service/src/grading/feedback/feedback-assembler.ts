import { ASTComparisonResult } from '../comparators/ast-comparator';
import { ExecutionPlanComparisonResult } from '../comparators/execution-plan-comparator';
import { AssembledFeedback } from '../../shared/interfaces/feedback';
import { t, SupportedLanguage } from '../../shared/i18n';

export type { AssembledFeedback };

/**
 * Assembles the final user-facing feedback object from the individual comparison
 * results produced by ResultSetComparator, ASTComparator, and
 * ExecutionPlanComparator.
 *
 * This is a pure, stateless helper — it holds no shared state and performs no
 * I/O.  It can be tested in isolation without any database setup.
 */
export class FeedbackAssembler {

    /**
     * Builds the combined AssembledFeedback object from all three comparison
     * stages.
     *
     * @param resultSetMatch  - Whether the two queries return the same rows.
     * @param astResult       - Output from ASTComparator.compare().
     * @param planResult      - Output from ExecutionPlanComparator.compare().
     *                          Pass null when the AST comparison determined that
     *                          the query structure is unsupported (execution-plan
     *                          comparison is skipped in that case).
     * @param lang            - Language for user-facing messages (default: 'en').
     */
    public build(
        resultSetMatch: boolean,
        astResult: ASTComparisonResult,
        planResult: ExecutionPlanComparisonResult | null,
        lang: SupportedLanguage = 'en'
    ): AssembledFeedback {
        const assembled: AssembledFeedback = {};

        // ── Result-set verdict ────────────────────────────────────────────────
        assembled.resultSet = {
            verdict: {
                message: resultSetMatch
                    ? t('FEEDBACK_RESULT_SET_MATCH', lang)
                    : t('FEEDBACK_RESULT_SET_MISMATCH', lang),
            },
        };

        // ── AST-level feedback ────────────────────────────────────────────────
        if (astResult.ast && Object.keys(astResult.ast).length > 0) {
            assembled.ast = astResult.ast;
        }

        // ── Execution-plan feedback (only when structure is supported) ────────
        if (planResult) {
            const ep = planResult.executionPlan;
            if (ep && Object.keys(ep).length > 0) {
                assembled.executionPlan = ep;
            }
        }

        return assembled;
    }
}
