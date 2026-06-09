import fastifyPlugin from 'fastify-plugin';
import { FastifyInstance, FastifyPluginAsync } from 'fastify';
import neo4j, { Driver } from 'neo4j-driver';
import { getNeo4jEnvConfig } from './env';

import healthRoutes from './routes/health';
import nodeRoutes from './routes/nodes';
import edgeRoutes from './routes/edges';

import GraphNodeSchema from '../../schemas/node.schema.json';
import GraphEdgeSchema from '../../schemas/edge.schema.json';
import GraphSchema from '../../schemas/graph.schema.json';
import GraphInstantiatedAttribute from '../../schemas/instantiated-attribute.schema.json';

import { Neo4jGraphService } from '../../service/db/neo4j/graph.service';
import { IGraphDB } from '../../service/db/types';

declare module 'fastify' {
	interface FastifyInstance {
		neo4j: Driver;
	}

	interface FastifyRequest {
		dbGraphService: IGraphDB | null;
	}
}

const neo4jConnector: FastifyPluginAsync = async (fastify: FastifyInstance) => {
	fastify.log.info('Fastify Neo4j Plugin: Setting up Neo4j connector');

	const neo4jConfig = getNeo4jEnvConfig();

	if (
		!neo4jConfig.NEO4J_URI ||
		!neo4jConfig.NEO4J_USERNAME ||
		!neo4jConfig.NEO4J_PASSWORD
	) {
		fastify.log.error(
			'Fastify Neo4j Plugin: Neo4j ENV Vars are not set correctly'
		);
	}

	let driver: Driver | null = null;
	try {
		driver = neo4j.driver(
			neo4jConfig.NEO4J_URI,
			neo4j.auth.basic(neo4jConfig.NEO4J_USERNAME, neo4jConfig.NEO4J_PASSWORD)
		);

		const serverInfo = await driver.getServerInfo();
		if (serverInfo) {
			fastify.log.info(
				serverInfo,
				'Fastify Neo4j Plugin: Neo4j Connection established'
			);
		}
	} catch (error) {
		fastify.log.error(
			'Fastify Neo4j Plugin: Error connecting to Neo4j database',
			error
		);
	}
	if (driver) {
		if (!fastify?.neo4j) {
			fastify.decorate('neo4j', driver);
			fastify.decorateRequest<IGraphDB | null, 'dbGraphService'>(
				'dbGraphService',
				null
			);
		}

		fastify.addHook('onRequest', (request, reply, done) => {
			const neo4jGraphService = new Neo4jGraphService(() => driver.session());
			request.dbGraphService = neo4jGraphService;
			done();
		});

		fastify.addHook('onClose', (instance, done) => {
			driver?.close();
			done();
		});
	}

	fastify.log.debug('Fastify Neo4j Plugin: Adding relevant schemas');
	fastify.addSchema(GraphNodeSchema);
	fastify.addSchema(GraphEdgeSchema);
	fastify.addSchema(GraphSchema);
	fastify.addSchema(GraphInstantiatedAttribute);

	fastify.log.debug('Fastify Neo4j Plugin: Adding Neo4j routes');
	fastify.register(healthRoutes, {
		prefix: '/neo4j',
	});

	fastify.register(nodeRoutes);
	fastify.register(edgeRoutes);
};

export default fastifyPlugin(neo4jConnector, {
	name: 'fastify-neo4j-connector',
});
