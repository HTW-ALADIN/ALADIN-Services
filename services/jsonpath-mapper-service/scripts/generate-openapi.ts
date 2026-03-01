/**
 * Generates the OpenAPI spec from the Fastify app and writes it to disk.
 *
 * Boots the server via buildServer(), calls server.ready() to trigger all
 * plugin and route registrations (@fastify/swagger collects schemas at that
 * point), then extracts the spec via server.swagger() and writes it to:
 *
 *   jsonpath-mapper-service.openapi.json   (default)
 *   jsonpath-mapper-service.openapi.yaml   (when --yaml is passed)
 *
 * Usage:
 *   tsx scripts/generate-openapi.ts [--yaml]
 */
import { writeFileSync } from 'fs';
import { buildServer } from '../src/api/server.js';

const yaml = process.argv.includes('--yaml');

async function generate() {
	const server = await buildServer();

	// ready() finalises all plugin registrations so that @fastify/swagger has
	// collected every route schema before we ask it for the spec.
	await server.ready();

	const spec = server.swagger({ yaml });
	const outFile = yaml
		? './jsonpath-mapper-service.openapi.yaml'
		: './jsonpath-mapper-service.openapi.json';
	const content = yaml
		? (spec as unknown as string)
		: JSON.stringify(spec, null, 2);

	writeFileSync(outFile, content + '\n');

	await server.close();
	console.log(`OpenAPI spec written to ${outFile}`);
}

generate();
