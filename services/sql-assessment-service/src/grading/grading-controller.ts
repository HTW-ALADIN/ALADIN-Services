import { Router, Request, Response } from 'express';
import { DataSource } from 'typeorm';
import { PostgresConnectionOptions } from 'typeorm/driver/postgres/PostgresConnectionOptions';
import { AST, Parser } from 'node-sql-parser';
import { connectToDatabase, generateDatabaseKey } from '../shared/utils/database-utils';
import { isDatabaseRegistered, validateConnectionInfo } from '../shared/utils/validation';
import { SQLQueryGradingService } from './query-grading-service';
import {
    GenerationOptions,
    GptOptions,
    IRequestGradingOptions,
    IRequestComparisonOptions,
} from '../shared/interfaces/index';
import { TaskDescriptionGenerationService } from '../generation/description/task-description-generation-service';
import { t, resolveLanguageCode, SupportedLanguage } from '../shared/i18n';
import { ResultSetComparator } from './result-set-comparator';
import { ASTComparator } from './comparators/ast-comparator';
import { ExecutionPlanComparator } from './comparators/execution-plan-comparator';

// ---------------------------------------------------------------------------
// Internal helper types
// ---------------------------------------------------------------------------

interface ValidatedConnection {
    connectionInfo: PostgresConnectionOptions;
    databaseKey:    string;
    dataSource:     DataSource;
    lang:           SupportedLanguage;
}

// ---------------------------------------------------------------------------
// GradingController
// ---------------------------------------------------------------------------

/**
 * Mounts four grading-related endpoints under /api/grading:
 *
 *   POST /api/grading/grade                    — full orchestrated grading
 *   POST /api/grading/compare/result-set       — result-set comparison only
 *   POST /api/grading/compare/ast              — AST / column comparison only
 *   POST /api/grading/compare/execution-plan   — execution-plan comparison only
 *
 * All endpoints share the same connection-validation boilerplate via the
 * private validateAndConnect() helper.
 */
export class GradingController {
    public router: Router;

    constructor(
        private readonly queryGradingService:            SQLQueryGradingService,
        private readonly taskDescriptionGenerationService: TaskDescriptionGenerationService,
        private readonly resultSetComparator:            ResultSetComparator,
        private readonly astComparator:                  ASTComparator,
        private readonly executionPlanComparator:        ExecutionPlanComparator
    ) {
        this.router = Router();
        this.initializeRoutes();
    }

    private initializeRoutes(): void {
        this.router.post('/grade', (req: Request, res: Response) => {
            this.gradeQuery(req, res);
        });
        this.router.post('/compare/result-set', (req: Request, res: Response) => {
            this.compareResultSet(req, res);
        });
        this.router.post('/compare/ast', (req: Request, res: Response) => {
            this.compareAST(req, res);
        });
        this.router.post('/compare/execution-plan', (req: Request, res: Response) => {
            this.compareExecutionPlan(req, res);
        });
    }

    // =========================================================================
    // Shared validation + connection helper
    // =========================================================================

    /**
     * Validates a comparison request (IRequestComparisonOptions) and opens a
     * DataSource.  Returns null and writes a 400 response on failure.
     */
    private async validateAndConnect(
        req: Request,
        res: Response
    ): Promise<ValidatedConnection | null> {
        const body = req.body as IRequestComparisonOptions;
        const lang = resolveLanguageCode(body?.languageCode);

        if (!body?.connectionInfo) {
            res.status(400).json({ message: t('MISSING_CONNECTION_INFO', lang) });
            return null;
        }

        if (!body.referenceQuery || typeof body.referenceQuery !== 'string' || !body.referenceQuery.trim()) {
            res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
            return null;
        }

        if (!body.studentQuery || typeof body.studentQuery !== 'string' || !body.studentQuery.trim()) {
            res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
            return null;
        }

        const validationError = validateConnectionInfo(body.connectionInfo, lang);
        if (validationError) {
            res.status(400).json({ message: validationError });
            return null;
        }

        const { host, port, schema } = body.connectionInfo;
        const databaseKey = generateDatabaseKey(host!, port!, schema!);

        if (!isDatabaseRegistered(databaseKey)) {
            res.status(400).json({ message: t('DATABASE_NOT_REGISTERED', lang) });
            return null;
        }

        let dataSource: DataSource;
        let isConnected: boolean;
        try {
            dataSource  = new DataSource(body.connectionInfo);
            isConnected = await connectToDatabase(dataSource);
        } catch {
            res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
            return null;
        }

        if (!isConnected) {
            res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
            return null;
        }

        return { connectionInfo: body.connectionInfo, databaseKey, dataSource, lang };
    }

    // =========================================================================
    // POST /api/grading/grade  (existing endpoint — unchanged contract)
    // =========================================================================

    async gradeQuery(req: Request, res: Response): Promise<Response> {
        let gradingRequestOptions: IRequestGradingOptions;
        let connectionInfo: PostgresConnectionOptions;

        try {
            gradingRequestOptions = req.body;
        } catch (err: any) {
            console.log('Error in reading grading request', err);
            return res.status(400).json({ message: t('GRADING_READ_ERROR', 'en') });
        }

        const lang = resolveLanguageCode(gradingRequestOptions!?.languageCode);

        try {
            connectionInfo = gradingRequestOptions.connectionInfo;
        } catch (err: any) {
            console.log('Error in reading connection info', err);
            return res.status(400).json({ message: t('GRADING_CONNECTION_READ_ERROR', lang) });
        }

        const validationError = validateConnectionInfo(connectionInfo, lang);
        if (validationError) {
            return res.status(400).json({ message: validationError });
        }

        const databaseKey = generateDatabaseKey(connectionInfo.host!, connectionInfo.port!, connectionInfo.schema!);
        if (!isDatabaseRegistered(databaseKey)) {
            return res.status(400).json({ message: t('DATABASE_NOT_REGISTERED', lang) });
        }

        let dataSource: DataSource;
        let isConnected: boolean;
        try {
            dataSource  = new DataSource(connectionInfo);
            isConnected = await connectToDatabase(dataSource);
        } catch {
            return res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
        }

        const gradingRequest = gradingRequestOptions.gradingRequest;
        if (isConnected) {
            try {
                let comparisonResult = await this.queryGradingService.gradeQuery(
                    gradingRequest.referenceQuery,
                    gradingRequest.studentQuery,
                    dataSource,
                    databaseKey
                );
                let studentTaskDescription: string | undefined;

                if (!comparisonResult.equivalent && comparisonResult.supportedQueryType && process.env.OPENAI_API_KEY) {
                    const parser = new Parser();
                    const studentAST = parser.astify(gradingRequest.studentQuery, { database: 'postgresql' });
                    studentTaskDescription = await this.taskDescriptionGenerationService.generateTaskFromQuery(
                        GenerationOptions.Hybrid,
                        gradingRequest.studentQuery,
                        studentAST as AST,
                        connectionInfo.schema!,
                        databaseKey
                    );
                } else if (!comparisonResult.equivalent && process.env.OPENAI_API_KEY) {
                    studentTaskDescription = await this.taskDescriptionGenerationService.generateTaskFromQuery(
                        GenerationOptions.LLM,
                        gradingRequest.studentQuery,
                        {} as AST,
                        connectionInfo.schema!,
                        databaseKey,
                        undefined,
                        GptOptions.Default
                    );
                }

                if (studentTaskDescription) {
                    comparisonResult.feedback.push('\n Your query solves the task with the following description:');
                    comparisonResult.feedback.push(studentTaskDescription);
                }

                await dataSource.destroy();
                return res.status(200).json({ comparisonResult });
            } catch (error) {
                console.log(error);
                await dataSource.destroy();
                return res.status(500).json({ message: t('GRADING_FAILED_WITH_ERROR', lang, String(error)) });
            }
        }
        return res.status(500).json({ message: t('GRADING_FAILED', lang) });
    }

    // =========================================================================
    // POST /api/grading/compare/result-set
    // =========================================================================

    /**
     * Executes both queries and compares their result sets row by row.
     *
     * Response: ResultSetComparisonResponse
     *   { match: boolean, feedback: string[] }
     */
    async compareResultSet(req: Request, res: Response): Promise<Response> {
        const validated = await this.validateAndConnect(req, res);
        if (!validated) return res;

        const { dataSource, lang } = validated;
        const { referenceQuery, studentQuery } = req.body as IRequestComparisonOptions;

        try {
            const [match, feedback] = await this.resultSetComparator.compare(
                referenceQuery,
                studentQuery,
                dataSource
            );
            await dataSource.destroy();
            return res.status(200).json({ match, feedback });
        } catch (error) {
            await dataSource.destroy();
            return res.status(500).json({ message: t('GRADING_FAILED_WITH_ERROR', lang, String(error)) });
        }
    }

    // =========================================================================
    // POST /api/grading/compare/ast
    // =========================================================================

    /**
     * Parses both queries and compares their ASTs at the structural level
     * (SELECT columns, alias resolution, unsupported structure detection).
     *
     * Response: ASTComparisonResponse
     *   { columnsMatch, supported, feedback, feedbackWithSolution }
     */
    async compareAST(req: Request, res: Response): Promise<Response> {
        const validated = await this.validateAndConnect(req, res);
        if (!validated) return res;

        const { dataSource, lang } = validated;
        const { referenceQuery, studentQuery } = req.body as IRequestComparisonOptions;
        await dataSource.destroy(); // No DB call needed for AST comparison

        const parser = new Parser();
        let studentAST:   any;
        let referenceAST: any;

        try {
            studentAST   = parser.astify(studentQuery,   { database: 'postgresql' });
            referenceAST = parser.astify(referenceQuery, { database: 'postgresql' });
        } catch (error) {
            return res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
        }

        if (Array.isArray(studentAST) || Array.isArray(referenceAST)) {
            return res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
        }

        try {
            const result = this.astComparator.compare(studentAST as AST, referenceAST as AST);
            return res.status(200).json({
                columnsMatch:        result.columnsMatch,
                supported:           result.supported,
                feedback:            result.feedback,
                feedbackWithSolution: result.feedbackWithSolution,
            });
        } catch (error) {
            return res.status(500).json({ message: t('GRADING_FAILED_WITH_ERROR', lang, String(error)) });
        }
    }

    // =========================================================================
    // POST /api/grading/compare/execution-plan
    // =========================================================================

    /**
     * Runs EXPLAIN (FORMAT JSON) for both queries and diffs the resulting plans
     * element by element (GROUP BY, HAVING, ORDER BY, WHERE, JOIN).
     *
     * Response: ExecutionPlanComparisonResponse
     *   { plansMatch, feedback, feedbackWithSolution, penaltyPoints }
     */
    async compareExecutionPlan(req: Request, res: Response): Promise<Response> {
        const validated = await this.validateAndConnect(req, res);
        if (!validated) return res;

        const { dataSource, lang } = validated;
        const { referenceQuery, studentQuery } = req.body as IRequestComparisonOptions;

        const parser = new Parser();
        let studentAST:   any;
        let referenceAST: any;

        try {
            studentAST   = parser.astify(studentQuery,   { database: 'postgresql' });
            referenceAST = parser.astify(referenceQuery, { database: 'postgresql' });
        } catch (error) {
            await dataSource.destroy();
            return res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
        }

        if (Array.isArray(studentAST) || Array.isArray(referenceAST)) {
            await dataSource.destroy();
            return res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
        }

        // Build alias maps so the plan comparator can normalise table references
        const studentAliasMap   = this.astComparator.buildAliasMap((studentAST   as any).from);
        const referenceAliasMap = this.astComparator.buildAliasMap((referenceAST as any).from);

        try {
            const result = await this.executionPlanComparator.compare(
                studentAST   as AST,
                referenceAST as AST,
                studentAliasMap,
                referenceAliasMap,
                dataSource,
                studentQuery,
                referenceQuery
            );
            await dataSource.destroy();
            return res.status(200).json(result);
        } catch (error) {
            await dataSource.destroy();
            return res.status(500).json({ message: t('GRADING_FAILED_WITH_ERROR', lang, String(error)) });
        }
    }
}
