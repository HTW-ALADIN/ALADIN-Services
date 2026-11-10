import type {
	SurfaceRealizationRequest,
	TemplateGenerationRequest,
} from '../src/schemas.js';

export function throwUnknown(value: unknown): never {
	throw value;
}

export function englishRequest(): SurfaceRealizationRequest {
	return {
		mode: 'surface_realization',
		backend: 'jsrealb',
		language: 'en',
		input: {
			representation: 'constituent',
			structure: {
				phrase: 'S',
				elements: [
					{
						phrase: 'NP',
						elements: [
							{ terminal: 'D', lemma: 'the' },
							{ terminal: 'N', lemma: 'cat' },
						],
					},
					{
						phrase: 'VP',
						elements: [
							{ terminal: 'V', lemma: 'chase' },
							{
								phrase: 'NP',
								elements: [
									{ terminal: 'D', lemma: 'the' },
									{ terminal: 'N', lemma: 'mouse' },
								],
							},
						],
					},
				],
			},
		},
	};
}

export function frenchRequest(): SurfaceRealizationRequest {
	return {
		mode: 'surface_realization',
		backend: 'jsrealb',
		language: 'fr',
		input: {
			representation: 'dependency',
			structure: {
				dependent: 'root',
				terminal: { terminal: 'V', lemma: 'aimer' },
				dependents: [
					{
						dependent: 'subj',
						terminal: { terminal: 'N', lemma: 'chat' },
						dependents: [
							{
								dependent: 'det',
								terminal: { terminal: 'D', lemma: 'le' },
								dependents: [],
							},
						],
					},
				],
			},
		},
	};
}

export function templateRequest(): TemplateGenerationRequest {
	return {
		mode: 'template_generation',
		backend: 'rosaenlg',
		language: 'en_US',
		input: {
			template: 'p Hello #{name}!',
			data: { name: 'Alice' },
			seed: 0,
		},
	};
}
