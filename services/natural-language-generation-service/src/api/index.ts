import { buildServer } from './server.js';
import { loadLimits } from '../config.js';

const host = process.env.HOST ?? '0.0.0.0';
const port = Number(process.env.PORT ?? '8000');

if (!Number.isInteger(port) || port < 1 || port > 65_535) {
	throw new Error('PORT must be an integer between 1 and 65535');
}

const server = await buildServer({ limits: loadLimits(), logger: true });
await server.listen({ host, port });
