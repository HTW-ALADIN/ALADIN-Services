import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { LLMTaskDescriptionGenerationEngine } from '../../../src/generation/description/llm-task-description-generation-engine';
import { LlmGatewayClient } from '../../../src/shared/llm-gateway/llm-gateway-client';
import { GptOptions } from '../../../src/shared/interfaces/domain';
import { EntityType } from '../../../src/shared/interfaces/domain';
import { databaseMetadata } from '../../../src/database/internal-memory';

const GATEWAY = { endpoint: 'http://gateway:8080', apiKey: 'secret' };
const DB_KEY = 'llm-engine-test-db';

function registerMetadata() {
	databaseMetadata.set(DB_KEY, [
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

describe('LLMTaskDescriptionGenerationEngine', () => {
	let stubClient: { generate: ReturnType<typeof vi.fn> };
	let engine: LLMTaskDescriptionGenerationEngine;

	beforeEach(() => {
		registerMetadata();
		stubClient = { generate: vi.fn() };
		engine = new LLMTaskDescriptionGenerationEngine(
			stubClient as unknown as LlmGatewayClient,
		);
	});

	afterEach(() => {
		databaseMetadata.clear();
		vi.restoreAllMocks();
	});

	describe('generateTaskFromQuery (default)', () => {
		it('issues a single gateway call at temperature 0 with one system message and one user message', async () => {
			stubClient.generate.mockResolvedValue('default description');
			const result = await engine.generateTaskFromQuery({
				query: 'SELECT name FROM products',
				databaseKey: DB_KEY,
				option: GptOptions.Default,
				lang: 'en',
				llmGateway: GATEWAY,
			});

			expect(result).toBe('default description');
			expect(stubClient.generate).toHaveBeenCalledTimes(1);
			const [config, request] = stubClient.generate.mock.calls[0];
			expect(config).toEqual(GATEWAY);
			expect(request.temperature).toBe(0);
			const roles = request.messages.map((m: any) => m.role);
			expect(roles).toEqual(['system', 'user']);
			expect(request.messages[0].parts[0].text).toContain(
				'You are a helpful assistant',
			);
			expect(request.messages[1].parts[0].text).toContain(
				'This is the query: SELECT name FROM products',
			);
			expect(request.messages[1].parts[0].text).toContain(
				'Respond in English.',
			);
			// every message is a valid UIMessage (id + parts)
			for (const message of request.messages) {
				expect(typeof message.id).toBe('string');
				expect(Array.isArray(message.parts)).toBe(true);
			}
		});

		it('applies the language directive for German', async () => {
			stubClient.generate.mockResolvedValue('x');
			await engine.generateTaskFromQuery({
				query: 'SELECT name FROM products',
				databaseKey: DB_KEY,
				option: GptOptions.Default,
				lang: 'de',
				llmGateway: GATEWAY,
			});
			const request = stubClient.generate.mock.calls[0][1];
			expect(request.messages[1].parts[0].text).toContain(
				'Antworte auf Deutsch.',
			);
		});

		it('throws when the database key is not registered in metadata', async () => {
			await expect(
				engine.generateTaskFromQuery({
					query: 'SELECT 1',
					databaseKey: 'unknown',
					option: GptOptions.Default,
					lang: 'en',
					llmGateway: GATEWAY,
				}),
			).rejects.toThrow('Error in accessing database tables.');
		});
	});

	describe('generateTaskFromQuery (creative)', () => {
		it('uses temperature 0.7', async () => {
			stubClient.generate.mockResolvedValue('creative description');
			const result = await engine.generateTaskFromQuery({
				query: 'SELECT name FROM products',
				databaseKey: DB_KEY,
				option: GptOptions.Creative,
				lang: 'en',
				llmGateway: GATEWAY,
			});
			expect(result).toBe('creative description');
			expect(stubClient.generate).toHaveBeenCalledTimes(1);
			expect(stubClient.generate.mock.calls[0][1].temperature).toBe(0.7);
		});
	});

	describe('generateTaskFromQuery (multi-step)', () => {
		it('executes the chained steps sequentially with the same intermediate-data flow', async () => {
			stubClient.generate.mockImplementation(async (_config, request) => {
				const first = request.messages[0].parts[0].text as string;
				if (first === 'You are a database expert.') return 'entity desc';
				if (first === 'You are a database and PostgreSQL expert.') {
					return `part description for ${request.messages[1].parts[0].text}`;
				}
				if (first === 'You are a SQL expert.') {
					const joined = request.messages[1].parts[0].text as string;
					return `final: ${joined}`;
				}
				throw new Error('unexpected step');
			});

			const result = await engine.generateTaskFromQuery({
				query:
					'SELECT name FROM products WHERE price > 10 ORDER BY name',
				databaseKey: DB_KEY,
				option: GptOptions.MultiStep,
				lang: 'en',
				llmGateway: GATEWAY,
			});

			// entity step + 4 clause parts (SELECT, FROM, WHERE, ORDER BY) + task step
			expect(stubClient.generate).toHaveBeenCalledTimes(6);
			const calls = stubClient.generate.mock.calls;
			for (const [config, request] of calls) {
				expect(config).toEqual(GATEWAY);
				expect(request.temperature).toBe(0);
			}
			// step 2 receives the entity description from step 1
			expect(calls[1][1].messages[1].parts[0].text).toContain('entity desc');
			// intermediate results flow into the final prompt
			expect(calls[5][1].messages[1].parts[0].text).toContain(
				'part description for Given the following query part: SELECT',
			);
			expect(result).toContain('final:');
		});

		it('throws a typed error wrapping gateway failures', async () => {
			stubClient.generate.mockRejectedValue(new Error('gateway down'));
			await expect(
				engine.generateTaskFromQuery({
					query: 'SELECT name FROM products',
					databaseKey: DB_KEY,
					option: GptOptions.MultiStep,
					lang: 'en',
					llmGateway: GATEWAY,
				}),
			).rejects.toThrow('Error in generating task description using GPT.');
		});
	});

	describe('generateNLGTaskFromTemplateTask', () => {
		it('post-processes a template description with one system message and one user message at temperature 0', async () => {
			stubClient.generate.mockResolvedValue('improved description');
			const result = await engine.generateNLGTaskFromTemplateTask(
				'SELECT name FROM products',
				'Retrieve all names.',
				DB_KEY,
				false,
				'en',
				GATEWAY,
			);
			expect(result).toBe('improved description');
			const [config, request] = stubClient.generate.mock.calls[0];
			expect(config).toEqual(GATEWAY);
			expect(request.temperature).toBe(0);
			expect(request.messages).toHaveLength(2);
			expect(request.messages[1].parts[0].text).toContain(
				'This is the task description that you should improve: Retrieve all names.',
			);
		});
	});
});
