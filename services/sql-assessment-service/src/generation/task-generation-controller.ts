import { Router, Request, Response } from 'express';
import { DataSource } from 'typeorm';
import {
	ConnectionInfo,
	DescriptionStrategy,
	GenerationOptions,
	GptOptions,
	IRequestTaskOptions,
	ITaskConfiguration,
	LlmGatewayConfig,
	TaskResponse,
} from '../shared/interfaces/index';
import {
	connectToDatabase,
	generateDatabaseKey,
	generatePGliteKey,
	makeRowQueryFn,
} from '../shared/utils/database-utils';
import {
	isDatabaseRegistered,
	validateConnectionInfo,
} from '../shared/utils/validation';
import { pgliteInstances } from '../database/internal-memory';
import { SQLQueryGenerationService } from './query/sql-query-generation-service';
import { TaskDescriptionGenerationService } from './description/task-description-generation-service';
import { t, resolveLanguageCode, SupportedLanguage } from '../shared/i18n';
import { DatabaseService } from '../database/database-service';

/**
 * @openapi
 * /api/generation/generate:
 *   get:
 *     summary: Generate a random SQL task
 *     description: >
 *       Generates a random SQL SELECT query based on the supplied task
 *       configuration (join depth, aggregation, predicates, etc.) and produces
 *       natural-language descriptions of the task. By default all five
 *       description strategies (template, LLM entity-relationship, LLM
 *       schema-based, LLM creative, hybrid) are generated; supply
 *       `descriptionStrategy` or `descriptionStrategies` to generate only the
 *       requested variants (the remaining response fields are then omitted).
 *       The database must have been previously registered via POST
 *       /api/database/analyze-database.
 *     tags:
 *       - Generation
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/GenerateTaskRequest'
 *     responses:
 *       '200':
 *         description: Task generated successfully.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/TaskResponse'
 *       '400':
 *         description: >
 *           Invalid connection info, unregistered database, or invalid task
 *           configuration.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: Query or description generation failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */

/** All description variants the generate endpoint can produce. */
export const ALL_DESCRIPTION_STRATEGIES: DescriptionStrategy[] = [
	'template',
	'entityRelationship',
	'schemaBased',
	'creative',
	'hybrid',
];

/**
 * Resolves the description variants requested by the caller. Accepts
 * `descriptionStrategy` (single) and/or `descriptionStrategies` (multiple);
 * the union of both is generated. Unrecognised values are ignored. When no
 * valid strategy is supplied the historical behaviour is preserved and all
 * variants are generated.
 */
export function resolveRequestedDescriptionStrategies(
	taskRequest: Pick<
		IRequestTaskOptions,
		'descriptionStrategy' | 'descriptionStrategies'
	>,
): Set<DescriptionStrategy> {
	const requested = new Set<DescriptionStrategy>();
	if (Array.isArray(taskRequest.descriptionStrategies)) {
		for (const strategy of taskRequest.descriptionStrategies) {
			if (ALL_DESCRIPTION_STRATEGIES.includes(strategy)) {
				requested.add(strategy);
			}
		}
	}
	if (
		taskRequest.descriptionStrategy &&
		ALL_DESCRIPTION_STRATEGIES.includes(taskRequest.descriptionStrategy)
	) {
		requested.add(taskRequest.descriptionStrategy);
	}
	return requested.size > 0
		? requested
		: new Set(ALL_DESCRIPTION_STRATEGIES);
}

export class TaskGenerationController {
	public router: Router;
	selectQueryGenerationService: SQLQueryGenerationService;
	taskDescriptionGenerationService: TaskDescriptionGenerationService;
	private readonly databaseService?: DatabaseService;

	constructor(
		selectQueryGenerationService: SQLQueryGenerationService,
		taskDescriptionGenerationService: TaskDescriptionGenerationService,
		databaseService?: DatabaseService,
	) {
		this.selectQueryGenerationService = selectQueryGenerationService;
		this.taskDescriptionGenerationService = taskDescriptionGenerationService;
		this.databaseService = databaseService;
		this.router = Router();
		this.initializeRoutes();
	}

	private initializeRoutes(): void {
		this.router.get('/generate', (req: Request, resp: Response) => {
			this.generateTaskForRequest(req, resp);
		});
	}

	public async generateTaskForRequest(
		req: Request,
		res: Response,
	): Promise<Response> {
		let taskRequest: IRequestTaskOptions;
		let connectionInfo: ConnectionInfo;

		try {
			taskRequest = req.body;
		} catch (err: any) {
			console.log('Error in reading request', err);
			return res
				.status(400)
				.json({ message: t('TASK_GENERATION_INVALID_REQUEST', 'en') });
		}

		const lang = resolveLanguageCode(taskRequest?.languageCode);

		try {
			connectionInfo = taskRequest.connectionInfo;
		} catch (err: any) {
			console.log('Error in reading connection info', err);
			return res
				.status(400)
				.json({ message: t('TASK_GENERATION_INVALID_CONNECTION', lang) });
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
		if (connectionInfo.type === 'pglite') {
			const { databaseId } = connectionInfo;
			if (!databaseId || typeof databaseId !== 'string') {
				return res
					.status(400)
					.json({ message: t('INVALID_CONNECTION_INFO', lang) });
			}

			const databaseKey = generatePGliteKey(databaseId);
			if (!isDatabaseRegistered(databaseKey)) {
				return res
					.status(400)
					.json({ message: t('DATABASE_NOT_REGISTERED', lang) });
			}

			const pgliteDb = pgliteInstances.get(databaseId);
			if (!pgliteDb) {
				return res
					.status(400)
					.json({ message: t('DATABASE_NOT_REGISTERED', lang) });
			}

		const runQuery = async (sql: string) => {
			const result = await pgliteDb.query(sql);
			return result.rows as any[];
		};

		return this.runGeneration(
			res,
			taskRequest.taskConfiguration,
			databaseKey,
			'public',
			runQuery,
			lang,
			null,
			taskRequest.llmGateway,
			resolveRequestedDescriptionStrategies(taskRequest),
		);
  }
	// ---------------------------------------------------------------------

	// ---- PostgreSQL branch ----------------------------------------------
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

	console.log('Received connection info:', connectionInfo);

	const taskContext: ITaskConfiguration = taskRequest.taskConfiguration;
	const dataSource = new DataSource(connectionInfo);
	const isConnected = await connectToDatabase(dataSource);

  if (isConnected) {
		return this.runGeneration(
			res,
			taskContext,
			databaseKey,
			connectionInfo.schema!,
			makeRowQueryFn(dataSource),
			lang,
			dataSource,
			taskRequest.llmGateway,
			resolveRequestedDescriptionStrategies(taskRequest),
		);
  }

		await dataSource.destroy();
		return res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
	}

	private async runGeneration(
		res: Response,
		taskContext: ITaskConfiguration,
		databaseKey: string,
		schema: string,
		runQuery: (sql: string) => Promise<any[]>,
		lang: SupportedLanguage,
		dataSource: DataSource | null,
		llmGateway?: LlmGatewayConfig,
		requestedStrategies?: Set<DescriptionStrategy>,
	): Promise<Response> {
		const configValidation =
			this.selectQueryGenerationService.validateConfiguration(taskContext);
		if (!configValidation[0]) {
			if (dataSource) await dataSource.destroy();
			return res.status(400).json({ message: configValidation[1] });
		}

		let query: string;
		let ast: any;
		try {
			[query, ast] =
				await this.selectQueryGenerationService.generateContextBasedQuery(
					taskContext,
					databaseKey,
					runQuery,
					schema,
				);
		} catch (error) {
			console.log(error);
			if (dataSource) await dataSource.destroy();
			return res.status(500).json({
				message: t('TASK_GENERATION_QUERY_ERROR', lang, String(error)),
			});
		}

		// Generate only the description variants the caller requested; when no
		// strategies were supplied all variants are produced (backward
		// compatible).
		const strategies =
			requestedStrategies ?? new Set(ALL_DESCRIPTION_STRATEGIES);
		const taskResponse: TaskResponse = { query };

		try {
			const isSelfJoin = taskContext.joinTypes.includes('SELF JOIN');
			const descriptionConfig = {
				query,
				queryAST: ast,
				schema,
				databaseKey,
				isSelfJoin,
				lang,
				llmGateway,
			};
			if (strategies.has('template')) {
				taskResponse.templateBasedDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						...descriptionConfig,
						generationType: GenerationOptions.Template,
					});
			}
			if (strategies.has('entityRelationship')) {
				taskResponse.gptEntityRelationshipDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						...descriptionConfig,
						generationType: GenerationOptions.LLM,
						option: GptOptions.MultiStep,
					});
			}
			if (strategies.has('creative')) {
				taskResponse.gptCreativeDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						...descriptionConfig,
						generationType: GenerationOptions.LLM,
						option: GptOptions.Creative,
					});
			}
			if (strategies.has('schemaBased')) {
				taskResponse.gptSchemaBasedDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						...descriptionConfig,
						generationType: GenerationOptions.LLM,
						option: GptOptions.Default,
					});
			}
			if (strategies.has('hybrid')) {
				taskResponse.hybridDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						...descriptionConfig,
						generationType: GenerationOptions.Hybrid,
					});
			}
		} catch (error) {
			console.log('Error in task description generation', error);
			if (dataSource) await dataSource.destroy();
			return res
				.status(500)
				.json({ message: t('TASK_GENERATION_DESCRIPTION_ERROR', lang) });
		}

		if (dataSource) await dataSource.destroy();
		return res.status(200).json(taskResponse);
	}
}
