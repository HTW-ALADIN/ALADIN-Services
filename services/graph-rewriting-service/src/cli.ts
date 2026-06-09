#!/usr/bin/env node

import 'dotenv/config';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import neo4j, { Driver } from 'neo4j-driver';
import { getNeo4jEnvConfig } from './plugins/neo4j/env';
import { Neo4jGraphService } from './service/db/neo4j/graph.service';
import { GraphTransformationService } from './service/grs/graph-transformation.service';

// ── Helpers ─────────────────────────────────────────────────────────────────

function usage(): never {
	const bin = 'graph-rewriting-service';
	console.error(`Usage: ${bin} <command> [options]

Graph Rewriting Service CLI — all API operations available from the command line.

Commands (graph transformation):
  transform <request.json>         Transform a hostgraph using rewrite rules
  find <request.json>              Find pattern matches in a hostgraph
  import <request.json>            Import a hostgraph into Neo4j

Commands (node CRUD):
  get-nodes                        List all nodes
  get-node <internalId>            Get a single node
  create-node <node.json>          Create a node
  delete-node <internalId>         Delete a single node
  delete-nodes                     Delete all nodes

Commands (edge CRUD):
  get-edge <internalId>            Get a single edge
  create-edge <edge.json>          Create an edge
  delete-edge <internalId>         Delete a single edge

Options:
  -o, --output <file>              Write result to file instead of stdout
  -h, --help                       Show this help message

Environment variables:
  NEO4J_URI        Neo4j Bolt URI       (default: bolt://localhost:7687)
  NEO4J_USERNAME   Neo4j username       (default: neo4j)
  NEO4J_PASSWORD   Neo4j password       (required)

Examples:
  ${bin} transform examples/data/grs/sierpinsky.json
  ${bin} transform examples/data/grs/sierpinsky.json -o result.json
  cat request.json | ${bin} transform -
  ${bin} get-nodes
  ${bin} get-node my-node-id
  ${bin} delete-nodes`);
	process.exit(1);
}

export function readJsonInput(pathArg: string): unknown {
	try {
		const raw =
			pathArg === '-'
				? readFileSync(0, 'utf-8')
				: readFileSync(resolve(pathArg), 'utf-8');
		return JSON.parse(raw);
	} catch (err) {
		console.error(`Error reading input "${pathArg}":`, (err as Error).message);
		process.exit(1);
	}
}

export function outputResult(data: unknown, outputPath?: string): void {
	const json = JSON.stringify(data, null, 2);
	if (outputPath) {
		writeFileSync(resolve(outputPath), json + '\n', 'utf-8');
	} else {
		console.log(json);
	}
}

function createDriver(): Driver {
	const config = getNeo4jEnvConfig();

	if (!config.NEO4J_URI || !config.NEO4J_USERNAME || !config.NEO4J_PASSWORD) {
		console.error(
			'Error: NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD must be set.\n' +
				'Set them as environment variables or in a .env file.'
		);
		process.exit(1);
	}

	return neo4j.driver(
		config.NEO4J_URI,
		neo4j.auth.basic(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
	);
}

// ── Argument parsing ────────────────────────────────────────────────────────

interface ParsedArgs {
	command: string;
	positional: string | undefined;
	outputPath: string | undefined;
}

export function parseArgs(argv: string[]): ParsedArgs {
	const args = argv.slice(2);

	if (args.includes('-h') || args.includes('--help') || args.length === 0) {
		usage();
	}

	const command = args[0];
	let positional: string | undefined;
	let outputPath: string | undefined;

	for (let i = 1; i < args.length; i++) {
		if (args[i] === '-o' || args[i] === '--output') {
			outputPath = args[++i];
			if (!outputPath) {
				console.error('Error: -o requires a file path argument');
				process.exit(1);
			}
		} else if (!positional) {
			positional = args[i];
		} else {
			console.error(`Error: unexpected argument "${args[i]}"`);
			usage();
		}
	}

	return { command, positional, outputPath };
}

// ── Command handlers ────────────────────────────────────────────────────────
// Each one directly reuses the same service classes that the HTTP handlers use.

export async function cmdTransform(
	graphService: Neo4jGraphService,
	inputPath: string,
	outputPath?: string
) {
	const body = readJsonInput(inputPath) as {
		hostgraph: Parameters<GraphTransformationService['transformGraph']>[0];
		rules?: Parameters<GraphTransformationService['transformGraph']>[1];
		sequence?: Parameters<GraphTransformationService['transformGraph']>[2];
		options?: Parameters<GraphTransformationService['transformGraph']>[3];
	};

	const grsService = new GraphTransformationService(graphService);
	const result = await grsService.transformGraph(
		body.hostgraph,
		body.rules || [],
		body.sequence || [],
		body.options || {}
	);
	outputResult(result, outputPath);
}

export async function cmdFind(
	graphService: Neo4jGraphService,
	inputPath: string,
	outputPath?: string
) {
	const body = readJsonInput(inputPath) as {
		hostgraph: Parameters<GraphTransformationService['matchPattern']>[0];
		rules?: Parameters<GraphTransformationService['matchPattern']>[1];
	};

	const grsService = new GraphTransformationService(graphService);
	const result = await grsService.matchPattern(
		body.hostgraph,
		body.rules || []
	);
	outputResult(result, outputPath);
}

export async function cmdImport(
	graphService: Neo4jGraphService,
	inputPath: string,
	outputPath?: string
) {
	const body = readJsonInput(inputPath) as {
		hostgraph: Parameters<GraphTransformationService['importHostgraph']>[0];
	};

	const grsService = new GraphTransformationService(graphService);
	const result = await grsService.importHostgraph(body.hostgraph);
	outputResult(result, outputPath);
}

export async function cmdGetNodes(
	graphService: Neo4jGraphService,
	outputPath?: string
) {
	const result = await graphService.getAllNodes();
	outputResult(result, outputPath);
}

export async function cmdGetNode(
	graphService: Neo4jGraphService,
	internalId: string,
	outputPath?: string
) {
	const result = await graphService.getNode(internalId);
	if (!result) {
		console.error(`Node "${internalId}" not found`);
		process.exit(1);
	}
	outputResult(result, outputPath);
}

export async function cmdCreateNode(
	graphService: Neo4jGraphService,
	inputPath: string,
	outputPath?: string
) {
	const body = readJsonInput(inputPath) as {
		key?: string;
		attributes?: Record<string, unknown>;
	};
	const result = await graphService.createNode(body.attributes || {}, body.key);
	outputResult(result, outputPath);
}

export async function cmdDeleteNode(
	graphService: Neo4jGraphService,
	internalId: string
) {
	await graphService.deleteNode(internalId);
	console.error(`Node "${internalId}" deleted`);
}

export async function cmdDeleteNodes(graphService: Neo4jGraphService) {
	await graphService.deleteAllNodes();
	console.error('All nodes deleted');
}

export async function cmdGetEdge(
	graphService: Neo4jGraphService,
	internalId: string,
	outputPath?: string
) {
	const result = await graphService.getEdge(internalId);
	if (!result) {
		console.error(`Edge "${internalId}" not found`);
		process.exit(1);
	}
	outputResult(result, outputPath);
}

export async function cmdCreateEdge(
	graphService: Neo4jGraphService,
	inputPath: string,
	outputPath?: string
) {
	const body = readJsonInput(inputPath) as {
		key: string;
		source: string;
		target: string;
		attributes?: Record<string, unknown>;
	};
	const result = await graphService.createEdge(
		body.source,
		body.target,
		body.key,
		body.attributes || {}
	);
	outputResult(result, outputPath);
}

export async function cmdDeleteEdge(
	graphService: Neo4jGraphService,
	internalId: string
) {
	await graphService.deleteEdge(internalId);
	console.error(`Edge "${internalId}" deleted`);
}

// ── Main ────────────────────────────────────────────────────────────────────

async function main() {
	const { command, positional, outputPath } = parseArgs(process.argv);

	const driver = createDriver();
	const graphService = new Neo4jGraphService(() => driver.session());

	try {
		switch (command) {
			// Graph transformation commands
			case 'transform': {
				if (!positional) {
					console.error(
						'Error: transform requires an input file path (or - for stdin)'
					);
					process.exit(1);
				}
				await cmdTransform(graphService, positional, outputPath);
				break;
			}
			case 'find': {
				if (!positional) {
					console.error(
						'Error: find requires an input file path (or - for stdin)'
					);
					process.exit(1);
				}
				await cmdFind(graphService, positional, outputPath);
				break;
			}
			case 'import': {
				if (!positional) {
					console.error(
						'Error: import requires an input file path (or - for stdin)'
					);
					process.exit(1);
				}
				await cmdImport(graphService, positional, outputPath);
				break;
			}

			// Node CRUD commands
			case 'get-nodes':
				await cmdGetNodes(graphService, outputPath);
				break;
			case 'get-node': {
				if (!positional) {
					console.error('Error: get-node requires a node internalId');
					process.exit(1);
				}
				await cmdGetNode(graphService, positional, outputPath);
				break;
			}
			case 'create-node': {
				if (!positional) {
					console.error(
						'Error: create-node requires an input file path (or - for stdin)'
					);
					process.exit(1);
				}
				await cmdCreateNode(graphService, positional, outputPath);
				break;
			}
			case 'delete-node': {
				if (!positional) {
					console.error('Error: delete-node requires a node internalId');
					process.exit(1);
				}
				await cmdDeleteNode(graphService, positional);
				break;
			}
			case 'delete-nodes':
				await cmdDeleteNodes(graphService);
				break;

			// Edge CRUD commands
			case 'get-edge': {
				if (!positional) {
					console.error('Error: get-edge requires an edge internalId');
					process.exit(1);
				}
				await cmdGetEdge(graphService, positional, outputPath);
				break;
			}
			case 'create-edge': {
				if (!positional) {
					console.error(
						'Error: create-edge requires an input file path (or - for stdin)'
					);
					process.exit(1);
				}
				await cmdCreateEdge(graphService, positional, outputPath);
				break;
			}
			case 'delete-edge': {
				if (!positional) {
					console.error('Error: delete-edge requires an edge internalId');
					process.exit(1);
				}
				await cmdDeleteEdge(graphService, positional);
				break;
			}

			default:
				console.error(`Unknown command: ${command}`);
				usage();
		}
	} catch (err) {
		console.error('Error:', (err as Error).message);
		process.exit(1);
	} finally {
		await driver.close();
	}
}

// Only run main() when this file is the entry point, not when imported for testing.
if (require.main === module) {
	main();
}
