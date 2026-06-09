import { Router, Request, Response } from 'express';
import { Parser } from 'node-sql-parser';
import {
	GenerationOptions,
	GptOptions,
	IAliasMap,
	IParsedTable,
} from '../../shared/interfaces/domain';
import {
	DescriptionResponse,
	IRequestDescriptionOptions,
} from '../../shared/interfaces/http';
import {
	buildAliasMapFromTables,
	generateDatabaseKey,
	generatePGliteKey,
} from '../../shared/utils/database-utils';
import {
	isDatabaseRegistered,
	validateConnectionInfo,
} from '../../shared/utils/validation';
import {
	databaseMetadata,
	selfJoinDatabaseMetadata,
} from '../../database/internal-memory';
import { TaskDescriptionGenerationService } from './task-description-generation-service';
import { t, resolveLanguageCode, SupportedLanguage } from '../../shared/i18n';
import { DatabaseService } from '../../database/database-service';

const sqlParser = new Parser();

/**
 * @openapi
 * /api/description/template:
 *   post:
 *     summary: Generate a template-based SQL description
 *     description: >
 *       Produces a deterministic, AST-driven natural-language description of
 *       the supplied SQL query using a hand-crafted template engine. No LLM
 *       or external API call is made.
 *     tags:
 *       - Description
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/DescriptionRequest'
 *     responses:
 *       '200':
 *         description: Description generated successfully.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/DescriptionResponse'
 *       '400':
 *         description: Invalid request, unregistered database, or SQL parse failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: Template engine failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *
 * /api/description/llm/default:
 *   post:
 *     summary: Generate an LLM description (default, temperature 0)
 *     description: >
 *       Uses a single-shot LLM call at temperature 0 to produce a
 *       natural-language description of the SQL query. Requires
 *       OPENAI_API_KEY to be set; falls back to the template engine otherwise.
 *     tags:
 *       - Description
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/DescriptionRequest'
 *     responses:
 *       '200':
 *         description: Description generated successfully.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/DescriptionResponse'
 *       '400':
 *         description: Invalid request or unregistered database.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: LLM call failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *
 * /api/description/llm/creative:
 *   post:
 *     summary: Generate a creative LLM description (temperature 0.7)
 *     description: >
 *       Uses a single-shot LLM call at temperature 0.7 to produce a more
 *       expressive natural-language description of the SQL query.
 *     tags:
 *       - Description
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/DescriptionRequest'
 *     responses:
 *       '200':
 *         description: Description generated successfully.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/DescriptionResponse'
 *       '400':
 *         description: Invalid request or unregistered database.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: LLM call failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *
 * /api/description/llm/multi-step:
 *   post:
 *     summary: Generate a multi-step LLM description
 *     description: >
 *       Runs a three-stage chained LLM pipeline to progressively build a
 *       high-quality natural-language description of the SQL query.
 *     tags:
 *       - Description
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/DescriptionRequest'
 *     responses:
 *       '200':
 *         description: Description generated successfully.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/DescriptionResponse'
 *       '400':
 *         description: Invalid request or unregistered database.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: LLM pipeline failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *
 * /api/description/hybrid:
 *   post:
 *     summary: Generate a hybrid template + LLM description
 *     description: >
 *       Feeds the deterministic template engine output as context into an LLM
 *       for natural-language post-processing, combining the reliability of
 *       templates with the fluency of an LLM.
 *     tags:
 *       - Description
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/DescriptionRequest'
 *     responses:
 *       '200':
 *         description: Description generated successfully.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/DescriptionResponse'
 *       '400':
 *         description: Invalid request, unregistered database, or SQL parse failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: Hybrid generation failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */

/**
 * Provides individual endpoints for each description generation approach.
 *
 * All routes are mounted under /api/description:
 *   POST /api/description/template        – deterministic AST-based template engine
 *   POST /api/description/llm/default     – single-shot LLM (temperature=0)
 *   POST /api/description/llm/creative    – single-shot LLM (temperature=0.7)
 *   POST /api/description/llm/multi-step  – three-stage chained LLM pipeline
 *   POST /api/description/hybrid          – template engine followed by LLM NLG post-processing
 *
 * All endpoints accept the same request body shape (IRequestDescriptionOptions) and return
 * a DescriptionResponse. The languageCode field is accepted and echoed back but is not yet
 * forwarded to the generation engines (see TODO comments below).
 */
export class DescriptionController {
	public router: Router;
	private taskDescriptionGenerationService: TaskDescriptionGenerationService;
	private readonly databaseService?: DatabaseService;

	constructor(
		taskDescriptionGenerationService: TaskDescriptionGenerationService,
		databaseService?: DatabaseService,
	) {
		this.taskDescriptionGenerationService = taskDescriptionGenerationService;
		this.databaseService = databaseService;
		this.router = Router();
		this.initializeRoutes();
	}

	private initializeRoutes(): void {
		this.router.post('/template', (req: Request, res: Response) => {
			this.generateTemplateDescription(req, res);
		});
		this.router.post('/llm/default', (req: Request, res: Response) => {
			this.generateLlmDefaultDescription(req, res);
		});
		this.router.post('/llm/creative', (req: Request, res: Response) => {
			this.generateLlmCreativeDescription(req, res);
		});
		this.router.post('/llm/multi-step', (req: Request, res: Response) => {
			this.generateLlmMultiStepDescription(req, res);
		});
		this.router.post('/hybrid', (req: Request, res: Response) => {
			this.generateHybridDescription(req, res);
		});
	}

	// ---------------------------------------------------------------------------
	// Shared request validation — returns null on success, a Response on failure
	// ---------------------------------------------------------------------------

	private async validateRequest(
		req: Request,
		res: Response,
	): Promise<{
		options: IRequestDescriptionOptions;
		databaseKey: string;
		lang: SupportedLanguage;
		tables: IParsedTable[];
		schemaAliasMap: IAliasMap | undefined;
		schema: string;
	} | null> {
		let options: IRequestDescriptionOptions;

		try {
			options = req.body as IRequestDescriptionOptions;
		} catch (err) {
			console.error(err);
			res.status(400).json({ message: t('INVALID_REQUEST_BODY', 'en') });
			return null;
		}

		const lang = resolveLanguageCode(options?.languageCode);

		if (!options?.connectionInfo) {
			res.status(400).json({ message: t('MISSING_CONNECTION_INFO', lang) });
			return null;
		}

		if (
			!options.query ||
			typeof options.query !== 'string' ||
			options.query.trim() === ''
		) {
			res.status(400).json({ message: t('DESCRIPTION_MISSING_QUERY', lang) });
			return null;
		}

		// ---- auto-analyze ---------------------------------------------------
		if (this.databaseService) {
			const analyzed = await this.databaseService.ensureAnalyzed(
				options.connectionInfo,
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
		const connectionInfoAny = options.connectionInfo as any;
		let databaseKey: string;
		let schema: string;

		if (connectionInfoAny?.type === 'pglite') {
			const { databaseId } = connectionInfoAny;
			if (!databaseId || typeof databaseId !== 'string') {
				res.status(400).json({ message: t('INVALID_CONNECTION_INFO', lang) });
				return null;
			}
			databaseKey = generatePGliteKey(databaseId);
			schema = 'public';
		} else {
			// PostgreSQL path
			const connectionError = validateConnectionInfo(
				options.connectionInfo,
				lang,
			);
			if (connectionError) {
				res.status(400).json({ message: connectionError });
				return null;
			}

			const { host, port, schema: pgSchema } = options.connectionInfo;
			databaseKey = generateDatabaseKey(host!, port!, pgSchema!);
			schema = pgSchema!;
		}
		// ---------------------------------------------------------------------

		if (!isDatabaseRegistered(databaseKey)) {
			res.status(400).json({ message: t('DATABASE_NOT_REGISTERED', lang) });
			return null;
		}

		// Resolve the stored table metadata so that alternativeName display names
		// (burned in at analysis time from the aliasMap) are available to both
		// the template engine and the LLM engine.
		const isSelfJoin = options.isSelfJoin ?? false;
		const tables = this.resolveStoredTables(databaseKey, isSelfJoin);
		const schemaAliasMap = buildAliasMapFromTables(tables);

		return { options, databaseKey, lang, tables, schemaAliasMap, schema };
	}

	/**
	 * Looks up the `IParsedTable[]` for the given database from the in-memory
	 * store, using the same fallback logic as the LLM engine.
	 *
	 * For self-join queries the self-join metadata is used exclusively.
	 * For all other queries self-join metadata is preferred when available,
	 * falling back to regular metadata.
	 */
	private resolveStoredTables(
		databaseKey: string,
		isSelfJoin: boolean,
	): IParsedTable[] {
		if (isSelfJoin) {
			return selfJoinDatabaseMetadata.get(databaseKey) ?? [];
		}
		return (
			selfJoinDatabaseMetadata.get(databaseKey) ??
			databaseMetadata.get(databaseKey) ??
			[]
		);
	}

	// ---------------------------------------------------------------------------
	// POST /api/description/template
	// ---------------------------------------------------------------------------

	public async generateTemplateDescription(
		req: Request,
		res: Response,
	): Promise<Response> {
		const validated = await this.validateRequest(req, res);
		if (!validated) return res;

		const { options, databaseKey, lang, tables, schemaAliasMap, schema } =
			validated;
		const languageCode = options.languageCode ?? 'en';

		let ast: any;
		try {
			ast = sqlParser.astify(options.query);
		} catch (err) {
			return res
				.status(400)
				.json({ message: t('DESCRIPTION_PARSE_FAILED', lang, String(err)) });
		}

		try {
			const description =
				await this.taskDescriptionGenerationService.generateTaskFromQuery({
					generationType: GenerationOptions.Template,
					query: options.query,
					queryAST: ast,
					schema: schema,
					databaseKey,
					isSelfJoin: options.isSelfJoin ?? false,
					schemaAliasMap,
					tables,
					lang,
				});

			const response: DescriptionResponse = { description, languageCode };
			return res.status(200).json(response);
		} catch (err) {
			console.error('Error in template description generation', err);
			return res
				.status(500)
				.json({ message: t('DESCRIPTION_TEMPLATE_FAILED', lang, String(err)) });
		}
	}

	// ---------------------------------------------------------------------------
	// POST /api/description/llm/default
	// ---------------------------------------------------------------------------

	public async generateLlmDefaultDescription(
		req: Request,
		res: Response,
	): Promise<Response> {
		const validated = await this.validateRequest(req, res);
		if (!validated) return res;

		const { options, databaseKey, lang, tables, schemaAliasMap, schema } =
			validated;
		const languageCode = options.languageCode ?? 'en';

		try {
			const description =
				await this.taskDescriptionGenerationService.generateTaskFromQuery({
					generationType: GenerationOptions.LLM,
					query: options.query,
					queryAST: null as any,
					schema: schema,
					databaseKey,
					isSelfJoin: options.isSelfJoin ?? false,
					option: GptOptions.Default,
					schemaAliasMap,
					tables,
					lang,
				});

			const response: DescriptionResponse = { description, languageCode };
			return res.status(200).json(response);
		} catch (err) {
			console.error('Error in LLM default description generation', err);
			return res.status(500).json({
				message: t('DESCRIPTION_LLM_DEFAULT_FAILED', lang, String(err)),
			});
		}
	}

	// ---------------------------------------------------------------------------
	// POST /api/description/llm/creative
	// ---------------------------------------------------------------------------

	public async generateLlmCreativeDescription(
		req: Request,
		res: Response,
	): Promise<Response> {
		const validated = await this.validateRequest(req, res);
		if (!validated) return res;

		const { options, databaseKey, lang, tables, schemaAliasMap, schema } =
			validated;
		const languageCode = options.languageCode ?? 'en';

		try {
			const description =
				await this.taskDescriptionGenerationService.generateTaskFromQuery({
					generationType: GenerationOptions.LLM,
					query: options.query,
					queryAST: null as any,
					schema: schema,
					databaseKey,
					isSelfJoin: options.isSelfJoin ?? false,
					option: GptOptions.Creative,
					schemaAliasMap,
					tables,
					lang,
				});

			const response: DescriptionResponse = { description, languageCode };
			return res.status(200).json(response);
		} catch (err) {
			console.error('Error in LLM creative description generation', err);
			return res.status(500).json({
				message: t('DESCRIPTION_LLM_CREATIVE_FAILED', lang, String(err)),
			});
		}
	}

	// ---------------------------------------------------------------------------
	// POST /api/description/llm/multi-step
	// ---------------------------------------------------------------------------

	public async generateLlmMultiStepDescription(
		req: Request,
		res: Response,
	): Promise<Response> {
		const validated = await this.validateRequest(req, res);
		if (!validated) return res;

		const { options, databaseKey, lang, tables, schemaAliasMap, schema } =
			validated;
		const languageCode = options.languageCode ?? 'en';

		try {
			const description =
				await this.taskDescriptionGenerationService.generateTaskFromQuery({
					generationType: GenerationOptions.LLM,
					query: options.query,
					queryAST: null as any,
					schema: schema,
					databaseKey,
					isSelfJoin: options.isSelfJoin ?? false,
					option: GptOptions.MultiStep,
					schemaAliasMap,
					tables,
					lang,
				});

			const response: DescriptionResponse = { description, languageCode };
			return res.status(200).json(response);
		} catch (err) {
			console.error('Error in LLM multi-step description generation', err);
			return res.status(500).json({
				message: t('DESCRIPTION_LLM_MULTISTEP_FAILED', lang, String(err)),
			});
		}
	}

	// ---------------------------------------------------------------------------
	// POST /api/description/hybrid
	// ---------------------------------------------------------------------------

	public async generateHybridDescription(
		req: Request,
		res: Response,
	): Promise<Response> {
		const validated = await this.validateRequest(req, res);
		if (!validated) return res;

		const { options, databaseKey, lang, tables, schemaAliasMap, schema } =
			validated;
		const languageCode = options.languageCode ?? 'en';

		let ast: any;
		try {
			ast = sqlParser.astify(options.query);
		} catch (err) {
			return res
				.status(400)
				.json({ message: t('DESCRIPTION_PARSE_FAILED', lang, String(err)) });
		}

		try {
			const description =
				await this.taskDescriptionGenerationService.generateTaskFromQuery({
					generationType: GenerationOptions.Hybrid,
					query: options.query,
					queryAST: ast,
					schema: schema,
					databaseKey,
					isSelfJoin: options.isSelfJoin ?? false,
					option: undefined,
					schemaAliasMap,
					tables,
					lang,
				});

			const response: DescriptionResponse = { description, languageCode };
			return res.status(200).json(response);
		} catch (err) {
			console.error('Error in hybrid description generation', err);
			return res
				.status(500)
				.json({ message: t('DESCRIPTION_HYBRID_FAILED', lang, String(err)) });
		}
	}
}
