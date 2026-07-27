import { GatewayClient } from '../../core/gateway-client.js';
import { getFormatAdapter } from '../../core/format/index.js';
import { readJsonInput, writeJsonOutput } from '../io.js';
import { config } from '../../config.js';

export interface GenerateCommandOptions {
	output?: string;
}

/**
 * `llm-gateway generate <input-file|-> [-o output-file]`
 *
 * Reads a chat request as JSON (from a file or stdin), calls LLM Gateway
 * (or a directly-specified custom provider via the `customProvider`
 * field), and writes the full JSON response to stdout or a file. This is
 * the primary integration point for workflows.
 *
 * The wire format defaults to the Vercel AI SDK `UIMessage` format; set
 * `"format": "openai-chat"` or `"format": "openai-responses"` in the input
 * JSON to use an OpenAI-compatible wire format instead.
 */
export async function generateCommand(
	inputPath: string | undefined,
	options: GenerateCommandOptions,
	client: GatewayClient = new GatewayClient(config.gateway)
): Promise<void> {
	const input = readJsonInput(inputPath) as { format?: string };
	const adapter = getFormatAdapter(input.format);
	const request = adapter.parseRequest(input);
	const result = await client.generate(request);
	writeJsonOutput(adapter.formatResponse(result), options.output);
}
