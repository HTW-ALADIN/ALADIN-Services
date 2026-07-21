import { buildServer } from './server.js';
import { config } from '../config.js';

async function start() {
	const fastify = await buildServer();

	try {
		await fastify.listen({ port: config.port, host: config.host });
		fastify.log.info(
			`OpenAPI spec (JSON) available at http://localhost:${config.port}/docs/json`
		);
		fastify.log.info(
			`Swagger UI available at http://localhost:${config.port}/docs`
		);
	} catch (err) {
		fastify.log.error(err);
		process.exit(1);
	}
}

start();
