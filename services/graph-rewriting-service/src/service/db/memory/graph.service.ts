import { GrafeoDB } from '@grafeo-db/js';
import {
	DBGraphEdgeInternalId,
	DBGraphNodeInternalId,
	DBGraphNodeMetadata,
	DBGraphNodeResult,
	IGraphDB,
	DBGraphEdgeResult,
	DBGraphEdgeMetadata,
	DBGraphType,
	DBGraphPatternMatchResult,
	DBGraphNACs,
	EdgeUpdateRewriteOptions,
	NodeUpdateRewriteOptions,
	DBGraphEdge,
} from '../types';
import { PatternNodeSchema } from '../../../types/patternnode.schema';
import {
	computeEdgeQuery,
	computeInjectivityClause,
	computeNodeQuery,
} from '../neo4j/cypher/rewrite';
import {
	DEFAULT_NODE_LABEL,
	DEFAULT_RELATIONSHIP_LABEL,
} from '../neo4j/constants';
import { sanitizeIdentifier } from '../neo4j/cypher/utils';
import { createNodeUuid, createParameterUuid } from '../../../utils/uuid';

export class InMemoryGraphService implements IGraphDB {
	private readonly db = GrafeoDB.create();
	/** Supplemental edge index — grafeo doesn't support WHERE on relationship properties */
	private readonly edgeStore = new Map<string, DBGraphEdgeResult>();

	public graphType: DBGraphType = 'undirected';

	// ---------- helpers ----------

	private propsToNodeResult(props: Record<string, unknown>): DBGraphNodeResult {
		const key = props._grs_internalId as string;
		const attributes = { ...props };
		delete attributes._grs_internalId;
		return { key, attributes };
	}

	private propsToEdgeResult(props: Record<string, unknown>): DBGraphEdgeResult {
		const key = props._grs_internalId as string;
		const source = props._grs_source as string;
		const target = props._grs_target as string;
		const attributes = { ...props };
		delete attributes._grs_internalId;
		delete attributes._grs_source;
		delete attributes._grs_target;
		return { key, source, target, attributes };
	}

	// ---------- Node CRUD ----------

	public async createNode(
		metadata: DBGraphNodeMetadata,
		internalId?: DBGraphNodeInternalId
	): Promise<DBGraphNodeResult> {
		const key = internalId ?? createNodeUuid();
		const attrs = { ...metadata };
		delete attrs._grs_internalId;
		const storedAttrs = { ...attrs, _grs_internalId: key };

		await this.db.executeCypher(
			`CREATE (n:\`${DEFAULT_NODE_LABEL}\`) SET n = $nodeMetadata`,
			{ nodeMetadata: storedAttrs }
		);

		return { key, attributes: attrs };
	}

	public async updateNode(
		metadata: DBGraphNodeMetadata,
		internalId: DBGraphNodeInternalId,
		// eslint-disable-next-line @typescript-eslint/no-unused-vars
		_oldTypes: string[] = [],
		options: NodeUpdateRewriteOptions = {}
	): Promise<DBGraphNodeResult> {
		if (!internalId) {
			throw new Error(
				'InMemoryGraphService: no internalId given in updateNode clause'
			);
		}

		const attrs = { ...metadata };
		delete attrs._grs_internalId;
		const mode = options?.attributeReplacementMode;

		if (mode === 'delete') {
			await this.db.executeCypher(
				`MATCH (n) WHERE n._grs_internalId = $internalId SET n = $metadata`,
				{ internalId, metadata: { _grs_internalId: internalId } }
			);
			return { key: internalId, attributes: {} };
		} else if (mode === 'replace') {
			await this.db.executeCypher(
				`MATCH (n) WHERE n._grs_internalId = $internalId SET n = $metadata`,
				{ internalId, metadata: { ...attrs, _grs_internalId: internalId } }
			);
			return { key: internalId, attributes: attrs };
		} else {
			await this.db.executeCypher(
				`MATCH (n) WHERE n._grs_internalId = $internalId SET n += $metadata`,
				{ internalId, metadata: { ...attrs, _grs_internalId: internalId } }
			);
			return (await this.getNode(internalId))!;
		}
	}

	public async getNode(
		internalId: DBGraphNodeInternalId
	): Promise<DBGraphNodeResult | undefined> {
		const result = await this.db.executeCypher(
			`MATCH (n) WHERE n._grs_internalId = $internalId RETURN properties(n) AS props`,
			{ internalId }
		);
		const rows = result.toArray();
		if (!rows.length) return undefined;
		return this.propsToNodeResult(rows[0].props as Record<string, unknown>);
	}

	public async deleteNode(
		internalId: DBGraphNodeInternalId
	): Promise<DBGraphNodeResult | undefined> {
		const node = await this.getNode(internalId);
		// Remove edges connected to this node from the supplemental store
		for (const [id, edge] of this.edgeStore) {
			if (edge.source === internalId || edge.target === internalId) {
				this.edgeStore.delete(id);
			}
		}
		await this.db.executeCypher(
			`MATCH (n) WHERE n._grs_internalId = $internalId DETACH DELETE n`,
			{ internalId }
		);
		return node;
	}

	public async deleteNodes(
		internalIds: DBGraphNodeInternalId[]
	): Promise<DBGraphNodeResult[] | undefined> {
		const results: DBGraphNodeResult[] = [];
		for (const id of internalIds) {
			const r = await this.deleteNode(id);
			if (r) results.push(r);
		}
		return results.length ? results : undefined;
	}

	public async getAllNodes(): Promise<DBGraphNodeResult[]> {
		const result = await this.db.executeCypher(
			`MATCH (n:\`${DEFAULT_NODE_LABEL}\`) RETURN properties(n) AS props`
		);
		return result
			.toArray()
			.map((row) =>
				this.propsToNodeResult(row.props as Record<string, unknown>)
			);
	}

	public async deleteAllNodes(): Promise<DBGraphNodeResult[]> {
		const all = await this.getAllNodes();
		this.edgeStore.clear();
		await this.db.executeCypher(`MATCH (n) DETACH DELETE n`);
		return all;
	}

	// ---------- Edge CRUD ----------

	public async createEdge(
		internalIdSource: DBGraphNodeInternalId,
		internalIdTarget: DBGraphNodeInternalId,
		internalId: DBGraphEdgeInternalId,
		metadata: DBGraphEdgeMetadata
	): Promise<DBGraphEdgeResult> {
		const storedAttrs = {
			...metadata,
			_grs_internalId: internalId,
			_grs_source: internalIdSource,
			_grs_target: internalIdTarget,
		};

		const result = await this.db.executeCypher(
			`MATCH (a:\`${DEFAULT_NODE_LABEL}\`), (b:\`${DEFAULT_NODE_LABEL}\`) WHERE a._grs_internalId = $src AND b._grs_internalId = $tgt CREATE (a)-[r:\`${DEFAULT_RELATIONSHIP_LABEL}\`]->(b) SET r = $attrs RETURN r`,
			{ src: internalIdSource, tgt: internalIdTarget, attrs: storedAttrs }
		);

		if (!result.toArray().length) {
			throw new Error(
				`InMemoryGraphService: createEdge failed — one or both endpoints do not exist (src=${internalIdSource}, tgt=${internalIdTarget})`
			);
		}

		const edge: DBGraphEdgeResult = {
			key: internalId,
			source: internalIdSource,
			target: internalIdTarget,
			attributes: { ...metadata },
		};
		this.edgeStore.set(internalId, edge);
		return edge;
	}

	public async updateEdge(
		internalIdSource: DBGraphNodeInternalId,
		internalIdTarget: DBGraphNodeInternalId,
		internalId: DBGraphEdgeInternalId,
		metadata: DBGraphEdgeMetadata,
		options: EdgeUpdateRewriteOptions = {}
	): Promise<DBGraphEdgeResult> {
		if (!internalId) {
			throw new Error(
				'InMemoryGraphService: no internalId given in updateEdge clause'
			);
		}

		const oldEdge = this.edgeStore.get(internalId);
		await this.deleteEdge(internalId);

		let attrs: DBGraphEdgeMetadata = {};
		const mode = options?.attributeReplacementMode;

		if (mode === 'delete') {
			attrs = {};
		} else if (mode === 'replace') {
			attrs = { ...metadata };
		} else {
			attrs = oldEdge
				? { ...oldEdge.attributes, ...metadata }
				: { ...metadata };
		}

		return this.createEdge(
			internalIdSource,
			internalIdTarget,
			internalId,
			attrs
		);
	}

	public async getEdge(
		internalId: DBGraphEdgeInternalId
	): Promise<DBGraphEdgeResult | undefined> {
		return this.edgeStore.get(internalId);
	}

	public async deleteEdge(
		internalId: DBGraphEdgeInternalId
	): Promise<DBGraphEdgeResult | undefined> {
		const edge = this.edgeStore.get(internalId);
		if (!edge) return undefined;
		this.edgeStore.delete(internalId);

		// Find other edges that share the same src/tgt (multigraph survivors)
		const survivors = [...this.edgeStore.values()].filter(
			(e) => e.source === edge.source && e.target === edge.target
		);

		// Delete ALL relationships between src/tgt (grafeo can't filter by rel property)
		await this.db.executeCypher(
			`MATCH (a)-[r:\`${DEFAULT_RELATIONSHIP_LABEL}\`]->(b) WHERE a._grs_internalId = $src AND b._grs_internalId = $tgt DELETE r`,
			{ src: edge.source, tgt: edge.target }
		);

		// Recreate the surviving parallel edges
		for (const survivor of survivors) {
			await this.db.executeCypher(
				`MATCH (a:\`${DEFAULT_NODE_LABEL}\`), (b:\`${DEFAULT_NODE_LABEL}\`) WHERE a._grs_internalId = $src AND b._grs_internalId = $tgt CREATE (a)-[r:\`${DEFAULT_RELATIONSHIP_LABEL}\`]->(b) SET r = $attrs`,
				{
					src: survivor.source,
					tgt: survivor.target,
					attrs: {
						...survivor.attributes,
						_grs_internalId: survivor.key,
						_grs_source: survivor.source,
						_grs_target: survivor.target,
					},
				}
			);
		}

		return edge;
	}

	public async deleteEdges(
		internalIds: DBGraphEdgeInternalId[]
	): Promise<DBGraphEdgeResult[]> {
		const results: DBGraphEdgeResult[] = [];
		for (const id of internalIds) {
			const r = await this.deleteEdge(id);
			if (r) results.push(r);
		}
		return results;
	}

	public async getAllEdges(): Promise<DBGraphEdgeResult[]> {
		return [...this.edgeStore.values()];
	}

	// ---------- Pattern matching ----------

	public async findPatternMatch(
		nodes: PatternNodeSchema[],
		edges: DBGraphEdge[],
		type: DBGraphType = 'undirected',
		homo = true,
		nacs: DBGraphNACs[] = []
	): Promise<DBGraphPatternMatchResult[] | []> {
		if (!nodes.length && !edges.length) {
			return [{ nodes: {}, edges: {} }];
		}

		// Edges referencing nodes not in the pattern cannot be resolved
		const nodeKeySet = new Set(nodes.map((n) => n.key));
		for (const edge of edges) {
			if (!nodeKeySet.has(edge.source) || !nodeKeySet.has(edge.target)) {
				return [];
			}
		}

		let query = '';
		let hasWhere = false;
		let parameters: Record<string, unknown> = {};
		const whereClauses: string[] = [];

		const nodeVars = nodes.map((n) => sanitizeIdentifier(n.key));
		const edgeVars = edges.map((e) => sanitizeIdentifier(e.key));

		const nodeQueries: string[] = [];
		for (const node of nodes) {
			const { cypher, where, params } = computeNodeQuery(
				node.key,
				[DEFAULT_NODE_LABEL],
				node.attributes ?? {}
			);
			if (where) whereClauses.push(where);
			if (params) parameters = { ...parameters, ...params };
			nodeQueries.push(cypher);
		}
		query += nodeQueries.join(', ');

		const edgeQueries: string[] = [];
		for (const edge of edges) {
			const { cypher, where, params } = computeEdgeQuery(
				edge.key,
				DEFAULT_RELATIONSHIP_LABEL,
				edge.attributes,
				edge.source,
				edge.target,
				type === 'directed'
			);
			if (where) whereClauses.push(where);
			if (params) parameters = { ...parameters, ...params };
			edgeQueries.push(cypher);
		}
		if (nodeQueries.length && edgeQueries.length) query += ', ';
		query += edgeQueries.join(', ');

		if (!homo) {
			const nodeInj = computeInjectivityClause(
				nodes.map((n) => n.key),
				hasWhere
			);
			query += nodeInj.cypher;
			hasWhere = nodeInj.hasWhere;
			const edgeInj = computeInjectivityClause(
				edges.map((e) => e.key),
				hasWhere
			);
			query += edgeInj.cypher;
			hasWhere = edgeInj.hasWhere;
		}

		if (whereClauses.length) {
			query += (!hasWhere ? ' WHERE' : ' AND') + whereClauses.join(' AND');
		}

		const returnParts = [
			...nodeVars.map((v) => `properties(\`${v}\`) AS \`${v}\``),
			...edgeVars.map((v) => `properties(\`${v}\`) AS \`${v}\``),
		];
		const cypher = `MATCH ${query} RETURN ${returnParts.join(', ')}`;

		const res = await this.db.executeCypher(cypher, parameters);
		const mainResults = res.toArray().map((row) => {
			const matchResult: DBGraphPatternMatchResult = { nodes: {}, edges: {} };
			for (const v of nodeVars) {
				const props = row[v] as Record<string, unknown> | undefined;
				if (props) matchResult.nodes[v] = this.propsToNodeResult(props);
			}
			for (const v of edgeVars) {
				const props = row[v] as Record<string, unknown> | undefined;
				if (props) matchResult.edges[v] = this.propsToEdgeResult(props);
			}
			return matchResult;
		});

		// Apply NACs as post-query filter
		if (!nacs.length) return mainResults;

		const finalResults: DBGraphPatternMatchResult[] = [];
		for (const matchResult of mainResults) {
			let violated = false;
			for (const nac of nacs) {
				if (await this.nacMatchExists(nac, matchResult)) {
					violated = true;
					break;
				}
			}
			if (!violated) finalResults.push(matchResult);
		}
		return finalResults;
	}

	/**
	 * Check whether a NAC pattern can be matched given the current binding.
	 * Returns true if the NAC fires (violation), false if the match is safe.
	 */
	private async nacMatchExists(
		nac: DBGraphNACs,
		matchResult: DBGraphPatternMatchResult
	): Promise<boolean> {
		const nacNodes = (nac.nodes || []) as PatternNodeSchema[];
		const nacEdges = (nac.edges || []) as DBGraphEdge[];
		const nacType = (nac.options?.type ?? 'undirected') as DBGraphType;

		if (!nacNodes.length && !nacEdges.length) return true;

		let parameters: Record<string, unknown> = {};
		const whereClauses: string[] = [];
		const nodeQueries: string[] = [];
		const edgeQueries: string[] = [];

		for (const nacNode of nacNodes) {
			const { cypher, where, params } = computeNodeQuery(
				nacNode.key,
				[DEFAULT_NODE_LABEL],
				nacNode.attributes ?? {}
			);
			nodeQueries.push(cypher);
			if (where) whereClauses.push(where);
			if (params) parameters = { ...parameters, ...params };

			// Pin already-bound NAC nodes to their matched host node
			if (nacNode.key in matchResult.nodes) {
				const boundId = matchResult.nodes[nacNode.key].key;
				const paramId = createParameterUuid();
				parameters[paramId] = boundId;
				whereClauses.push(
					`\`${sanitizeIdentifier(nacNode.key)}\`._grs_internalId = $${paramId}`
				);
			}
		}

		for (const edge of nacEdges) {
			const { cypher, where, params } = computeEdgeQuery(
				edge.key,
				DEFAULT_RELATIONSHIP_LABEL,
				edge.attributes,
				edge.source,
				edge.target,
				nacType === 'directed'
			);
			edgeQueries.push(cypher);
			if (where) whereClauses.push(where);
			if (params) parameters = { ...parameters, ...params };
		}

		let matchPart = nodeQueries.join(', ');
		if (nodeQueries.length && edgeQueries.length) matchPart += ', ';
		matchPart += edgeQueries.join(', ');

		if (!matchPart) return false;

		const whereStr = whereClauses.length
			? ' WHERE ' + whereClauses.join(' AND ')
			: '';
		const cypher = `MATCH ${matchPart}${whereStr} RETURN COUNT(*) AS c`;

		const result = await this.db.executeCypher(cypher, parameters);
		const rows = result.toArray();
		if (!rows.length) return false;
		return (rows[0].c as number) > 0;
	}
}
