import { Router, Request, Response } from 'express';
import { DataSource } from 'typeorm';
import { PostgresConnectionOptions } from 'typeorm/driver/postgres/PostgresConnectionOptions';
import { AST, Parser } from 'node-sql-parser';
import {
	connectToDatabase,
	generateDatabaseKey,
} from '../shared/utils/database-utils';
import {
	isDatabaseRegistered,
	validateConnectionInfo,
} from '../shared/utils/validation';
import { SQLQueryGradingService } from './query-grading-service';
import {
	ComparisonResult,
	GenerationOptions,
	GptOptions,
	IRequestGradingOptions,
	IRequestComparisonOptions,
	ReferenceQuery,
} from '../shared/interfaces/index';
import { TaskDescriptionGenerationService } from '../generation/description/task-description-generation-service';
import { t, resolveLanguageCode, SupportedLanguage } from '../shared/i18n';
import { ResultSetComparator } from './result-set-comparator';
import { ASTComparator } from './comparators/ast-comparator';
import { ExecutionPlanComparator } from './comparators/execution-plan-comparator';
import {
	ProximityHeuristic,
	QueryProximityService,
} from './query-proximity-service';
import { DatabaseService } from '../database/database-service';

// ---------------------------------------------------------------------------
// Internal helper types
// ---------------------------------------------------------------------------

interface ValidatedConnection {
	connectionInfo: PostgresConnectionOptions;
	databaseKey: string;
	dataSource: DataSource;
	lang: SupportedLanguage;
}

// ---------------------------------------------------------------------------
// GradingController
// ---------------------------------------------------------------------------

/**
 * @openapi
 * /api/grading/grade:
 *   post:
 *     summary: Full orchestrated grading of a student SQL query
 *     description: >
 *       Executes both the reference and student queries, compares their result
 *       sets, AST structure, and execution plans, calculates a grade, and
 *       optionally generates a natural-language description of the student
 *       query. Accepts either a single `referenceQuery` (deprecated) or a
 *       `referenceQueries` array; when multiple references are supplied the
 *       structurally closest one is selected automatically.
 *     tags:
 *       - Grading
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/GradeRequest'
 *     responses:
 *       '200':
 *         description: Grading completed successfully.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/GradeResponse'
 *       '400':
 *         description: Invalid request, unregistered database, or connection failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: Grading pipeline failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *
 * /api/grading/compare/result-set:
 *   post:
 *     summary: Compare result sets of two SQL queries
 *     description: >
 *       Executes both the reference and student queries against the registered
 *       database and compares their returned rows. Useful as a lightweight
 *       correctness check without full grading overhead.
 *     tags:
 *       - Grading
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/ComparisonRequest'
 *     responses:
 *       '200':
 *         description: Result-set comparison completed.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ResultSetComparisonResponse'
 *       '400':
 *         description: Invalid request or connection failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: Comparison failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *
 * /api/grading/compare/ast:
 *   post:
 *     summary: Compare AST structures of two SQL queries
 *     description: >
 *       Parses both the reference and student queries and compares their
 *       abstract syntax trees at the structural level (SELECT columns, alias
 *       resolution, unsupported structure detection). No database execution
 *       is required.
 *     tags:
 *       - Grading
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/ComparisonRequest'
 *     responses:
 *       '200':
 *         description: AST comparison completed.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ASTComparisonResponse'
 *       '400':
 *         description: Invalid request or parse failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: Comparison failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *
 * /api/grading/compare/execution-plan:
 *   post:
 *     summary: Compare query execution plans
 *     description: >
 *       Runs EXPLAIN (FORMAT JSON) for both queries and diffs the resulting
 *       plans element by element (WHERE, GROUP BY, ORDER BY, JOIN). Returns
 *       per-element feedback and a penalty point total.
 *     tags:
 *       - Grading
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/ComparisonRequest'
 *     responses:
 *       '200':
 *         description: Execution-plan comparison completed.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ExecutionPlanComparisonResponse'
 *       '400':
 *         description: Invalid request or parse failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: Comparison failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */

/**
 * Mounts four grading-related endpoints under /api/grading:
 *
 *   POST /api/grading/grade                    — full orchestrated grading
 *   POST /api/grading/compare/result-set       — result-set comparison only
 *   POST /api/grading/compare/ast              — AST / column comparison only
 *   POST /api/grading/compare/execution-plan   — execution-plan comparison only
 *
 * All endpoints accept either a single `referenceQuery` string (legacy) or a
 * `referenceQueries` array (preferred).  When multiple reference queries are
 * provided the {@link QueryProximityService} selects the structurally closest
 * one to the student query before comparison.
 *
 * All endpoints share the same connection-validation boilerplate via the
 * private validateAndConnect() helper.
 */
export class GradingController {
	public router: Router;

	constructor(
		private readonly queryGradingService: SQLQueryGradingService,
		private readonly taskDescriptionGenerationService: TaskDescriptionGenerationService,
		private readonly resultSetComparator: ResultSetComparator,
		private readonly astComparator: ASTComparator,
		private readonly executionPlanComparator: ExecutionPlanComparator,
		private readonly queryProximityService: QueryProximityService = new QueryProximityService(),
		private readonly databaseService?: DatabaseService,
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
		this.router.post(
			'/compare/execution-plan',
			(req: Request, res: Response) => {
				this.compareExecutionPlan(req, res);
			},
		);
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
		res: Response,
	): Promise<ValidatedConnection | null> {
		const body = req.body as IRequestComparisonOptions;
		const lang = resolveLanguageCode(body?.languageCode);

		if (!body?.connectionInfo) {
			res.status(400).json({ message: t('MISSING_CONNECTION_INFO', lang) });
			return null;
		}

		// At least one reference query source must be provided
		const hasLegacy =
			typeof body.referenceQuery === 'string' &&
			body.referenceQuery.trim().length > 0;
		const hasCollection =
			Array.isArray(body.referenceQueries) && body.referenceQueries.length > 0;
		if (!hasLegacy && !hasCollection) {
			res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
			return null;
		}

		if (
			!body.studentQuery ||
			typeof body.studentQuery !== 'string' ||
			!body.studentQuery.trim()
		) {
			res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
			return null;
		}

		// ---- auto-analyze ---------------------------------------------------
		if (this.databaseService) {
			const analyzed = await this.databaseService.ensureAnalyzed(
				body.connectionInfo,
				undefined,
				lang,
			);
			if (!analyzed.ok) {
				res.status(analyzed.status).json({ message: analyzed.message });
				return null;
			}
		}
		// ---------------------------------------------------------------------

		// ---- PGlite branch --------------------------------------------------
		if ((body.connectionInfo as any)?.type === 'pglite') {
			res
				.status(400)
				.json({ message: t('GRADING_PGLITE_NOT_SUPPORTED', lang) });
			return null;
		}
		// ---------------------------------------------------------------------

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
			dataSource = new DataSource(body.connectionInfo);
			isConnected = await connectToDatabase(dataSource);
		} catch {
			res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
			return null;
		}

		if (!isConnected) {
			res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
			return null;
		}

		return {
			connectionInfo: body.connectionInfo,
			databaseKey,
			dataSource,
			lang,
		};
	}

	// =========================================================================
	// Reference-query resolution helper
	// =========================================================================

	/**
	 * Resolves the single reference query string to use for comparison.
	 *
	 * When `referenceQueries` is supplied (preferred), the
	 * {@link QueryProximityService} selects the structurally closest candidate
	 * to `studentQuery`.  The legacy `referenceQuery` string is used as a
	 * fallback when no collection is present.
	 *
	 * The optional `heuristic` parameter is forwarded to the proximity service.
	 * Defaults to {@link ProximityHeuristic.ASTEditDistance}.
	 */
	private resolveReferenceQuery(
		studentQuery: string,
		referenceQuery?: string,
		referenceQueries?: ReferenceQuery[],
		heuristic?: ProximityHeuristic,
	): string {
		if (Array.isArray(referenceQueries) && referenceQueries.length > 0) {
			const result = this.queryProximityService.selectClosest(
				studentQuery,
				referenceQueries,
				heuristic,
			);
			return result.referenceQuery.query;
		}
		// Fallback to legacy single string (already validated to be non-empty by this point)
		return referenceQuery!;
	}

	// =========================================================================
	// POST /api/grading/grade
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

		const lang = resolveLanguageCode(gradingRequestOptions?.languageCode);

		try {
			connectionInfo = gradingRequestOptions.connectionInfo;
		} catch (err: any) {
			console.log('Error in reading connection info', err);
			return res
				.status(400)
				.json({ message: t('GRADING_CONNECTION_READ_ERROR', lang) });
		}

		// ---- auto-analyze ---------------------------------------------------
		if (this.databaseService) {
			const analyzed = await this.databaseService.ensureAnalyzed(
				connectionInfo,
				undefined,
				lang,
			);
			if (!analyzed.ok) {
				return res.status(analyzed.status).json({ message: analyzed.message });
			}
		}
		// ---------------------------------------------------------------------

		// ---- PGlite branch --------------------------------------------------
		if ((connectionInfo as any)?.type === 'pglite') {
			return res
				.status(400)
				.json({ message: t('GRADING_PGLITE_NOT_SUPPORTED', lang) });
		}
		// ---------------------------------------------------------------------

		const validationError = validateConnectionInfo(connectionInfo, lang);
		if (validationError) {
			return res.status(400).json({ message: validationError });
		}

		const databaseKey = generateDatabaseKey(
			connectionInfo.host!,
			connectionInfo.port!,
			connectionInfo.schema!,
		);
		if (!isDatabaseRegistered(databaseKey)) {
			return res
				.status(400)
				.json({ message: t('DATABASE_NOT_REGISTERED', lang) });
		}

		let dataSource: DataSource;
		let isConnected: boolean;
		try {
			dataSource = new DataSource(connectionInfo);
			isConnected = await connectToDatabase(dataSource);
		} catch {
			return res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
		}

		const gradingRequest = gradingRequestOptions.gradingRequest;
		if (isConnected) {
			try {
				const resolvedReferenceQuery = this.resolveReferenceQuery(
					gradingRequest.studentQuery,
					gradingRequest.referenceQuery,
					gradingRequest.referenceQueries,
				);

				const comparisonResult = await this.queryGradingService.gradeQuery(
					resolvedReferenceQuery,
					gradingRequest.studentQuery,
					dataSource,
					databaseKey,
					lang,
				);

				await this.appendTaskDescription(
					comparisonResult,
					gradingRequest.studentQuery,
					connectionInfo.schema!,
					databaseKey,
					lang,
					gradingRequestOptions.generationStrategy,
					gradingRequestOptions.gptOption,
				);

				await dataSource.destroy();
				return res.status(200).json({ comparisonResult });
			} catch (error) {
				console.log(error);
				await dataSource.destroy();
				return res.status(500).json({
					message: t('GRADING_FAILED_WITH_ERROR', lang, String(error)),
				});
			}
		}
		return res.status(500).json({ message: t('GRADING_FAILED', lang) });
	}

	// =========================================================================
	// Task-description generation helper
	// =========================================================================

	/**
	 * Generates a natural-language description of the student's query and
	 * appends it to `comparisonResult.feedback` when applicable.
	 *
	 * The concrete generation strategy is selected via `strategy`:
	 *
	 * | strategy              | behaviour                                                      |
	 * |-----------------------|----------------------------------------------------------------|
	 * | `undefined` (default) | Hybrid when the query type is supported, LLM otherwise         |
	 * | `Template`            | AST-based template engine only (no LLM required)               |
	 * | `LLM`                 | Pure LLM call; uses `gptOption` (defaults to `GptOptions.Default`) |
	 * | `Hybrid`              | Template engine → LLM NLG post-processing                      |
	 *
	 * When `OPENAI_API_KEY` is absent the service automatically falls back to the
	 * Template engine so a description is always produced.
	 *
	 * The method is a no-op when the student query is already equivalent to the
	 * reference query.
	 */
	private async appendTaskDescription(
		comparisonResult: ComparisonResult,
		studentQuery: string,
		schema: string,
		databaseKey: string,
		lang: SupportedLanguage,
		strategy?: GenerationOptions,
		gptOption?: GptOptions,
	): Promise<void> {
		if (comparisonResult.equivalent) return;

		const resolvedGptOption = gptOption ?? GptOptions.Default;

		let studentTaskDescription: string | undefined;

		if (strategy !== undefined) {
			// Explicit strategy chosen by the caller
			const parser = new Parser();
			const studentAST =
				strategy !== GenerationOptions.LLM
					? (parser.astify(studentQuery, { database: 'postgresql' }) as AST)
					: ({} as AST);

			studentTaskDescription =
				await this.taskDescriptionGenerationService.generateTaskFromQuery({
					generationType: strategy,
					query: studentQuery,
					queryAST: studentAST,
					schema: schema,
					databaseKey,
					isSelfJoin: undefined,
					option: resolvedGptOption,
					lang,
				});
		} else {
			// Default behaviour: Hybrid for supported types, LLM otherwise.
			// When OPENAI_API_KEY is absent the service falls back to Template.
			if (comparisonResult.supportedQueryType) {
				const parser = new Parser();
				const studentAST = parser.astify(studentQuery, {
					database: 'postgresql',
				}) as AST;
				studentTaskDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						generationType: GenerationOptions.Hybrid,
						query: studentQuery,
						queryAST: studentAST,
						schema: schema,
						databaseKey,
						isSelfJoin: undefined,
						option: resolvedGptOption,
						lang,
					});
			} else {
				studentTaskDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						generationType: GenerationOptions.LLM,
						query: studentQuery,
						queryAST: {} as AST,
						schema: schema,
						databaseKey,
						isSelfJoin: undefined,
						option: GptOptions.Default,
						lang,
					});
			}
		}

		if (studentTaskDescription) {
			comparisonResult.feedbackDetails.taskDescription = {
				description: {
					message: t('FEEDBACK_TASK_DESCRIPTION', lang),
					solution: studentTaskDescription,
				},
			};
		}
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
		const body = req.body as IRequestComparisonOptions;
		const { studentQuery } = body;

		const referenceQuery = this.resolveReferenceQuery(
			studentQuery,
			body.referenceQuery,
			body.referenceQueries,
		);

		try {
			const [match, rsFeedback] = await this.resultSetComparator.compare(
				referenceQuery,
				studentQuery,
				dataSource,
			);
			await dataSource.destroy();
			const feedback =
				rsFeedback.length > 0
					? { verdict: { message: rsFeedback[0] } }
					: undefined;
			return res.status(200).json({ match, feedback });
		} catch (error) {
			await dataSource.destroy();
			return res
				.status(500)
				.json({ message: t('GRADING_FAILED_WITH_ERROR', lang, String(error)) });
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
		const body = req.body as IRequestComparisonOptions;
		const { studentQuery } = body;

		const referenceQuery = this.resolveReferenceQuery(
			studentQuery,
			body.referenceQuery,
			body.referenceQueries,
		);

		await dataSource.destroy(); // No DB call needed for AST comparison

		const parser = new Parser();
		let studentAST: any;
		let referenceAST: any;

		try {
			studentAST = parser.astify(studentQuery, { database: 'postgresql' });
			referenceAST = parser.astify(referenceQuery, { database: 'postgresql' });
		} catch (error) {
			console.error(error);
			return res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
		}

		if (Array.isArray(studentAST) || Array.isArray(referenceAST)) {
			return res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
		}

		try {
			const result = this.astComparator.compare(
				studentAST as AST,
				referenceAST as AST,
			);
			return res.status(200).json({
				columnsMatch: result.columnsMatch,
				supported: result.supported,
				feedback: result.ast,
			});
		} catch (error) {
			return res
				.status(500)
				.json({ message: t('GRADING_FAILED_WITH_ERROR', lang, String(error)) });
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
		const body = req.body as IRequestComparisonOptions;
		const { studentQuery } = body;

		const referenceQuery = this.resolveReferenceQuery(
			studentQuery,
			body.referenceQuery,
			body.referenceQueries,
		);

		const parser = new Parser();
		let studentAST: any;
		let referenceAST: any;

		try {
			studentAST = parser.astify(studentQuery, { database: 'postgresql' });
			referenceAST = parser.astify(referenceQuery, { database: 'postgresql' });
		} catch (error) {
			console.error(error);
			await dataSource.destroy();
			return res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
		}

		if (Array.isArray(studentAST) || Array.isArray(referenceAST)) {
			await dataSource.destroy();
			return res.status(400).json({ message: t('GRADING_READ_ERROR', lang) });
		}

		// Build alias maps so the plan comparator can normalise table references
		const studentAliasMap = this.astComparator.buildAliasMap(
			(studentAST as any).from,
		);
		const referenceAliasMap = this.astComparator.buildAliasMap(
			(referenceAST as any).from,
		);

		try {
			const result = await this.executionPlanComparator.compare(
				studentAST as AST,
				referenceAST as AST,
				studentAliasMap,
				referenceAliasMap,
				dataSource,
				studentQuery,
				referenceQuery,
			);
			await dataSource.destroy();
			return res.status(200).json({
				plansMatch: result.plansMatch,
				feedback: result.executionPlan,
				penaltyPoints: result.penaltyPoints,
			});
		} catch (error) {
			await dataSource.destroy();
			return res
				.status(500)
				.json({ message: t('GRADING_FAILED_WITH_ERROR', lang, String(error)) });
		}
	}
}
