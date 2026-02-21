import fastifyPlugin from 'fastify-plugin';
import { FastifyInstance, FastifyPluginAsync } from 'fastify';

import GraphRewritingRule from '../../schemas/rewrite-rule.schema.json';
import GraphFindRule from '../../schemas/find-rule.schema.json';
import RequestTransformSchema from '../../schemas/request-transform.schema.json';
import RequestFindSchema from '../../schemas/request-find.schema.json';
import PatternnodeSchema from '../../schemas/patternnode.schema.json';
import PatterngraphSchema from '../../schemas/patterngraph.schema.json';
import ReplacementnodeSchema from '../../schemas/replacementnode.schema.json';
import ReplacementedgeSchema from '../../schemas/replacementedge.schema.json';
import ReplacementgraphSchema from '../../schemas/replacementgraph.schema.json';
import RewritingRuleProcessingConfigSchema from '../../schemas/run-config.schema.json';
import RewritingNestedRuleProcessingConfigSchema from '../../schemas/run-nested-config.schema.json';

import grsRoutes from '../grs/routes/grs';

const grsPlugin: FastifyPluginAsync = async (fastify: FastifyInstance) => {
	fastify.log.info('GraphTransformation Plugin: Setting up plugin');
	if (fastify.hasRequestDecorator('dbGraphService')) {
		fastify.register(grsRoutes);
	} else {
		fastify.log.error("GraphTransformation Plugin: Can't find datbase service");
	}

	fastify.log.debug('GraphTransformation Plugin: Adding relevant schemas');
	fastify.addSchema(RewritingRuleProcessingConfigSchema);
	fastify.addSchema(RewritingNestedRuleProcessingConfigSchema);
	fastify.addSchema(PatternnodeSchema);
	fastify.addSchema(PatterngraphSchema);
	fastify.addSchema(ReplacementedgeSchema);
	fastify.addSchema(ReplacementnodeSchema);
	fastify.addSchema(ReplacementgraphSchema);
	fastify.addSchema(GraphRewritingRule);
	fastify.addSchema(GraphFindRule);
	fastify.addSchema(RequestTransformSchema);
	fastify.addSchema(RequestFindSchema);
};

export default fastifyPlugin(grsPlugin, {
	name: 'fastify-grs',
});
