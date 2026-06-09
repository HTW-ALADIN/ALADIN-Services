import { Router, Request, Response, NextFunction } from 'express';
import { DataSource } from 'typeorm';
import {
	connectToDatabase,
	generateDatabaseKey,
	generatePGliteKey,
} from '../shared/utils/database-utils';
import {
	isDatabaseRegistered,
	validateConnectionInfo,
} from '../shared/utils/validation';
import { IRequestQueryOptions } from '../shared/interfaces/http';
import {
	QueryExecutionError,
	QueryExecutionService,
} from './query-execution-service';
import { t, resolveLanguageCode, SupportedLanguage } from '../shared/i18n';
import { pgliteInstances } from '../database/internal-memory';
import { DatabaseService } from '../database/database-service';

/**
 * Exposes a single endpoint for executing a raw SQL SELECT query against a
 * pre-registered database.
 *
 *   POST /api/query/execute
 *
 * Request body: IRequestQueryOptions
 *   { connectionInfo, query, languageCode? }
 *
 * Success response (200):
 *   { rows: Record<string, unknown>[], rowCount: number }
 *
 * Error responses:
 *   400 – missing / invalid input, unregistered DB, non-SELECT or unparseable query
 *   500 – database-level execution failure or unexpected error
 *
 * All error messages are localised according to the optional `languageCode`
 * field in the request body (default: "en").
 */
/**
 * @openapi
 * /api/query/execute:
 *   post:
 *     summary: Execute a raw SQL SELECT query
 *     description: >
 *       Executes a raw SQL SELECT statement against a pre-registered database.
 *       Only SELECT statements are permitted; all other statement types are
 *       rejected with a 400 error. The database must have been previously
 *       registered via POST /api/database/analyze-database.
 *     tags:
 *       - Query
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/QueryExecuteRequest'
 *     responses:
 *       '200':
 *         description: Query executed successfully.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/QueryExecutionResult'
 *       '400':
 *         description: >
 *           Invalid request body, unregistered database, non-SELECT statement,
 *           or connection failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: Database-level execution failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */
export class QueryExecutionController {
	public router: Router;
	private readonly queryExecutionService: QueryExecutionService;
	private readonly databaseService?: DatabaseService;

	constructor(
		queryExecutionService: QueryExecutionService,
		databaseService?: DatabaseService,
	) {
		this.queryExecutionService = queryExecutionService;
		this.databaseService = databaseService;
		this.router = Router();
		this.initializeRoutes();
	}

	private initializeRoutes(): void {
		this.router.post(
			'/execute',
			(req: Request, res: Response, next: NextFunction) => {
				this.executeQuery(req, res).catch(next);
			},
		);
	}

	public async executeQuery(req: Request, res: Response): Promise<Response> {
		let options: IRequestQueryOptions;

		try {
			options = req.body as IRequestQueryOptions;
		} catch {
			// Language unknown at this point — fall back to default.
			return res.status(400).json({ message: t('INVALID_REQUEST_BODY', 'en') });
		}

		const lang = resolveLanguageCode(options?.languageCode);

		if (!options?.connectionInfo) {
			return res
				.status(400)
				.json({ message: t('MISSING_CONNECTION_INFO', lang) });
		}

		if (
			!options.query ||
			typeof options.query !== 'string' ||
			options.query.trim() === ''
		) {
			return res
				.status(400)
				.json({ message: t('MISSING_OR_EMPTY_QUERY', lang) });
		}

		// ---- auto-analyze ---------------------------------------------------
		if (this.databaseService) {
			const analyzed = await this.databaseService.ensureAnalyzed(
				options.connectionInfo,
				undefined,
				lang,
			);
			if (!analyzed.ok) {
				return res.status(analyzed.status).json({ message: analyzed.message });
			}
		}
		// ---------------------------------------------------------------------

		// ---- PGlite branch ------------------------------------------------
		if ((options.connectionInfo as any)?.type === 'pglite') {
			return this.executeQueryOnPGlite(
				options.connectionInfo as any,
				options.query,
				lang,
				res,
			);
		}
		// -------------------------------------------------------------------

		const validationError = validateConnectionInfo(
			options.connectionInfo,
			lang,
		);
		if (validationError) {
			return res.status(400).json({ message: validationError });
		}

		const { host, port, schema } = options.connectionInfo;
		const databaseKey = generateDatabaseKey(host!, port!, schema!);

		if (!isDatabaseRegistered(databaseKey)) {
			return res
				.status(400)
				.json({ message: t('DATABASE_NOT_REGISTERED', lang) });
		}

		let dataSource: DataSource;
		let isConnected: boolean;
		try {
			dataSource = new DataSource(options.connectionInfo);
			isConnected = await connectToDatabase(dataSource);
		} catch {
			return res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
		}

		if (!isConnected) {
			return res.status(400).json({ message: t('UNABLE_TO_CONNECT', lang) });
		}

		try {
			const result = await this.queryExecutionService.executeQuery(
				options.query,
				dataSource,
				lang,
			);
			await dataSource.destroy();
			return res.status(200).json(result);
		} catch (err) {
			await dataSource.destroy();

			if (err instanceof QueryExecutionError) {
				const clientCodes: QueryExecutionError['code'][] = [
					'EMPTY_QUERY',
					'PARSE_ERROR',
					'MULTIPLE_STATEMENTS',
					'NON_SELECT',
				];
				const status = clientCodes.includes(err.code) ? 400 : 500;
				return res
					.status(status)
					.json({ message: err.message, code: err.code });
			}

			console.error('Unexpected error in query execution', err);
			return res
				.status(500)
				.json({ message: t('QUERY_UNEXPECTED_ERROR', lang, String(err)) });
		}
	}

	// -------------------------------------------------------------------------
	// PGlite helpers
	// -------------------------------------------------------------------------

	private async executeQueryOnPGlite(
		connectionInfo: any,
		query: string,
		lang: SupportedLanguage,
		res: Response,
	): Promise<Response> {
		const { databaseId } = connectionInfo ?? {};

		if (!databaseId || typeof databaseId !== 'string') {
			return res
				.status(400)
				.json({ message: t('INVALID_CONNECTION_INFO', lang) });
		}

		const key = generatePGliteKey(databaseId);
		if (!isDatabaseRegistered(key)) {
			return res
				.status(400)
				.json({ message: t('DATABASE_NOT_REGISTERED', lang) });
		}

		const db = pgliteInstances.get(databaseId);
		if (!db) {
			return res
				.status(400)
				.json({ message: t('DATABASE_NOT_REGISTERED', lang) });
		}

		try {
			const result = await this.queryExecutionService.executeQueryOnPGlite(
				query,
				db,
				lang,
			);
			return res.status(200).json(result);
		} catch (err) {
			if (err instanceof QueryExecutionError) {
				const clientCodes: QueryExecutionError['code'][] = [
					'EMPTY_QUERY',
					'PARSE_ERROR',
					'MULTIPLE_STATEMENTS',
					'NON_SELECT',
				];
				const status = clientCodes.includes(err.code) ? 400 : 500;
				return res
					.status(status)
					.json({ message: err.message, code: err.code });
			}
			console.error('Unexpected error in PGlite query execution', err);
			return res
				.status(500)
				.json({ message: t('QUERY_UNEXPECTED_ERROR', lang, String(err)) });
		}
	}
}
