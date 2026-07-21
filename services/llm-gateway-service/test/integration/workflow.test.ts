import { expect } from 'chai';
import { mkdtempSync, readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import {
	MockOpenAIServer,
	chatCompletionResponse,
} from '../support/mock-openai-server.js';
import { runCli } from '../support/run-cli.js';

/**
 * End-to-end workflow simulation, driving the actual CLI as a real
 * subprocess (real argv parsing, env-driven config, stdin/stdout JSON I/O —
 * matching how an automated workflow would invoke this service):
 *
 *   1. `register-provider` — registers a custom OpenAI-compatible provider
 *      with LLM Gateway's admin API in one step (mocked here).
 *   2. `generate` — once registered, calls that provider *through the
 *      gateway* (by `{provider}/{model}`, no `customProvider` override
 *      needed) with a multi-turn message history and a system prompt.
 *
 * This exercises the full stack for both commands: CLI parsing, config
 * loading from env vars, JSON file I/O, the provider registry's admin-API
 * call, the Vercel format adapter, and the gateway client's real HTTP
 * request/response handling — against local mock HTTP servers standing in
 * for LLM Gateway's admin and inference APIs.
 */
describe('workflow: register a custom provider, then generate through the gateway', () => {
	let adminServer: MockOpenAIServer;
	let adminBaseUrl: string;
	let gatewayServer: MockOpenAIServer;
	let gatewayBaseUrl: string;
	let workdir: string;

	beforeEach(async () => {
		adminServer = new MockOpenAIServer();
		adminBaseUrl = await adminServer.listen();

		gatewayServer = new MockOpenAIServer();
		gatewayBaseUrl = await gatewayServer.listen();

		workdir = mkdtempSync(join(tmpdir(), 'llm-gateway-workflow-test-'));
	});

	afterEach(async () => {
		await adminServer.close();
		await gatewayServer.close();
	});

	it('registers a custom provider and then generates a response through it, with message history and a system prompt', async function () {
		this.timeout(20000);

		// -------------------------------------------------------------------
		// Step 1: the workflow registers a brand-new custom provider with the
		// gateway's admin API, in one CLI call.
		// -------------------------------------------------------------------
		let registrationRequestBody: unknown;
		adminServer.on('/keys/provider', (body) => {
			registrationRequestBody = body;
			return { status: 201, body: { id: 'pk_workflow_test' } };
		});

		const registerResultPath = join(workdir, 'register-result.json');
		const registerRun = await runCli(
			[
				'register-provider',
				'--name',
				'mycompany',
				'--base-url',
				'https://api.mycompany.com',
				'--api-key',
				'sk-custom-provider-key',
				'-o',
				registerResultPath,
			],
			{
				env: {
					LLM_GATEWAY_ADMIN_BASE_URL: adminBaseUrl,
					LLM_GATEWAY_ADMIN_TOKEN: 'llmgmk_test_master_key',
				},
			}
		);

		expect(
			registerRun.exitCode,
			`register-provider stderr: ${registerRun.stderr}`
		).to.equal(0);

		const registerResult = JSON.parse(
			readFileSync(registerResultPath, 'utf-8')
		);
		expect(registerResult).to.deep.equal({
			registered: true,
			mode: 'gateway-admin-api',
			message: 'Custom provider "mycompany" registered with LLM Gateway.',
		});

		// Confirm the CLI actually forwarded the provider connection details to
		// the gateway's admin API, not just echoing back a fabricated success.
		expect(registrationRequestBody).to.deep.equal({
			provider: 'custom',
			name: 'mycompany',
			baseUrl: 'https://api.mycompany.com',
			token: 'sk-custom-provider-key',
		});

		// -------------------------------------------------------------------
		// Step 2: now that the provider is registered, the workflow calls
		// `generate` addressing it through the gateway as "mycompany/<model>"
		// (no `customProvider` override needed), with a realistic multi-turn
		// conversation and a system prompt.
		// -------------------------------------------------------------------
		let generateRequestBody: any;
		gatewayServer.on('/chat/completions', (body) => {
			generateRequestBody = body;
			return {
				status: 200,
				body: chatCompletionResponse({
					model: 'mycompany/custom-gpt-4',
					choices: [
						{
							index: 0,
							message: { role: 'assistant', content: 'The result is 84.' },
							finish_reason: 'stop',
						},
					],
					usage: {
						prompt_tokens: 42,
						completion_tokens: 6,
						total_tokens: 48,
						cost: 0.00123,
					},
				}),
			};
		});

		const generateRequest = {
			provider: 'mycompany',
			model: 'custom-gpt-4',
			system:
				'You are a concise math assistant for an ALADIN workflow. Only answer with the final number.',
			messages: [
				{ role: 'user', content: 'What is 21 + 21?' },
				{ role: 'assistant', content: '21 + 21 is 42.' },
				{ role: 'user', content: 'Great — now multiply that result by 2.' },
			],
			temperature: 0.2,
			maxOutputTokens: 64,
		};

		const generateRequestPath = join(workdir, 'generate-request.json');
		const generateResultPath = join(workdir, 'generate-result.json');
		writeFileSync(generateRequestPath, JSON.stringify(generateRequest));

		const generateRun = await runCli(
			['generate', generateRequestPath, '-o', generateResultPath],
			{
				env: {
					LLM_GATEWAY_BASE_URL: gatewayBaseUrl,
					LLM_GATEWAY_API_KEY: 'llmgtwy_test_key',
				},
			}
		);

		expect(
			generateRun.exitCode,
			`generate stderr: ${generateRun.stderr}`
		).to.equal(0);

		// The gateway received the request routed through the *registered*
		// provider — addressed as "{provider}/{model}" — not a customProvider
		// bypass, and with the full conversation history plus the system
		// prompt intact.
		expect(generateRequestBody.model).to.equal('mycompany/custom-gpt-4');
		const roles = generateRequestBody.messages.map((m: any) => m.role);
		expect(roles).to.deep.equal(['system', 'user', 'assistant', 'user']);
		expect(generateRequestBody.messages[0].content).to.equal(
			'You are a concise math assistant for an ALADIN workflow. Only answer with the final number.'
		);
		expect(generateRequestBody.messages[1].content).to.equal(
			'What is 21 + 21?'
		);
		expect(generateRequestBody.messages[2].content).to.equal('21 + 21 is 42.');
		expect(generateRequestBody.messages[3].content).to.equal(
			'Great — now multiply that result by 2.'
		);

		// The CLI's final output reflects the full round trip: generated text,
		// usage/cost accounting, resolved provider/model, and that this went
		// through the gateway rather than a customProvider bypass.
		const generateResult = JSON.parse(
			readFileSync(generateResultPath, 'utf-8')
		);
		expect(generateResult.text).to.equal('The result is 84.');
		expect(generateResult.finishReason).to.equal('stop');
		expect(generateResult.provider).to.equal('mycompany');
		expect(generateResult.model).to.equal('custom-gpt-4');
		expect(generateResult.usage).to.deep.equal({
			inputTokens: 42,
			outputTokens: 6,
			totalTokens: 48,
		});
		expect(generateResult.cost).to.equal(0.00123);
		expect(generateResult.viaGatewayBypass).to.equal(false);
	});
});
