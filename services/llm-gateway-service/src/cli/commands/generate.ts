import { GatewayClient } from '../../core/gateway-client.js';
import {
	vercelFormatAdapter,
	type VercelGenerateRequest,
} from '../../core/format/vercel.js';
import { readJsonInput, writeJsonOutput } from '../io.js';
import { config } from '../../config.js';

export interface GenerateCommandOptions {
	output?: string;
}

/**
 * `llm-gateway generate <input-file|-> [-o output-file]`
 *
 * Reads a Vercel AI SDK-format request as JSON (from a file or stdin),
 * calls LLM Gateway (or a directly-specified custom provider via the
 * `customProvider` field), and writes the full JSON response to stdout or a
 * file. This is the primary integration point for workflows.
 */
export async function generateCommand(
	inputPath: string | undefined,
	options: GenerateCommandOptions,
	client: GatewayClient = new GatewayClient(config.gateway)
): Promise<void> {
	const input = readJsonInput(inputPath) as VercelGenerateRequest;
	const request = vercelFormatAdapter.parseRequest(input);
	const result = await client.generate(request);
	writeJsonOutput(vercelFormatAdapter.formatResponse(result), options.output);
}
