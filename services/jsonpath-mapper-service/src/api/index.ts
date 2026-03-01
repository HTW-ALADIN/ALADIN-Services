import { buildServer } from './server.js';

const PORT = parseInt(process.env.PORT ?? '3000', 10);
const HOST = process.env.HOST ?? '0.0.0.0';

async function start() {
	const fastify = await buildServer();

	try {
		await fastify.listen({ port: PORT, host: HOST });
		fastify.log.info(
			`OpenAPI spec (JSON) available at http://localhost:${PORT}/docs/json`
		);
		fastify.log.info(
			`OpenAPI spec (YAML) available at http://localhost:${PORT}/docs/yaml`
		);
		fastify.log.info(`Swagger UI available at http://localhost:${PORT}/docs`);
	} catch (err) {
		fastify.log.error(err);
		process.exit(1);
	}
}

start();
