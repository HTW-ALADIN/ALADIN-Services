import { DataSource } from 'typeorm';
import { AST, Parser } from 'node-sql-parser';
import { ComparisonResult } from '../shared/interfaces/index';
import { ResultSetComparator } from './result-set-comparator';
import { ASTComparator } from './comparators/ast-comparator';
import { ExecutionPlanComparator } from './comparators/execution-plan-comparator';
import { FeedbackAssembler } from './feedback/feedback-assembler';
import { GradeCalculator } from './grading/grade-calculator';

/**
 * Orchestrates all comparison strategies to produce a single ComparisonResult.
 *
 * Pipeline:
 *  1. Executability check        — ResultSetComparator.isExecutable()
 *  2. Result-set comparison      — ResultSetComparator.compare()
 *  3. AST parsing & validation   — node-sql-parser + ASTComparator.compare()
 *  4. Execution-plan comparison  — ExecutionPlanComparator.compare()   (skipped for unsupported queries)
 *  5. Grading                    — GradeCalculator.calculate()
 *  6. Feedback assembly          — FeedbackAssembler.build()
 */
export class SQLQueryGradingService {

    private static readonly FULL_GRADE = 7;
    private readonly parser = new Parser();

    constructor(
        private readonly resultSetComparator:    ResultSetComparator,
        private readonly astComparator:          ASTComparator,
        private readonly executionPlanComparator: ExecutionPlanComparator,
        private readonly gradeCalculator:        GradeCalculator,
        private readonly feedbackAssembler:      FeedbackAssembler
    ) {}

    public async gradeQuery(
        referenceQuery: string,
        studentQuery:   string,
        dataSource:     DataSource,
        databaseKey:    string
    ): Promise<ComparisonResult> {
        studentQuery   = this.removeSemicolon(studentQuery);
        referenceQuery = this.removeSemicolon(referenceQuery);

        // ── 1. Executability ─────────────────────────────────────────────────

        const [executable, execFeedback] =
            await this.resultSetComparator.isExecutable(studentQuery, dataSource);

        if (!executable) {
            return {
                grade: 0,
                feedback: execFeedback,
                feedbackWithSolution: [],
                equivalent: false,
                supportedQueryType: false,
            };
        }

        // ── 2. Result-set comparison ─────────────────────────────────────────

        const [resultSetMatch, rsFeedback] =
            await this.resultSetComparator.compare(referenceQuery, studentQuery, dataSource);

        // ── 3. AST parsing & validation ──────────────────────────────────────

        let studentAST   = this.parser.astify(studentQuery,   { database: 'postgresql' });
        let referenceAST = this.parser.astify(referenceQuery, { database: 'postgresql' });

        // Multi-statement input
        if (Array.isArray(studentAST) || Array.isArray(referenceAST)) {
            const grade = resultSetMatch ? SQLQueryGradingService.FULL_GRADE : 0;
            return {
                grade,
                feedback:             [...execFeedback, ...rsFeedback, 'AST array not supported.'],
                feedbackWithSolution: [],
                equivalent:           grade === SQLQueryGradingService.FULL_GRADE,
                supportedQueryType:   false,
            };
        }

        if (!studentAST || !referenceAST) {
            const grade = resultSetMatch ? SQLQueryGradingService.FULL_GRADE : 0;
            return {
                grade,
                feedback:             [...execFeedback, ...rsFeedback, 'AST parsing failed.'],
                feedbackWithSolution: [],
                equivalent:           grade === SQLQueryGradingService.FULL_GRADE,
                supportedQueryType:   false,
            };
        }

        studentAST   = studentAST   as AST;
        referenceAST = referenceAST as AST;

        // Wrong statement type
        if (studentAST.type !== referenceAST.type) {
            const grade = resultSetMatch ? SQLQueryGradingService.FULL_GRADE : 0;
            return {
                grade,
                feedback: [
                    ...execFeedback,
                    ...rsFeedback,
                    `Incorrect SQL clause, the task requires a clause of type: ${referenceAST.type}`,
                ],
                feedbackWithSolution: [],
                equivalent:         grade === SQLQueryGradingService.FULL_GRADE,
                supportedQueryType: false,
            };
        }

        // ── 4. AST structural comparison ─────────────────────────────────────

        const astResult = this.astComparator.compare(studentAST, referenceAST);

        // Unsupported structure: FROM-clause derived-table subqueries only.
        // DISTINCT, WHERE/HAVING subqueries, CTEs, LIMIT and window functions
        // are now handled by the execution-plan comparator.
        if (!astResult.supported) {
            const grade = resultSetMatch ? SQLQueryGradingService.FULL_GRADE : 0;
            const { feedback, feedbackWithSolution } = this.feedbackAssembler.build(
                resultSetMatch, astResult, null
            );
            return {
                grade,
                feedback:           [...execFeedback, ...rsFeedback, ...feedback],
                feedbackWithSolution,
                equivalent:         grade === SQLQueryGradingService.FULL_GRADE,
                supportedQueryType: false,
            };
        }

        // ── 5. Execution-plan comparison ─────────────────────────────────────

        const planResult = await this.executionPlanComparator.compare(
            studentAST,
            referenceAST,
            astResult.studentAliasMap,
            astResult.referenceAliasMap,
            dataSource,
            studentQuery,
            referenceQuery
        );

        // ── 6. Grading ───────────────────────────────────────────────────────

        const grade = this.gradeCalculator.calculate({
            fullGrade:        SQLQueryGradingService.FULL_GRADE,
            resultSetMatch,
            columnsMatch:     astResult.columnsMatch,
            planPenaltyPoints: planResult.penaltyPoints,
        });

        // ── 7. Feedback assembly ─────────────────────────────────────────────

        const { feedback, feedbackWithSolution } = this.feedbackAssembler.build(
            resultSetMatch, astResult, planResult
        );

        return {
            grade,
            feedback:           [...execFeedback, ...rsFeedback, ...feedback],
            feedbackWithSolution,
            equivalent:         grade === SQLQueryGradingService.FULL_GRADE,
            supportedQueryType: true,
        };
    }

    private removeSemicolon(str: string): string {
        return str.endsWith(';') ? str.slice(0, -1) : str;
    }
}
