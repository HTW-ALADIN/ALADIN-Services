/**
 * Interface implemented by each wire-format adapter (Vercel today; OpenAI /
 * Anthropic could be added later) so the HTTP/CLI layers and the gateway
 * client never need to know which wire format is in use.
 */
import type { GenerateRequest, GenerateResponse } from '../types.js';

export interface FormatAdapter<TRequest = unknown, TResponse = unknown> {
	parseRequest(input: TRequest): GenerateRequest;
	formatResponse(response: GenerateResponse): TResponse;
}
