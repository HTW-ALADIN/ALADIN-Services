import fastifyPlugin from 'fastify-plugin';
import { FastifyInstance, FastifyPluginAsync } from 'fastify';

import healthRoutes from './routes/health';
import nodeRoutes from '../neo4j/routes/nodes';
import edgeRoutes from '../neo4j/routes/edges';

import GraphNodeSchema from '../../schemas/node.schema.json';
import GraphEdgeSchema from '../../schemas/edge.schema.json';
import GraphSchema from '../../schemas/graph.schema.json';
import GraphInstantiatedAttribute from '../../schemas/instantiated-attribute.schema.json';

import { InMemoryGraphService } from '../../service/db/memory/graph.service';
import { IGraphDB } from '../../service/db/types';

declare module 'fastify' {
	interface FastifyRequest {
		dbGraphService: IGraphDB | null;
	}
}

const memoryConnector: FastifyPluginAsync = async (
	fastify: FastifyInstance
) => {
	fastify.log.info(
		'Fastify InMemory Plugin: Setting up in-memory graph database'
	);

	const graphService = new InMemoryGraphService();

	fastify.decorateRequest<IGraphDB | null, 'dbGraphService'>(
		'dbGraphService',
		null
	);

	fastify.addHook('onRequest', (request, _reply, done) => {
		// All requests share the same in-memory graph instance
		request.dbGraphService = graphService;
		done();
	});

	fastify.log.debug('Fastify InMemory Plugin: Adding relevant schemas');
	fastify.addSchema(GraphNodeSchema);
	fastify.addSchema(GraphEdgeSchema);
	fastify.addSchema(GraphSchema);
	fastify.addSchema(GraphInstantiatedAttribute);

	fastify.log.debug('Fastify InMemory Plugin: Adding routes');
	fastify.register(healthRoutes, {
		prefix: '/memory',
	});

	fastify.register(nodeRoutes);
	fastify.register(edgeRoutes);
};

export default fastifyPlugin(memoryConnector, {
	name: 'fastify-memory-connector',
});
