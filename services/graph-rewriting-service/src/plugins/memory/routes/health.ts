import { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { okReply } from '../../../utils/response';

const healthcheck = async (
	request: FastifyRequest,
	reply: FastifyReply
): Promise<FastifyReply> => {
	if (request.dbGraphService) {
		return okReply(reply, { backend: 'memory' });
	}

	throw Error('In-memory graph service not found');
};

export default async function routes(fastify: FastifyInstance) {
	fastify.get('/health', healthcheck);
}
