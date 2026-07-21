import {
	createServer,
	type IncomingMessage,
	type Server,
	type ServerResponse,
} from 'http';

export type MockHandler = (
	body: any,
	req: IncomingMessage
) => { status: number; body: unknown };

/**
 * Minimal local HTTP server that mimics an OpenAI-compatible API
 * (`/chat/completions`, `/embeddings`) for exercising the real AI SDK
 * request/response pipeline without hitting the network.
 */
export class MockOpenAIServer {
	private server: Server | undefined;
	private handlers = new Map<string, MockHandler>();

	on(path: string, handler: MockHandler): void {
		this.handlers.set(path, handler);
	}

	async listen(): Promise<string> {
		this.server = createServer((req, res) => this.handleRequest(req, res));
		await new Promise<void>((resolve) =>
			this.server!.listen(0, '127.0.0.1', resolve)
		);
		const address = this.server.address();
		if (!address || typeof address === 'string') {
			throw new Error('Failed to determine mock server address');
		}
		return `http://127.0.0.1:${address.port}`;
	}

	async close(): Promise<void> {
		await new Promise<void>((resolve, reject) => {
			if (!this.server) return resolve();
			this.server.close((err) => (err ? reject(err) : resolve()));
		});
	}

	private handleRequest(req: IncomingMessage, res: ServerResponse): void {
		const chunks: Buffer[] = [];
		req.on('data', (chunk) => chunks.push(chunk));
		req.on('end', () => {
			const raw = Buffer.concat(chunks).toString('utf-8');
			const body = raw ? JSON.parse(raw) : undefined;
			const path = (req.url ?? '').split('?')[0];
			const handler = this.handlers.get(path);

			if (!handler) {
				res.writeHead(404, { 'Content-Type': 'application/json' });
				res.end(
					JSON.stringify({ error: { message: `No mock handler for ${path}` } })
				);
				return;
			}

			const { status, body: responseBody } = handler(body, req);
			res.writeHead(status, { 'Content-Type': 'application/json' });
			res.end(JSON.stringify(responseBody));
		});
	}
}

export function chatCompletionResponse(overrides: Record<string, any> = {}) {
	return {
		id: 'chatcmpl-123',
		object: 'chat.completion',
		created: 1700000000,
		model: 'gpt-4o',
		choices: [
			{
				index: 0,
				message: {
					role: 'assistant',
					content: 'Hello there',
					tool_calls: undefined,
				},
				finish_reason: 'stop',
			},
		],
		usage: { prompt_tokens: 3, completion_tokens: 4, total_tokens: 7 },
		...overrides,
	};
}

export function embeddingResponse(vectors: number[][]) {
	return {
		object: 'list',
		data: vectors.map((embedding, index) => ({
			object: 'embedding',
			embedding,
			index,
		})),
		model: 'text-embedding-3-small',
		usage: { prompt_tokens: vectors.length, total_tokens: vectors.length },
	};
}
