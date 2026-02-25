import { DataSource } from 'typeorm';
import { AST, Parser } from 'node-sql-parser';
import { ComparisonResult } from '../shared/interfaces/index';
import { AssembledFeedback } from '../shared/interfaces/feedback';
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
            const feedbackDetails: AssembledFeedback = {
                general: {
                    executability: {
                        message: execFeedback[0] ?? 'Query is not executable.',
                        solution: execFeedback[1],
                    },
                },
            };
            return {
                grade: 0,
                feedbackDetails,
                equivalent: false,
                supportedQueryType: false,
            };
        }

        // ── 2. Result-set comparison ─────────────────────────────────────────

        const [resultSetMatch, rsFeedback] =
            await this.resultSetComparator.compare(referenceQuery, studentQuery, dataSource);

        // Build a base feedbackDetails that may be extended below
        const buildWithGeneral = (
            generalEntry: AssembledFeedback['general'],
            extra?: Partial<AssembledFeedback>
        ): AssembledFeedback => {
            const fd: AssembledFeedback = {};
            if (rsFeedback.length > 0) {
                fd.general = {
                    ...generalEntry,
                    executability: rsFeedback[0]
                        ? { message: rsFeedback[0] }
                        : undefined,
                };
            } else if (generalEntry) {
                fd.general = generalEntry;
            }
            return { ...fd, ...extra };
        };

        // ── 3. AST parsing & validation ──────────────────────────────────────

        let studentAST   = this.parser.astify(studentQuery,   { database: 'postgresql' });
        let referenceAST = this.parser.astify(referenceQuery, { database: 'postgresql' });

        // Multi-statement input
        if (Array.isArray(studentAST) || Array.isArray(referenceAST)) {
            const grade = resultSetMatch ? SQLQueryGradingService.FULL_GRADE : 0;
            const feedbackDetails: AssembledFeedback = {
                general: { astArray: { message: 'AST array not supported.' } },
            };
            if (rsFeedback.length > 0) {
                feedbackDetails.general!.executability = { message: rsFeedback[0] };
            }
            return {
                grade,
                feedbackDetails,
                equivalent:         grade === SQLQueryGradingService.FULL_GRADE,
                supportedQueryType: false,
            };
        }

        if (!studentAST || !referenceAST) {
            const grade = resultSetMatch ? SQLQueryGradingService.FULL_GRADE : 0;
            const feedbackDetails: AssembledFeedback = {
                general: { astParsing: { message: 'AST parsing failed.' } },
            };
            if (rsFeedback.length > 0) {
                feedbackDetails.general!.executability = { message: rsFeedback[0] };
            }
            return {
                grade,
                feedbackDetails,
                equivalent:         grade === SQLQueryGradingService.FULL_GRADE,
                supportedQueryType: false,
            };
        }

        studentAST   = studentAST   as AST;
        referenceAST = referenceAST as AST;

        // Wrong statement type
        if (studentAST.type !== referenceAST.type) {
            const grade = resultSetMatch ? SQLQueryGradingService.FULL_GRADE : 0;
            const feedbackDetails: AssembledFeedback = {
                general: {
                    sqlClauseType: {
                        message: `Incorrect SQL clause, the task requires a clause of type: ${referenceAST.type}`,
                    },
                },
            };
            if (rsFeedback.length > 0) {
                feedbackDetails.general!.executability = { message: rsFeedback[0] };
            }
            return {
                grade,
                feedbackDetails,
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
            const assembled = this.feedbackAssembler.build(resultSetMatch, astResult, null);
            if (rsFeedback.length > 0) {
                assembled.general = {
                    ...assembled.general,
                    executability: { message: rsFeedback[0] },
                };
            }
            return {
                grade,
                feedbackDetails:    assembled,
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

        const feedbackDetails = this.feedbackAssembler.build(resultSetMatch, astResult, planResult);
        if (rsFeedback.length > 0) {
            feedbackDetails.general = {
                ...feedbackDetails.general,
                executability: { message: rsFeedback[0] },
            };
        }

        return {
            grade,
            feedbackDetails,
            equivalent:         grade === SQLQueryGradingService.FULL_GRADE,
            supportedQueryType: true,
        };
    }

    private removeSemicolon(str: string): string {
        return str.endsWith(';') ? str.slice(0, -1) : str;
    }
}
