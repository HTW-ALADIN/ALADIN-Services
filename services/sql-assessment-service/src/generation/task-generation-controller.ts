import { Router, Request, Response } from 'express';
import { DataSource } from 'typeorm';
import { PostgresConnectionOptions } from 'typeorm/driver/postgres/PostgresConnectionOptions';
import {
	GenerationOptions,
	GptOptions,
	IRequestTaskOptions,
	ITaskConfiguration,
	TaskResponse,
} from '../shared/interfaces/index';
import {
	connectToDatabase,
	generateDatabaseKey,
} from '../shared/utils/database-utils';
import {
	isDatabaseRegistered,
	validateConnectionInfo,
} from '../shared/utils/validation';
import { SQLQueryGenerationService } from './query/sql-query-generation-service';
import { TaskDescriptionGenerationService } from './description/task-description-generation-service';
import { t, resolveLanguageCode } from '../shared/i18n';

export class TaskGenerationController {
	public router: Router;
	selectQueryGenerationService: SQLQueryGenerationService;
	taskDescriptionGenerationService: TaskDescriptionGenerationService;

	constructor(
		selectQueryGenerationService: SQLQueryGenerationService,
		taskDescriptionGenerationService: TaskDescriptionGenerationService,
	) {
		this.selectQueryGenerationService = selectQueryGenerationService;
		this.taskDescriptionGenerationService = taskDescriptionGenerationService;
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
		let connectionInfo: PostgresConnectionOptions;

		try {
			taskRequest = req.body;
		} catch (err: any) {
			console.log('Error in reading request', err);
			return res
				.status(400)
				.json({ message: t('TASK_GENERATION_INVALID_REQUEST', 'en') });
		}

		const lang = resolveLanguageCode(taskRequest!?.languageCode);

		try {
			connectionInfo = taskRequest.connectionInfo;
		} catch (err: any) {
			console.log('Error in reading connection info', err);
			return res
				.status(400)
				.json({ message: t('TASK_GENERATION_INVALID_CONNECTION', lang) });
		}

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
			const configValidation =
				this.selectQueryGenerationService.validateConfiguration(taskContext);
			if (!configValidation[0]) {
				return res.status(400).json({ message: configValidation[1] });
			}

			let query: string;
			let ast: any;
			try {
				[query, ast] =
					await this.selectQueryGenerationService.generateContextBasedQuery(
						taskContext,
						databaseKey,
						dataSource,
						connectionInfo.schema!,
					);
			} catch (error) {
				console.log(error);
				dataSource.destroy();
				return res.status(500).json({
					message: t('TASK_GENERATION_QUERY_ERROR', lang, String(error)),
				});
			}

			let taskDescription: string | undefined;
			let entityDescription: string | undefined;
			let creativeDescription: string | undefined;
			let schemaBasedDescription: string | undefined;
			let semanticNGL: string | undefined;

			try {
				const isSelfJoin = taskContext.joinTypes.includes('SELF JOIN');
				taskDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						generationType: GenerationOptions.Template,
						query,
						queryAST: ast,
						schema: connectionInfo.schema!,
						databaseKey,
						isSelfJoin,
						lang,
					});
				entityDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						generationType: GenerationOptions.LLM,
						query,
						queryAST: ast,
						schema: connectionInfo.schema!,
						databaseKey,
						isSelfJoin,
						option: GptOptions.MultiStep,
						lang,
					});
				creativeDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						generationType: GenerationOptions.LLM,
						query,
						queryAST: ast,
						schema: connectionInfo.schema!,
						databaseKey,
						isSelfJoin,
						option: GptOptions.Creative,
						lang,
					});
				schemaBasedDescription =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						generationType: GenerationOptions.LLM,
						query,
						queryAST: ast,
						schema: connectionInfo.schema!,
						databaseKey,
						isSelfJoin,
						option: GptOptions.Default,
						lang,
					});
				semanticNGL =
					await this.taskDescriptionGenerationService.generateTaskFromQuery({
						generationType: GenerationOptions.Hybrid,
						query,
						queryAST: ast,
						schema: connectionInfo.schema!,
						databaseKey,
						isSelfJoin,
						lang,
					});
			} catch (error) {
				console.log('Error in task description generation', error);
				return res
					.status(500)
					.json({ message: t('TASK_GENERATION_DESCRIPTION_ERROR', lang) });
			}

			const taskResponse: TaskResponse = {
				query: query,
				templateBasedDescription: taskDescription!,
				gptEntityRelationshipDescription: entityDescription!,
				gptSchemaBasedDescription: schemaBasedDescription!,
				hybridDescription: semanticNGL!,
				gptCreativeDescription: creativeDescription,
			};
			await dataSource.destroy();
			return res.status(200).json(taskResponse);
		}

		return res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
	}
}
