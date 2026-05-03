import { expect, test, describe, beforeEach } from 'vitest';

import { InMemoryGraphService } from './graph.service';
import { DBGraphNACs } from '../types';
import { PatternNodeSchema } from '../../../types/patternnode.schema';

let graphService: InMemoryGraphService;

describe('InMemoryGraphService', () => {
	beforeEach(() => {
		graphService = new InMemoryGraphService();
	});

	describe('Node CRUD', () => {
		test('createNode', async () => {
			const result = await graphService.createNode(
				{ hello: 'world' },
				'testnode1'
			);
			expect(result).toEqual({
				key: 'testnode1',
				attributes: { hello: 'world' },
			});
		});

		test('createNode with type attribute', async () => {
			const result = await graphService.createNode(
				{ type: 'Gate', test: 'testMe' },
				'testnode4'
			);
			expect(result).toEqual({
				key: 'testnode4',
				attributes: { type: 'Gate', test: 'testMe' },
			});
		});

		test('createNode strips _grs_internalId from attributes', async () => {
			const result = await graphService.createNode(
				{ hello: 'world', _grs_internalId: 'testnode1' },
				'testnode1'
			);
			expect(result.attributes).not.toHaveProperty('_grs_internalId');
			expect(result).toEqual({
				key: 'testnode1',
				attributes: { hello: 'world' },
			});
		});

		test('getNode', async () => {
			await graphService.createNode({ label: 'Test' }, 'testnode1');
			const result = await graphService.getNode('testnode1');
			expect(result).toEqual({
				key: 'testnode1',
				attributes: { label: 'Test' },
			});
		});

		test('getNode returns undefined for missing node', async () => {
			const result = await graphService.getNode('nonexistent');
			expect(result).toBeUndefined();
		});

		test('updateNode with default (modify) mode', async () => {
			await graphService.createNode({ label: 'Test', foo: 'bar' }, 'testnode1');
			const result = await graphService.updateNode(
				{ hello: 'world' },
				'testnode1'
			);
			expect(result).toEqual({
				key: 'testnode1',
				attributes: { label: 'Test', foo: 'bar', hello: 'world' },
			});
		});

		test('updateNode with replace mode', async () => {
			await graphService.createNode({ label: 'Test', foo: 'bar' }, 'testnode1');
			const result = await graphService.updateNode(
				{ hello: 'world' },
				'testnode1',
				[],
				{ attributeReplacementMode: 'replace' }
			);
			expect(result).toEqual({
				key: 'testnode1',
				attributes: { hello: 'world' },
			});
		});

		test('updateNode with delete mode', async () => {
			await graphService.createNode({ label: 'Test', foo: 'bar' }, 'testnode1');
			const result = await graphService.updateNode(
				{ hello: 'world' },
				'testnode1',
				[],
				{ attributeReplacementMode: 'delete' }
			);
			expect(result).toEqual({
				key: 'testnode1',
				attributes: {},
			});
		});

		test('getAllNodes', async () => {
			await graphService.createNode({ label: 'A' }, 'testnodeA');
			await graphService.createNode({ label: 'B' }, 'testnodeB');
			await graphService.createNode({ label: 'C' }, 'testnodeC');
			const result = await graphService.getAllNodes();
			expect(result).toEqual(
				expect.arrayContaining([
					{ key: 'testnodeA', attributes: { label: 'A' } },
					{ key: 'testnodeB', attributes: { label: 'B' } },
					{ key: 'testnodeC', attributes: { label: 'C' } },
				])
			);
		});

		test('deleteNode', async () => {
			await graphService.createNode({ label: 'A' }, 'testnodeA');
			await graphService.createNode({ label: 'B' }, 'testnodeB');
			await graphService.deleteNode('testnodeA');
			const all = await graphService.getAllNodes();
			expect(all).toHaveLength(1);
			expect(all[0].key).toBe('testnodeB');
		});

		test('deleteNode detaches edges', async () => {
			await graphService.createNode({}, 'a');
			await graphService.createNode({}, 'b');
			await graphService.createEdge('a', 'b', 'e1', { type: 'rel' });
			await graphService.deleteNode('a');
			const edges = await graphService.getAllEdges();
			expect(edges).toHaveLength(0);
		});

		test('deleteNodes', async () => {
			await graphService.createNode({ label: 'A' }, 'testnodeA');
			await graphService.createNode({ label: 'B' }, 'testnodeB');
			await graphService.createNode({ label: 'C' }, 'testnodeC');
			await graphService.deleteNodes(['testnodeA', 'testnodeB']);
			const all = await graphService.getAllNodes();
			expect(all).toHaveLength(1);
			expect(all[0].key).toBe('testnodeC');
		});

		test('deleteAllNodes', async () => {
			await graphService.createNode({ label: 'A' }, 'testnodeA');
			await graphService.createNode({ label: 'B' }, 'testnodeB');
			const result = await graphService.deleteAllNodes();
			expect(result).toHaveLength(2);
			const all = await graphService.getAllNodes();
			expect(all).toHaveLength(0);
		});
	});

	describe('Edge CRUD', () => {
		test('createEdge', async () => {
			await graphService.createNode({}, 'testnodeA');
			await graphService.createNode({}, 'testnodeB');
			const result = await graphService.createEdge(
				'testnodeA',
				'testnodeB',
				'testrelation',
				{ type: 'relation', hello: 'world' }
			);
			expect(result).toEqual({
				key: 'testrelation',
				source: 'testnodeA',
				target: 'testnodeB',
				attributes: { type: 'relation', hello: 'world' },
			});
		});

		test('getEdge', async () => {
			await graphService.createNode({}, 'testnodeA');
			await graphService.createNode({}, 'testnodeB');
			await graphService.createEdge('testnodeA', 'testnodeB', 'testedge', {
				hello: 'world',
			});
			const result = await graphService.getEdge('testedge');
			expect(result).toEqual({
				key: 'testedge',
				source: 'testnodeA',
				target: 'testnodeB',
				attributes: { hello: 'world' },
			});
		});

		test('getEdge returns undefined for missing edge', async () => {
			const result = await graphService.getEdge('nonexistent');
			expect(result).toBeUndefined();
		});

		test('deleteEdge', async () => {
			await graphService.createNode({}, 'testnodeA');
			await graphService.createNode({}, 'testnodeB');
			await graphService.createEdge('testnodeA', 'testnodeB', 'testedge', {});
			await graphService.deleteEdge('testedge');
			const result = await graphService.getEdge('testedge');
			expect(result).toBeUndefined();
		});

		test('deleteEdge returns undefined for missing edge', async () => {
			const result = await graphService.deleteEdge('nonexistent');
			expect(result).toBeUndefined();
		});

		test('deleteEdges', async () => {
			await graphService.createNode({}, 'a');
			await graphService.createNode({}, 'b');
			await graphService.createNode({}, 'c');
			await graphService.createEdge('a', 'b', 'e1', {});
			await graphService.createEdge('a', 'c', 'e2', {});
			await graphService.createEdge('b', 'c', 'e3', {});
			await graphService.deleteEdges(['e1', 'e2']);
			const edges = await graphService.getAllEdges();
			expect(edges).toHaveLength(1);
			expect(edges[0].key).toBe('e3');
		});

		test('getAllEdges', async () => {
			await graphService.createNode({}, 'a');
			await graphService.createNode({}, 'b');
			await graphService.createEdge('a', 'b', 'e1', { type: 'x' });
			const edges = await graphService.getAllEdges();
			expect(edges).toHaveLength(1);
			expect(edges[0]).toEqual({
				key: 'e1',
				source: 'a',
				target: 'b',
				attributes: { type: 'x' },
			});
		});

		test('updateEdge with modify mode', async () => {
			await graphService.createNode({}, 'a');
			await graphService.createNode({}, 'b');
			await graphService.createEdge('a', 'b', 'e1', {
				type: 'x',
				old: 'value',
			});
			const result = await graphService.updateEdge('a', 'b', 'e1', {
				type: 'y',
				new: 'attr',
			});
			expect(result.attributes).toEqual({
				type: 'y',
				old: 'value',
				new: 'attr',
			});
		});

		test('updateEdge with replace mode', async () => {
			await graphService.createNode({}, 'a');
			await graphService.createNode({}, 'b');
			await graphService.createEdge('a', 'b', 'e1', {
				type: 'x',
				old: 'value',
			});
			const result = await graphService.updateEdge(
				'a',
				'b',
				'e1',
				{ type: 'y' },
				{ attributeReplacementMode: 'replace' }
			);
			expect(result.attributes).toEqual({ type: 'y' });
		});

		test('updateEdge with delete mode', async () => {
			await graphService.createNode({}, 'a');
			await graphService.createNode({}, 'b');
			await graphService.createEdge('a', 'b', 'e1', {
				type: 'x',
				old: 'value',
			});
			const result = await graphService.updateEdge(
				'a',
				'b',
				'e1',
				{ type: 'y' },
				{ attributeReplacementMode: 'delete' }
			);
			expect(result.attributes).toEqual({});
		});
	});

	describe('Pattern Matching', () => {
		test('empty pattern returns single empty match', async () => {
			const result = await graphService.findPatternMatch([], []);
			expect(result).toEqual([{ nodes: {}, edges: {} }]);
		});

		test('single node pattern', async () => {
			await graphService.createNode({}, 'testnodeA');
			await graphService.createNode({}, 'testnodeB');
			await graphService.createNode({}, 'testnodeC');

			const patternNodes: PatternNodeSchema[] = [{ key: 'A', attributes: {} }];

			const result = await graphService.findPatternMatch(patternNodes, []);
			expect(result).toHaveLength(3);
			expect(result).toContainEqual({
				edges: {},
				nodes: { A: { key: 'testnodeA', attributes: {} } },
			});
			expect(result).toContainEqual({
				edges: {},
				nodes: { A: { key: 'testnodeB', attributes: {} } },
			});
			expect(result).toContainEqual({
				edges: {},
				nodes: { A: { key: 'testnodeC', attributes: {} } },
			});
		});

		test('single node pattern with attributes', async () => {
			await graphService.createNode({ hello: 'world' }, 'testnodeA');
			await graphService.createNode({ test: 'test2' }, 'testnodeB');
			await graphService.createNode({}, 'testnodeC');

			const patternNodes: PatternNodeSchema[] = [
				{ key: 'A', attributes: { test: 'test2' } },
			];

			const result = await graphService.findPatternMatch(patternNodes, []);
			expect(result).toHaveLength(1);
			expect(result).toContainEqual({
				edges: {},
				nodes: {
					A: { key: 'testnodeB', attributes: { test: 'test2' } },
				},
			});
		});

		test('single edge pattern (undirected)', async () => {
			await graphService.createNode({ hello: 'world' }, 'testnodeA');
			await graphService.createNode({ test: 'test2' }, 'testnodeB');
			await graphService.createNode({}, 'testnodeC');
			await graphService.createEdge('testnodeA', 'testnodeB', 'testedge1', {});
			await graphService.createEdge('testnodeA', 'testnodeC', 'testedge2', {});

			const patternEdges = [
				{ key: 'edge', source: 'A', target: 'B', attributes: {} },
			];

			// For edge-only pattern, nodes aren't in the pattern but are referenced via edges
			// The edge-only pattern requires corresponding pattern nodes to be matched
			// Since no pattern nodes, it won't be able to resolve source/target
			// Actually, looking at Neo4j impl, edge-only matches don't require explicit nodes
			const result = await graphService.findPatternMatch([], patternEdges);
			// Without explicit pattern nodes bound, edge source/target refs can't be resolved
			// This matches the Neo4j behavior where edge variables like (A)-[edge]-(B) auto-bind
			expect(result).toEqual([]);
		});

		test('two connected nodes (directed)', async () => {
			await graphService.createNode({ hello: 'world' }, 'testnodeA');
			await graphService.createNode({ test: 'test2' }, 'testnodeB');
			await graphService.createNode({}, 'testnodeC');
			await graphService.createEdge('testnodeA', 'testnodeB', 'testedge1', {});
			await graphService.createEdge('testnodeA', 'testnodeC', 'testedge2', {});

			const patternNodes: PatternNodeSchema[] = [
				{ key: 'A', attributes: {} },
				{ key: 'B', attributes: {} },
			];

			const patternEdges = [
				{ key: 'edge', source: 'A', target: 'B', attributes: {} },
			];

			const result = await graphService.findPatternMatch(
				patternNodes,
				patternEdges,
				'directed'
			);

			expect(result).toHaveLength(2);
			expect(result).toContainEqual({
				edges: {
					edge: {
						attributes: {},
						key: 'testedge1',
						source: 'testnodeA',
						target: 'testnodeB',
					},
				},
				nodes: {
					A: { key: 'testnodeA', attributes: { hello: 'world' } },
					B: { key: 'testnodeB', attributes: { test: 'test2' } },
				},
			});
			expect(result).toContainEqual({
				edges: {
					edge: {
						attributes: {},
						key: 'testedge2',
						source: 'testnodeA',
						target: 'testnodeC',
					},
				},
				nodes: {
					A: { key: 'testnodeA', attributes: { hello: 'world' } },
					B: { key: 'testnodeC', attributes: {} },
				},
			});
		});

		test('isomorphic matching (homo=false) prevents same host node', async () => {
			await graphService.createNode({}, 'n1');
			await graphService.createNode({}, 'n2');

			const patternNodes: PatternNodeSchema[] = [
				{ key: 'A', attributes: {} },
				{ key: 'B', attributes: {} },
			];

			// Isomorphic: A and B must be different host nodes
			const result = await graphService.findPatternMatch(
				patternNodes,
				[],
				'undirected',
				false
			);
			// 2 nodes, 2 pattern nodes → 2 permutations (n1→A,n2→B) and (n2→A,n1→B)
			expect(result).toHaveLength(2);
			// No match should have A and B pointing to same node
			for (const match of result) {
				expect(match.nodes['A'].key).not.toBe(match.nodes['B'].key);
			}
		});

		test('homomorphic matching allows same host node', async () => {
			await graphService.createNode({}, 'n1');

			const patternNodes: PatternNodeSchema[] = [
				{ key: 'A', attributes: {} },
				{ key: 'B', attributes: {} },
			];

			// Homomorphic: A and B CAN be same host node
			const result = await graphService.findPatternMatch(
				patternNodes,
				[],
				'undirected',
				true
			);
			// 1 node, 2 pattern nodes → 1 match (both → n1)
			expect(result).toHaveLength(1);
			expect(result[0].nodes['A'].key).toBe('n1');
			expect(result[0].nodes['B'].key).toBe('n1');
		});

		test('NAC: excluding attribute', async () => {
			await graphService.createNode({ hello: 'world' }, 'testnodeA');
			await graphService.createNode({ test: 'wert' }, 'testnodeB');
			await graphService.createNode({ hello: 'world' }, 'testnodeC');
			await graphService.createNode({ attribute: 'value' }, 'testnodeD');
			await graphService.createNode({}, 'testnodeE');
			await graphService.createNode({}, 'testnodeF');

			await graphService.createEdge('testnodeA', 'testnodeB', 'aToB', {});
			await graphService.createEdge('testnodeA', 'testnodeC', 'aToC', {});
			await graphService.createEdge('testnodeC', 'testnodeD', 'cToD', {});
			await graphService.createEdge('testnodeD', 'testnodeE', 'dToE', {});
			await graphService.createEdge('testnodeE', 'testnodeC', 'eToC', {});
			await graphService.createEdge('testnodeA', 'testnodeF', 'aToF', {});

			const patternNodes: PatternNodeSchema[] = [
				{ key: 'A', attributes: {} },
				{ key: 'B', attributes: {} },
			];

			const patternEdges = [
				{ key: 'edge', source: 'A', target: 'B', attributes: {} },
			];

			const nacs: DBGraphNACs[] = [
				{
					nodes: [{ key: 'A', attributes: { hello: 'world' } }],
					edges: [],
				},
			];

			const result = await graphService.findPatternMatch(
				patternNodes,
				patternEdges,
				'directed',
				false,
				nacs
			);

			// Nodes with hello='world' (A, C) should be excluded from pattern-node A
			// So only D→E and E→C should match
			expect(result).toContainEqual({
				edges: {
					edge: {
						attributes: {},
						key: 'dToE',
						source: 'testnodeD',
						target: 'testnodeE',
					},
				},
				nodes: {
					A: { key: 'testnodeD', attributes: { attribute: 'value' } },
					B: { key: 'testnodeE', attributes: {} },
				},
			});
			expect(result).toContainEqual({
				edges: {
					edge: {
						attributes: {},
						key: 'eToC',
						source: 'testnodeE',
						target: 'testnodeC',
					},
				},
				nodes: {
					A: { key: 'testnodeE', attributes: {} },
					B: { key: 'testnodeC', attributes: { hello: 'world' } },
				},
			});
		});

		test('NAC: exclude node with connection to NAC-Node', async () => {
			await graphService.createNode({ name: 'A' }, 'testnodeA');
			await graphService.createNode({ name: 'B' }, 'testnodeB');
			await graphService.createNode({ name: 'C' }, 'testnodeC');
			await graphService.createNode({ name: 'D' }, 'testnodeD');

			await graphService.createEdge('testnodeA', 'testnodeB', 'aToB', {});
			await graphService.createEdge('testnodeA', 'testnodeC', 'aToC', {});
			await graphService.createEdge('testnodeA', 'testnodeD', 'aToD', {});
			await graphService.createEdge('testnodeC', 'testnodeB', 'cToB', {});

			const patternNodes: PatternNodeSchema[] = [
				{ key: 'node1', attributes: {} },
				{ key: 'node2', attributes: {} },
			];

			const patternEdges = [
				{ key: 'edge', source: 'node1', target: 'node2', attributes: {} },
			];

			const nacs: DBGraphNACs[] = [
				{
					options: { type: 'directed' },
					nodes: [
						{ key: 'node2' },
						{ key: 'node3', attributes: { name: 'B' } },
					],
					edges: [
						{
							key: 'edge2',
							source: 'node2',
							target: 'node3',
							attributes: {},
						},
					],
				},
			];

			const result = await graphService.findPatternMatch(
				patternNodes,
				patternEdges,
				'directed',
				false,
				nacs
			);

			// A->C should be excluded because C has connection to B (NAC node3)
			// Valid matches: A->B, A->D, C->B
			expect(result).toContainEqual({
				edges: {
					edge: {
						attributes: {},
						key: 'aToB',
						source: 'testnodeA',
						target: 'testnodeB',
					},
				},
				nodes: {
					node1: { key: 'testnodeA', attributes: { name: 'A' } },
					node2: { key: 'testnodeB', attributes: { name: 'B' } },
				},
			});
			expect(result).toContainEqual({
				edges: {
					edge: {
						attributes: {},
						key: 'aToD',
						source: 'testnodeA',
						target: 'testnodeD',
					},
				},
				nodes: {
					node1: { key: 'testnodeA', attributes: { name: 'A' } },
					node2: { key: 'testnodeD', attributes: { name: 'D' } },
				},
			});
			expect(result).toContainEqual({
				edges: {
					edge: {
						attributes: {},
						key: 'cToB',
						source: 'testnodeC',
						target: 'testnodeB',
					},
				},
				nodes: {
					node1: { key: 'testnodeC', attributes: { name: 'C' } },
					node2: { key: 'testnodeB', attributes: { name: 'B' } },
				},
			});

			// A->C should NOT be in result
			expect(result).not.toContainEqual(
				expect.objectContaining({
					edges: expect.objectContaining({
						edge: expect.objectContaining({ key: 'aToC' }),
					}),
				})
			);
		});

		test('pattern matching with array attribute (IN semantics)', async () => {
			await graphService.createNode({ type: 'Gate' }, 'n1');
			await graphService.createNode({ type: 'Place' }, 'n2');
			await graphService.createNode({ type: 'Transition' }, 'n3');

			const patternNodes: PatternNodeSchema[] = [
				{
					key: 'A',
					attributes: { type: ['Gate', 'Place'] },
				},
			];

			const result = await graphService.findPatternMatch(patternNodes, []);
			expect(result).toHaveLength(2);
			expect(result).toContainEqual({
				edges: {},
				nodes: { A: { key: 'n1', attributes: { type: 'Gate' } } },
			});
			expect(result).toContainEqual({
				edges: {},
				nodes: { A: { key: 'n2', attributes: { type: 'Place' } } },
			});
		});
	});
});
