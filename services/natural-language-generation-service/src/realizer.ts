import jsRealB from 'jsrealb';
import type { ServiceLimits } from './config.js';
import { ServiceError } from './errors.js';
import type {
	GenerateRequest,
	GenerateResponse,
	SurfaceRealizationRequest,
	SurfaceRealizationResponse,
	TemplateGenerationRequest,
	TemplateGenerationResponse,
} from './schemas.js';
import { realizeTemplate, rosaeNlgVersion } from './template-realizer.js';

jsRealB.setExceptionOnWarning(true);

interface StructuralNode {
	phrase?: string;
	elements?: StructuralNode[];
	dependent?: string;
	terminal?: StructuralNode | string;
	dependents?: StructuralNode[];
}

function inspectStructure(root: StructuralNode, limits: ServiceLimits): number {
	const stack: Array<{ node: unknown; depth: number }> = [
		{ node: root, depth: 1 },
	];
	let nodeCount = 0;

	while (stack.length > 0) {
		const current = stack.pop()!;
		nodeCount += 1;
		if (nodeCount > limits.maxNodes) {
			throw new ServiceError(
				'resource-limit',
				422,
				'Resource limit exceeded',
				`structure contains more than ${limits.maxNodes} nodes`
			);
		}
		if (current.depth > limits.maxDepth) {
			throw new ServiceError(
				'resource-limit',
				422,
				'Resource limit exceeded',
				`structure is deeper than ${limits.maxDepth} levels`
			);
		}

		if (
			current.node === null ||
			typeof current.node !== 'object' ||
			Array.isArray(current.node)
		) {
			continue;
		}
		const node = current.node as StructuralNode;
		if (Array.isArray(node.elements)) {
			for (const element of node.elements) {
				stack.push({ node: element, depth: current.depth + 1 });
			}
		}
		if (node.terminal !== undefined && typeof node.terminal === 'object') {
			stack.push({
				node: node.terminal,
				depth: current.depth + 1,
			});
		}
		if (Array.isArray(node.dependents)) {
			for (const dependent of node.dependents) {
				stack.push({ node: dependent, depth: current.depth + 1 });
			}
		}
	}

	return nodeCount;
}

function inspectTemplateData(root: unknown, limits: ServiceLimits): number {
	const stack: Array<{ value: unknown; depth: number }> = [
		{ value: root, depth: 1 },
	];
	let valueCount = 0;

	while (stack.length > 0) {
		const current = stack.pop()!;
		valueCount += 1;
		if (valueCount > limits.maxNodes) {
			throw new ServiceError(
				'resource-limit',
				422,
				'Resource limit exceeded',
				`template data contains more than ${limits.maxNodes} values`
			);
		}
		if (current.depth > limits.maxDepth) {
			throw new ServiceError(
				'resource-limit',
				422,
				'Resource limit exceeded',
				`template data is deeper than ${limits.maxDepth} levels`
			);
		}
		if (Array.isArray(current.value)) {
			for (const value of current.value) {
				stack.push({ value, depth: current.depth + 1 });
			}
		} else if (current.value !== null && typeof current.value === 'object') {
			for (const value of Object.values(current.value)) {
				stack.push({ value, depth: current.depth + 1 });
			}
		}
	}

	return valueCount;
}

export function inspectRequestStructure(
	value: unknown,
	limits: ServiceLimits
): number | undefined {
	if (value === null || typeof value !== 'object' || Array.isArray(value)) {
		return undefined;
	}
	const input = (value as Record<string, unknown>).input;
	if (input === null || typeof input !== 'object' || Array.isArray(input)) {
		return undefined;
	}
	const structure = (input as Record<string, unknown>).structure;
	if (
		structure === null ||
		typeof structure !== 'object' ||
		Array.isArray(structure)
	) {
		const data = (input as Record<string, unknown>).data;
		if (data === null || typeof data !== 'object' || Array.isArray(data)) {
			return undefined;
		}
		return inspectTemplateData(data, limits);
	}
	return inspectStructure(structure as StructuralNode, limits);
}

export function realize(
	request: SurfaceRealizationRequest,
	limits: ServiceLimits
): Promise<SurfaceRealizationResponse>;
export function realize(
	request: TemplateGenerationRequest,
	limits: ServiceLimits
): Promise<TemplateGenerationResponse>;
export function realize(
	request: GenerateRequest,
	limits: ServiceLimits
): Promise<GenerateResponse>;
export async function realize(
	request: GenerateRequest,
	limits: ServiceLimits
): Promise<GenerateResponse> {
	if (request.mode === 'template_generation') {
		inspectTemplateData(request.input.data, limits);
		return realizeTemplate(request, limits);
	}
	const structure = structuredClone(
		request.input.structure
	) as StructuralNode & {
		lang?: 'en' | 'fr';
	};
	const nodeCount = inspectStructure(structure, limits);
	structure.lang = request.language;

	try {
		const constituent = jsRealB.fromJSON(
			structure as unknown as Record<string, unknown>,
			request.language
		);
		if (constituent === undefined) {
			throw new Error('jsRealB did not create a realisable structure');
		}

		const text = constituent.realize().trimEnd();
		if (Buffer.byteLength(text, 'utf8') > limits.maxOutputBytes) {
			throw new ServiceError(
				'resource-limit',
				422,
				'Resource limit exceeded',
				`realised output exceeds ${limits.maxOutputBytes} bytes`
			);
		}

		return {
			text,
			mode: request.mode,
			backend: request.backend,
			language: request.language,
			metadata: {
				engineVersion: jsRealB.jsRealB_version,
				representation: request.input.representation,
				nodeCount,
			},
		};
	} catch (error) {
		if (error instanceof ServiceError) throw error;
		const detail = error instanceof Error ? error.message : String(error);
		throw new ServiceError(
			'realisation-error',
			422,
			'Realisation failed',
			detail
		);
	}
}

export function capabilities(limits: ServiceLimits) {
	return {
		engines: [
			{
				name: 'jsRealB',
				version: jsRealB.jsRealB_version,
				maintenance: 'active' as const,
			},
			{
				name: 'RosaeNLG',
				version: rosaeNlgVersion(),
				maintenance: 'archived' as const,
			},
		],
		modes: {
			surface_realization: {
				backends: ['jsrealb' as const],
				languages: ['en', 'fr'],
				representations: ['constituent', 'dependency'],
				features: [
					'morphology',
					'agreement',
					'tense_aspect',
					'sentence_transformations',
					'coordination',
					'numbers_dates',
					'orthography',
				],
			},
			template_generation: {
				backends: ['rosaenlg' as const],
				languages: ['en_US', 'fr_FR', 'de_DE', 'it_IT', 'es_ES'],
				features: ['anaphora', 'lexical_variation', 'document_templates'],
				trustedTemplateRequired: true as const,
			},
		},
		coverage: {
			directCapabilityFamilies: 15 as const,
			totalCapabilityFamilies: 15 as const,
			percentage: 100 as const,
		},
		phraseKinds: ['S', 'NP', 'AP', 'VP', 'AdvP', 'PP', 'CP', 'SP'],
		terminalKinds: [
			'N',
			'A',
			'Pro',
			'D',
			'V',
			'Adv',
			'C',
			'P',
			'DT',
			'NO',
			'Q',
		],
		dependencyKinds: ['root', 'det', 'subj', 'comp', 'mod', 'coord'],
		limits: {
			maxBodyBytes: limits.maxBodyBytes,
			maxNodes: limits.maxNodes,
			maxDepth: limits.maxDepth,
			maxOutputBytes: limits.maxOutputBytes,
			templateTimeoutMs: limits.templateTimeoutMs,
		},
	};
}
