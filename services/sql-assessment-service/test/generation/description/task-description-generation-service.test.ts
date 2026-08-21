import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { AST, Parser } from 'node-sql-parser';
import { TaskDescriptionGenerationService } from '../../../src/generation/description/task-description-generation-service';
import { TemplateTaskDescriptionGenerationEngine } from '../../../src/generation/description/template-task-description-generation-engine';
import { LLMTaskDescriptionGenerationEngine } from '../../../src/generation/description/llm-task-description-generation-engine';
import { GenerationOptions, GptOptions } from '../../../src/shared/interfaces/domain';
import { LlmGatewayClient } from '../../../src/shared/llm-gateway/llm-gateway-client';
import { databaseMetadata } from '../../../src/database/internal-memory';
import { EntityType } from '../../../src/shared/interfaces/domain';

const parser = new Parser();

function minimalMetadata() {
	databaseMetadata.set('fallback-test-db', [
		{
			name: 'products',
			joinPaths: [],
			columns: [
				{
					name: 'name',
					type: 'varchar',
					tableName: 'products',
					isNullable: false,
					isPrimaryKey: false,
					isForeignKey: false,
				},
			],
			entityType: EntityType.Strong,
			relationships: [],
		},
	]);
}

const GATEWAY = { endpoint: 'http://gateway:8080', apiKey: 'secret' };

describe('TaskDescriptionGenerationService', () => {
	let llmEngine: LLMTaskDescriptionGenerationEngine;
	let templateEngine: TemplateTaskDescriptionGenerationEngine;
	let stubClient: { generate: ReturnType<typeof vi.fn> };
	let service: TaskDescriptionGenerationService;

	beforeEach(() => {
		minimalMetadata();
		stubClient = { generate: vi.fn() };
		llmEngine = new LLMTaskDescriptionGenerationEngine(
			stubClient as unknown as LlmGatewayClient,
		);
		templateEngine = new TemplateTaskDescriptionGenerationEngine();
		service = new TaskDescriptionGenerationService(llmEngine, templateEngine);
	});

	afterEach(() => {
		databaseMetadata.clear();
		vi.restoreAllMocks();
	});

	const baseConfig = {
		query: 'SELECT name FROM products',
		queryAST: parser.astify('SELECT name FROM products') as AST,
		schema: 'public',
		databaseKey: 'fallback-test-db',
	};

	describe('generateTaskFromQuery', () => {
		it('delegates to the template engine when generationType is "template"', async () => {
			stubClient.generate.mockRejectedValue(
				new Error('must not call the gateway'),
			);
			const result = await service.generateTaskFromQuery({
				...baseConfig,
				generationType: GenerationOptions.Template,
				llmGateway: GATEWAY,
			});
			expect(stubClient.generate).not.toHaveBeenCalled();
			expect(result).toEqual(expect.any(String));
			expect(result.length).toBeGreaterThan(0);
		});

		it('falls back to the template engine for "llm" without an llmGateway block', async () => {
			stubClient.generate.mockRejectedValue(
				new Error('must not call the gateway'),
			);
			const result = await service.generateTaskFromQuery({
				...baseConfig,
				generationType: GenerationOptions.LLM,
				option: GptOptions.Default,
			});
			expect(stubClient.generate).not.toHaveBeenCalled();
			expect(result).toEqual(expect.any(String));
			expect(result.length).toBeGreaterThan(0);
		});

		it('falls back to the template engine for "llm" with an invalid llmGateway block', async () => {
			stubClient.generate.mockRejectedValue(
				new Error('must not call the gateway'),
			);
			const result = await service.generateTaskFromQuery({
				...baseConfig,
				generationType: GenerationOptions.LLM,
				option: GptOptions.Default,
				llmGateway: { endpoint: '', apiKey: '' } as any,
			});
			expect(stubClient.generate).not.toHaveBeenCalled();
			expect(result).toEqual(expect.any(String));
		});

		it('delegates to the LLM engine when "llm" carries a usable llmGateway block', async () => {
			stubClient.generate.mockResolvedValue('LLM description');
			const result = await service.generateTaskFromQuery({
				...baseConfig,
				generationType: GenerationOptions.LLM,
				option: GptOptions.Default,
				llmGateway: GATEWAY,
			});
			expect(result).toBe('LLM description');
			expect(stubClient.generate).toHaveBeenCalledWith(
				GATEWAY,
				expect.objectContaining({ temperature: 0 }),
			);
		});

		it('throws when "llm" has a usable gateway but no GptOption is provided', async () => {
			await expect(
				service.generateTaskFromQuery({
					...baseConfig,
					generationType: GenerationOptions.LLM,
					llmGateway: GATEWAY,
				}),
			).rejects.toThrow('Undefined GPT configuration');
		});

		it('falls back to the template engine for "hybrid" without an llmGateway block', async () => {
			stubClient.generate.mockRejectedValue(
				new Error('must not call the gateway'),
			);
			const result = await service.generateTaskFromQuery({
				...baseConfig,
				generationType: GenerationOptions.Hybrid,
			});
			expect(stubClient.generate).not.toHaveBeenCalled();
			expect(result).toEqual(expect.any(String));
		});

		it('delegates to the LLM NLG engine for "hybrid" with a usable llmGateway block', async () => {
			stubClient.generate.mockResolvedValue('NLG description');
			const result = await service.generateTaskFromQuery({
				...baseConfig,
				generationType: GenerationOptions.Hybrid,
				llmGateway: GATEWAY,
			});
			expect(result).toBe('NLG description');
			expect(stubClient.generate).toHaveBeenCalledWith(
				GATEWAY,
				expect.objectContaining({ temperature: 0 }),
			);
		});

		it('returns the fallback message for an unknown generationType', async () => {
			const result = await service.generateTaskFromQuery({
				...baseConfig,
				generationType: 'unknown' as GenerationOptions,
			});
			expect(result).toBe('Unknown generationType selected.');
		});
	});
});
