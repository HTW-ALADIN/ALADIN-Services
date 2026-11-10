import { AST } from 'node-sql-parser';
import {
	GenerationOptions,
	GptOptions,
	IAliasMap,
	IParsedTable,
} from '../../shared/interfaces/domain';
import { LlmGatewayConfig } from '../../shared/interfaces/llm-gateway';
import { isUsableLlmGatewayBlock } from '../../shared/llm-gateway/llm-gateway-config';
import { LLMTaskDescriptionGenerationEngine } from './llm-task-description-generation-engine';
import { TemplateTaskDescriptionGenerationEngine } from './template-task-description-generation-engine';
import { SupportedLanguage } from '../../shared/i18n';

export class TaskDescriptionGenerationService {
	templateTaskDescriptionGenerationEngine: TemplateTaskDescriptionGenerationEngine;
	llmTaskDescriptionGenerationEngine: LLMTaskDescriptionGenerationEngine;

	constructor(
		llmTaskDescriptionGenerationEngine: LLMTaskDescriptionGenerationEngine,
		templateTaskDescriptionGenerationEngine: TemplateTaskDescriptionGenerationEngine,
	) {
		this.templateTaskDescriptionGenerationEngine =
			templateTaskDescriptionGenerationEngine;
		this.llmTaskDescriptionGenerationEngine =
			llmTaskDescriptionGenerationEngine;
	}

	public async generateTaskFromQuery(config: {
		generationType: GenerationOptions;
		query: string;
		queryAST: AST;
		schema: string;
		databaseKey: string;
		isSelfJoin?: boolean;
		option?: GptOptions;
		schemaAliasMap?: IAliasMap;
		tables?: IParsedTable[];
		lang?: SupportedLanguage;
		llmGateway?: LlmGatewayConfig;
	}): Promise<string> {
		const {
			generationType,
			query,
			queryAST,
			schema,
			databaseKey,
			isSelfJoin,
			option,
			schemaAliasMap,
			tables,
			llmGateway,
		} = config;

		const lang = config.lang ?? 'en';
		const usableGateway = isUsableLlmGatewayBlock(llmGateway);

		const generateFromTemplate = () =>
			this.templateTaskDescriptionGenerationEngine.generateTaskFromQuery({
				query: queryAST,
				schema,
				schemaAliasMap,
				tables,
				lang,
			});

		switch (generationType) {
			case 'template':
				return generateFromTemplate();

			case 'llm':
				if (!usableGateway) {
					return generateFromTemplate();
				}
				if (!option) {
					throw Error('Undefined GPT configuration');
				}
				return await this.llmTaskDescriptionGenerationEngine.generateTaskFromQuery(
					{
						query,
						databaseKey,
						option,
						isSelfJoin,
						lang,
						llmGateway,
					},
				);

			case 'hybrid': {
				const templateDescription = generateFromTemplate();
				if (!usableGateway) {
					return templateDescription;
				}
				return await this.llmTaskDescriptionGenerationEngine.generateNLGTaskFromTemplateTask(
					query,
					templateDescription,
					databaseKey,
					isSelfJoin,
					lang,
					llmGateway,
				);
			}

			default:
				return 'Unknown generationType selected.';
		}
	}
}
