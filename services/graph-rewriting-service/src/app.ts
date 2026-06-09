import 'dotenv/config';

import fastify, { FastifyInstance } from 'fastify';
import fastifyStatic from '@fastify/static';
import path from 'path';
import { Server, IncomingMessage, ServerResponse } from 'http';

import Swagger from '@fastify/swagger';
import SwaggerUI from '@fastify/swagger-ui';

import cors from '@fastify/cors';

import { loggerConfig } from './config/logger';
import { getAppEnvConfig } from './config/env';
import { CorsOptions } from './config/cors';

import healthRoutes from './routes/health';

import neo4jConnector from './plugins/neo4j/index';
import memoryConnector from './plugins/memory/index';
import grsPlugin from './plugins/grs/index';

import { logger } from './utils/logger';

/**
 * Creates a fastify server instance
 */
export function buildServer(): FastifyInstance {
	const appEnvConfig = getAppEnvConfig();

	const server: FastifyInstance<Server, IncomingMessage, ServerResponse> =
		fastify({
			logger: loggerConfig[appEnvConfig.APP_ENV] ?? false,
			ignoreTrailingSlash: true,
		});

	logger.init(server.log);

	// Setup static file serving
	server.register(fastifyStatic, { root: path.join(__dirname, '/static') });

	// Setup CORS
	server.register(cors, CorsOptions);

	// Setup Swagger / SwaggerUI
	// Access Swagger page through <root-route>/documentation endpoint
	server.register(Swagger);
	server.register(SwaggerUI);

	server.register(healthRoutes);

	// Register database backend based on DB_BACKEND env var
	if (appEnvConfig.DB_BACKEND === 'neo4j') {
		server.register(neo4jConnector);
	} else {
		server.register(memoryConnector);
	}

	// Add grs plugin
	server.register(grsPlugin);

	return server;
}
