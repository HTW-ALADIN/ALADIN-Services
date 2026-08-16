export interface ServiceLimits {
	maxBodyBytes: number;
	maxNodes: number;
	maxDepth: number;
	maxOutputBytes: number;
	templateTimeoutMs: number;
}

export const DEFAULT_LIMITS: ServiceLimits = {
	maxBodyBytes: 1_048_576,
	maxNodes: 1_000,
	maxDepth: 64,
	maxOutputBytes: 1_048_576,
	templateTimeoutMs: 5_000,
};

function positiveInteger(name: string, fallback: number): number {
	const raw = process.env[name];
	if (raw === undefined) return fallback;
	if (
		!/^\d+$/.test(raw) ||
		Number(raw) < 1 ||
		!Number.isSafeInteger(Number(raw))
	) {
		throw new Error(`${name} must be a positive safe integer`);
	}
	return Number(raw);
}

export function loadLimits(): ServiceLimits {
	return {
		maxBodyBytes: positiveInteger(
			'NLG_MAX_BODY_BYTES',
			DEFAULT_LIMITS.maxBodyBytes
		),
		maxNodes: positiveInteger('NLG_MAX_NODES', DEFAULT_LIMITS.maxNodes),
		maxDepth: positiveInteger('NLG_MAX_DEPTH', DEFAULT_LIMITS.maxDepth),
		maxOutputBytes: positiveInteger(
			'NLG_MAX_OUTPUT_BYTES',
			DEFAULT_LIMITS.maxOutputBytes
		),
		templateTimeoutMs: positiveInteger(
			'NLG_TEMPLATE_TIMEOUT_MS',
			DEFAULT_LIMITS.templateTimeoutMs
		),
	};
}
