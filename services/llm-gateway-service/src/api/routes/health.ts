import type { FastifyPluginAsync } from 'fastify';

const healthRoutes: FastifyPluginAsync = async (fastify) => {
	fastify.get(
		'/health',
		{
			schema: {
				tags: ['Health'],
				summary: 'Liveness probe',
				response: {
					200: {
						type: 'object',
						properties: { status: { type: 'string' } },
					},
				},
			},
		},
		async () => ({ status: 'ok' })
	);
};

export default healthRoutes;
