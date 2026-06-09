import { Router, Request, Response } from 'express';
import { DatabaseAnalyzer } from './database-analyzer';
import { DatabaseService } from './database-service';
import { t, resolveLanguageCode } from '../shared/i18n';
import { IAliasMap } from '../shared/interfaces/domain';

/**
 * @openapi
 * /api/database/analyze-database:
 *   post:
 *     summary: Analyze and register a PostgreSQL database
 *     description: >
 *       Connects to a PostgreSQL database, extracts its full schema metadata
 *       (tables, columns, FK relationships, cardinalities), and stores it in
 *       the in-memory registry under a generated database key derived from
 *       host, port, and schema. The key is required by all subsequent endpoints.
 *     tags:
 *       - Database
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/AnalyzeDatabaseRequest'
 *     responses:
 *       '200':
 *         description: Database successfully analyzed and registered.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/MessageResponse'
 *       '400':
 *         description: Invalid connection info or connection failure.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       '500':
 *         description: Schema extraction failed.
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */
export class DatabaseController {
	public router: Router;
	databaseAnalyzer: DatabaseAnalyzer;
	private readonly databaseService: DatabaseService;

	constructor(
		databaseAnalyzer: DatabaseAnalyzer,
		databaseService?: DatabaseService,
	) {
		this.databaseAnalyzer = databaseAnalyzer;
		this.databaseService =
			databaseService ?? new DatabaseService(databaseAnalyzer);
		this.router = Router();
		this.initializeRoutes();
	}

	private initializeRoutes(): void {
		this.router.post('/analyze-database', (req: Request, resp: Response) => {
			this.analyzeDatabase(req, resp);
		});
	}

	public async analyzeDatabase(req: Request, res: Response): Promise<Response> {
		const lang = resolveLanguageCode(req.body?.languageCode);

		const connectionInfo = req.body?.connectionInfo;
		if (!connectionInfo) {
			return res
				.status(400)
				.json({ message: t('MISSING_CONNECTION_INFO', lang) });
		}

		// Parse and validate the optional alias map
		let aliasMap: IAliasMap | undefined;
		const rawAliasMap = req.body.aliasMap;
		if (rawAliasMap !== undefined) {
			if (
				typeof rawAliasMap !== 'object' ||
				Array.isArray(rawAliasMap) ||
				rawAliasMap === null
			) {
				console.log(
					'Invalid aliasMap provided — must be a plain object. Ignoring.',
				);
			} else {
				aliasMap = rawAliasMap as IAliasMap;
			}
		}

		const result = await this.databaseService.ensureAnalyzed(
			connectionInfo,
			aliasMap,
			lang,
			true,
		);
		return res.status(result.status).json({ message: result.message });
	}
}
