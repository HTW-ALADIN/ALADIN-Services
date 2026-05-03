import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
	parseArgs,
	readJsonInput,
	outputResult,
	cmdTransform,
	cmdFind,
	cmdImport,
	cmdGetNodes,
	cmdGetNode,
	cmdCreateNode,
	cmdDeleteNode,
	cmdDeleteNodes,
	cmdGetEdge,
	cmdCreateEdge,
	cmdDeleteEdge,
} from './cli';
import { Neo4jGraphService } from './service/db/neo4j/graph.service';
import { GraphSchema } from './types/graph.schema';

// Mock fs module
vi.mock('node:fs', () => ({
	readFileSync: vi.fn(),
	writeFileSync: vi.fn(),
}));

// Mock dotenv (imported at top of cli.ts)
vi.mock('dotenv/config', () => ({}));

// Mock neo4j-driver (imported at top of cli.ts)
vi.mock('neo4j-driver', () => ({
	default: {
		driver: vi.fn(),
		auth: { basic: vi.fn() },
	},
}));

// ─── Sample data ────────────────────────────────────────────────────────────

const sampleGraph: GraphSchema = {
	options: { type: 'directed' },
	nodes: [
		{ key: 'A', attributes: { label: 'Start' } },
		{ key: 'B', attributes: { label: 'End' } },
	],
	edges: [{ key: 'e1', source: 'A', target: 'B', attributes: {} }],
};

const sampleTransformRequest = {
	hostgraph: sampleGraph,
	rules: [],
	sequence: [],
	options: {},
};

const sampleFindRequest = {
	hostgraph: sampleGraph,
	rules: [],
};

// ─── parseArgs ──────────────────────────────────────────────────────────────

describe('parseArgs', () => {
	let exitSpy: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		exitSpy = vi
			.spyOn(process, 'exit')
			.mockImplementation(() => undefined as never);
	});

	afterEach(() => {
		exitSpy.mockRestore();
	});

	test('parses command with positional arg', () => {
		const result = parseArgs(['node', 'cli.js', 'transform', 'input.json']);
		expect(result).toEqual({
			command: 'transform',
			positional: 'input.json',
			outputPath: undefined,
		});
	});

	test('parses command with -o flag', () => {
		const result = parseArgs([
			'node',
			'cli.js',
			'transform',
			'input.json',
			'-o',
			'output.json',
		]);
		expect(result).toEqual({
			command: 'transform',
			positional: 'input.json',
			outputPath: 'output.json',
		});
	});

	test('parses command with --output flag', () => {
		const result = parseArgs([
			'node',
			'cli.js',
			'find',
			'data.json',
			'--output',
			'result.json',
		]);
		expect(result).toEqual({
			command: 'find',
			positional: 'data.json',
			outputPath: 'result.json',
		});
	});

	test('parses command without positional (e.g. get-nodes)', () => {
		const result = parseArgs(['node', 'cli.js', 'get-nodes']);
		expect(result).toEqual({
			command: 'get-nodes',
			positional: undefined,
			outputPath: undefined,
		});
	});

	test('exits on --help', () => {
		parseArgs(['node', 'cli.js', '--help']);
		expect(exitSpy).toHaveBeenCalledWith(1);
	});

	test('exits on -h', () => {
		parseArgs(['node', 'cli.js', '-h']);
		expect(exitSpy).toHaveBeenCalledWith(1);
	});

	test('exits when no args provided', () => {
		parseArgs(['node', 'cli.js']);
		expect(exitSpy).toHaveBeenCalledWith(1);
	});

	test('exits on -o without value', () => {
		parseArgs(['node', 'cli.js', 'transform', 'input.json', '-o']);
		expect(exitSpy).toHaveBeenCalledWith(1);
	});

	test('exits on unexpected extra argument', () => {
		parseArgs(['node', 'cli.js', 'transform', 'input.json', 'extra-arg']);
		expect(exitSpy).toHaveBeenCalledWith(1);
	});
});

// ─── readJsonInput ──────────────────────────────────────────────────────────

describe('readJsonInput', () => {
	let exitSpy: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		exitSpy = vi
			.spyOn(process, 'exit')
			.mockImplementation(() => undefined as never);
		vi.mocked(readFileSync).mockReset();
	});

	afterEach(() => {
		exitSpy.mockRestore();
	});

	test('reads and parses a JSON file', () => {
		vi.mocked(readFileSync).mockReturnValue(JSON.stringify(sampleGraph));

		const result = readJsonInput('test.json');

		expect(readFileSync).toHaveBeenCalledWith(resolve('test.json'), 'utf-8');
		expect(result).toEqual(sampleGraph);
	});

	test('reads from stdin when path is "-"', () => {
		vi.mocked(readFileSync).mockReturnValue(JSON.stringify({ ok: true }));

		const result = readJsonInput('-');

		expect(readFileSync).toHaveBeenCalledWith(0, 'utf-8');
		expect(result).toEqual({ ok: true });
	});

	test('exits on read error', () => {
		vi.mocked(readFileSync).mockImplementation(() => {
			throw new Error('file not found');
		});

		readJsonInput('missing.json');
		expect(exitSpy).toHaveBeenCalledWith(1);
	});

	test('exits on invalid JSON', () => {
		vi.mocked(readFileSync).mockReturnValue('not valid json {{{');

		readJsonInput('bad.json');
		expect(exitSpy).toHaveBeenCalledWith(1);
	});
});

// ─── outputResult ───────────────────────────────────────────────────────────

describe('outputResult', () => {
	let consoleSpy: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		// eslint-disable-next-line @typescript-eslint/no-empty-function
		consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
		vi.mocked(writeFileSync).mockReset();
	});

	afterEach(() => {
		consoleSpy.mockRestore();
	});

	test('writes to stdout when no output path', () => {
		outputResult({ key: 'value' });
		expect(consoleSpy).toHaveBeenCalledWith(
			JSON.stringify({ key: 'value' }, null, 2)
		);
	});

	test('writes to file when output path given', () => {
		outputResult({ key: 'value' }, 'out.json');
		expect(writeFileSync).toHaveBeenCalledWith(
			resolve('out.json'),
			JSON.stringify({ key: 'value' }, null, 2) + '\n',
			'utf-8'
		);
		expect(consoleSpy).not.toHaveBeenCalled();
	});
});

// ─── Command handlers ───────────────────────────────────────────────────────

describe('CLI command handlers', () => {
	let mockGraphService: Neo4jGraphService;
	let consoleSpy: ReturnType<typeof vi.spyOn>;
	let consoleErrorSpy: ReturnType<typeof vi.spyOn>;
	let exitSpy: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		mockGraphService = {
			createNode: vi
				.fn()
				.mockResolvedValue({ key: 'new-node', attributes: {} }),
			getNode: vi.fn(),
			getAllNodes: vi.fn().mockResolvedValue(sampleGraph.nodes),
			deleteNode: vi.fn().mockResolvedValue(undefined),
			deleteAllNodes: vi.fn().mockResolvedValue([]),
			createEdge: vi.fn().mockResolvedValue({
				key: 'new-edge',
				source: 'A',
				target: 'B',
				attributes: {},
			}),
			getEdge: vi.fn(),
			deleteEdge: vi.fn().mockResolvedValue(undefined),
			getAllEdges: vi.fn().mockResolvedValue(sampleGraph.edges),
		} as unknown as Neo4jGraphService;

		// eslint-disable-next-line @typescript-eslint/no-empty-function
		consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
		// eslint-disable-next-line @typescript-eslint/no-empty-function
		consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
		exitSpy = vi
			.spyOn(process, 'exit')
			.mockImplementation(() => undefined as never);
		vi.mocked(readFileSync).mockReset();
		vi.mocked(writeFileSync).mockReset();
	});

	afterEach(() => {
		consoleSpy.mockRestore();
		consoleErrorSpy.mockRestore();
		exitSpy.mockRestore();
		vi.restoreAllMocks();
	});

	// ── transform ───────────────────────────────────────────────────────

	describe('cmdTransform', () => {
		test('calls transformGraph and outputs result', async () => {
			vi.mocked(readFileSync).mockReturnValue(
				JSON.stringify(sampleTransformRequest)
			);

			const transformResult = [sampleGraph];
			const mockTransformGraph = vi.fn().mockResolvedValue(transformResult);
			vi.spyOn(
				await import('./service/grs/graph-transformation.service'),
				'GraphTransformationService'
			).mockImplementation(
				() =>
					({
						transformGraph: mockTransformGraph,
					}) as unknown as InstanceType<
						typeof import('./service/grs/graph-transformation.service').GraphTransformationService
					>
			);

			await cmdTransform(mockGraphService, 'transform-req.json');

			expect(mockTransformGraph).toHaveBeenCalledWith(
				sampleTransformRequest.hostgraph,
				sampleTransformRequest.rules,
				sampleTransformRequest.sequence,
				sampleTransformRequest.options
			);
			expect(consoleSpy).toHaveBeenCalled();
		});

		test('writes to file with -o', async () => {
			vi.mocked(readFileSync).mockReturnValue(
				JSON.stringify(sampleTransformRequest)
			);

			const transformResult = [sampleGraph];
			vi.spyOn(
				await import('./service/grs/graph-transformation.service'),
				'GraphTransformationService'
			).mockImplementation(
				() =>
					({
						transformGraph: vi.fn().mockResolvedValue(transformResult),
					}) as unknown as InstanceType<
						typeof import('./service/grs/graph-transformation.service').GraphTransformationService
					>
			);

			await cmdTransform(mockGraphService, 'req.json', 'out.json');

			expect(writeFileSync).toHaveBeenCalledWith(
				resolve('out.json'),
				expect.any(String),
				'utf-8'
			);
		});
	});

	// ── find ────────────────────────────────────────────────────────────

	describe('cmdFind', () => {
		test('calls matchPattern and outputs result', async () => {
			vi.mocked(readFileSync).mockReturnValue(
				JSON.stringify(sampleFindRequest)
			);

			const findResult = [sampleGraph];
			const mockMatchPattern = vi.fn().mockResolvedValue(findResult);
			vi.spyOn(
				await import('./service/grs/graph-transformation.service'),
				'GraphTransformationService'
			).mockImplementation(
				() =>
					({
						matchPattern: mockMatchPattern,
					}) as unknown as InstanceType<
						typeof import('./service/grs/graph-transformation.service').GraphTransformationService
					>
			);

			await cmdFind(mockGraphService, 'find-req.json');

			expect(mockMatchPattern).toHaveBeenCalledWith(
				sampleFindRequest.hostgraph,
				sampleFindRequest.rules
			);
			expect(consoleSpy).toHaveBeenCalled();
		});
	});

	// ── import ──────────────────────────────────────────────────────────

	describe('cmdImport', () => {
		test('calls importHostgraph and outputs result', async () => {
			vi.mocked(readFileSync).mockReturnValue(
				JSON.stringify({ hostgraph: sampleGraph })
			);

			const importResult = sampleGraph;
			const mockImportHostgraph = vi.fn().mockResolvedValue(importResult);
			vi.spyOn(
				await import('./service/grs/graph-transformation.service'),
				'GraphTransformationService'
			).mockImplementation(
				() =>
					({
						importHostgraph: mockImportHostgraph,
					}) as unknown as InstanceType<
						typeof import('./service/grs/graph-transformation.service').GraphTransformationService
					>
			);

			await cmdImport(mockGraphService, 'import-req.json');

			expect(mockImportHostgraph).toHaveBeenCalledWith(sampleGraph);
			expect(consoleSpy).toHaveBeenCalled();
		});
	});

	// ── node CRUD ───────────────────────────────────────────────────────

	describe('cmdGetNodes', () => {
		test('lists all nodes', async () => {
			await cmdGetNodes(mockGraphService);

			expect(mockGraphService.getAllNodes).toHaveBeenCalled();
			expect(consoleSpy).toHaveBeenCalledWith(
				JSON.stringify(sampleGraph.nodes, null, 2)
			);
		});
	});

	describe('cmdGetNode', () => {
		test('returns a node by id', async () => {
			const node = { key: 'A', attributes: { label: 'Start' } };
			vi.mocked(mockGraphService.getNode).mockResolvedValue(node);

			await cmdGetNode(mockGraphService, 'A');

			expect(mockGraphService.getNode).toHaveBeenCalledWith('A');
			expect(consoleSpy).toHaveBeenCalledWith(JSON.stringify(node, null, 2));
		});

		test('exits with error when node not found', async () => {
			vi.mocked(mockGraphService.getNode).mockResolvedValue(undefined);

			await cmdGetNode(mockGraphService, 'missing');

			expect(exitSpy).toHaveBeenCalledWith(1);
		});
	});

	describe('cmdCreateNode', () => {
		test('creates a node from JSON file', async () => {
			const nodeInput = { key: 'C', attributes: { label: 'New' } };
			vi.mocked(readFileSync).mockReturnValue(JSON.stringify(nodeInput));

			await cmdCreateNode(mockGraphService, 'node.json');

			expect(mockGraphService.createNode).toHaveBeenCalledWith(
				{ label: 'New' },
				'C'
			);
			expect(consoleSpy).toHaveBeenCalled();
		});

		test('creates a node with empty attributes when not provided', async () => {
			vi.mocked(readFileSync).mockReturnValue(JSON.stringify({}));

			await cmdCreateNode(mockGraphService, 'minimal.json');

			expect(mockGraphService.createNode).toHaveBeenCalledWith({}, undefined);
		});
	});

	describe('cmdDeleteNode', () => {
		test('deletes a node by id', async () => {
			await cmdDeleteNode(mockGraphService, 'A');

			expect(mockGraphService.deleteNode).toHaveBeenCalledWith('A');
			expect(consoleErrorSpy).toHaveBeenCalledWith('Node "A" deleted');
		});
	});

	describe('cmdDeleteNodes', () => {
		test('deletes all nodes', async () => {
			await cmdDeleteNodes(mockGraphService);

			expect(mockGraphService.deleteAllNodes).toHaveBeenCalled();
			expect(consoleErrorSpy).toHaveBeenCalledWith('All nodes deleted');
		});
	});

	// ── edge CRUD ───────────────────────────────────────────────────────

	describe('cmdGetEdge', () => {
		test('returns an edge by id', async () => {
			const edge = { key: 'e1', source: 'A', target: 'B', attributes: {} };
			vi.mocked(mockGraphService.getEdge).mockResolvedValue(edge);

			await cmdGetEdge(mockGraphService, 'e1');

			expect(mockGraphService.getEdge).toHaveBeenCalledWith('e1');
			expect(consoleSpy).toHaveBeenCalledWith(JSON.stringify(edge, null, 2));
		});

		test('exits with error when edge not found', async () => {
			vi.mocked(mockGraphService.getEdge).mockResolvedValue(undefined);

			await cmdGetEdge(mockGraphService, 'missing');

			expect(exitSpy).toHaveBeenCalledWith(1);
		});
	});

	describe('cmdCreateEdge', () => {
		test('creates an edge from JSON file', async () => {
			const edgeInput = {
				key: 'e2',
				source: 'A',
				target: 'B',
				attributes: { weight: 5 },
			};
			vi.mocked(readFileSync).mockReturnValue(JSON.stringify(edgeInput));

			await cmdCreateEdge(mockGraphService, 'edge.json');

			expect(mockGraphService.createEdge).toHaveBeenCalledWith('A', 'B', 'e2', {
				weight: 5,
			});
			expect(consoleSpy).toHaveBeenCalled();
		});

		test('creates an edge with empty attributes when not provided', async () => {
			const edgeInput = { key: 'e3', source: 'X', target: 'Y' };
			vi.mocked(readFileSync).mockReturnValue(JSON.stringify(edgeInput));

			await cmdCreateEdge(mockGraphService, 'edge-minimal.json');

			expect(mockGraphService.createEdge).toHaveBeenCalledWith(
				'X',
				'Y',
				'e3',
				{}
			);
		});
	});

	describe('cmdDeleteEdge', () => {
		test('deletes an edge by id', async () => {
			await cmdDeleteEdge(mockGraphService, 'e1');

			expect(mockGraphService.deleteEdge).toHaveBeenCalledWith('e1');
			expect(consoleErrorSpy).toHaveBeenCalledWith('Edge "e1" deleted');
		});
	});
});
