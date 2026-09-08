import { Static, Type } from '@sinclair/typebox';

const PhraseKindSchema = Type.Union(
	['S', 'NP', 'AP', 'VP', 'AdvP', 'PP', 'CP', 'SP'].map((value) =>
		Type.Literal(value)
	)
);

const TerminalKindSchema = Type.Union(
	['N', 'A', 'Pro', 'D', 'V', 'Adv', 'C', 'P', 'DT', 'NO', 'Q'].map((value) =>
		Type.Literal(value)
	)
);

const DependencyKindSchema = Type.Union(
	['root', 'det', 'subj', 'comp', 'mod', 'coord'].map((value) =>
		Type.Literal(value)
	)
);

const TemplateLanguageSchema = Type.Union([
	Type.Literal('en_US'),
	Type.Literal('fr_FR'),
	Type.Literal('de_DE'),
	Type.Literal('it_IT'),
	Type.Literal('es_ES'),
]);

const TenseSchema = Type.Union(
	[
		'p',
		'b',
		'b-to',
		'bp-to',
		'i',
		'ps',
		'f',
		'ip',
		'c',
		'pr',
		's',
		'si',
		'pp',
		'pc',
		'pq',
		'cp',
		'fa',
		'pa',
		'spa',
		'spq',
		'bp',
	].map((value) => Type.Literal(value))
);

const SentenceTypeSchema = Type.Object(
	{
		neg: Type.Optional(
			Type.Union([Type.Boolean(), Type.String({ minLength: 1, maxLength: 32 })])
		),
		pas: Type.Optional(Type.Boolean()),
		prog: Type.Optional(Type.Boolean()),
		exc: Type.Optional(Type.Boolean()),
		perf: Type.Optional(Type.Boolean()),
		contr: Type.Optional(Type.Boolean()),
		refl: Type.Optional(Type.Boolean()),
		maje: Type.Optional(Type.Boolean()),
		mod: Type.Optional(
			Type.Union(
				[false, 'poss', 'perm', 'nece', 'obli', 'will'].map((value) =>
					Type.Literal(value)
				)
			)
		),
		int: Type.Optional(
			Type.Union(
				[
					false,
					'yon',
					'wos',
					'wod',
					'woi',
					'was',
					'wad',
					'wai',
					'whe',
					'why',
					'whn',
					'how',
					'muc',
					'tag',
				].map((value) => Type.Literal(value))
			)
		),
	},
	{ additionalProperties: false }
);

const DisplayOptionsSchema = Type.Object(
	{
		year: Type.Optional(Type.Boolean()),
		month: Type.Optional(Type.Boolean()),
		date: Type.Optional(Type.Boolean()),
		day: Type.Optional(Type.Boolean()),
		hour: Type.Optional(Type.Boolean()),
		minute: Type.Optional(Type.Boolean()),
		second: Type.Optional(Type.Boolean()),
		det: Type.Optional(Type.Boolean()),
		nat: Type.Optional(Type.Boolean()),
		ord: Type.Optional(Type.Boolean()),
		rom: Type.Optional(Type.Boolean()),
		raw: Type.Optional(Type.Boolean()),
		mprecision: Type.Optional(Type.Number({ minimum: 0, maximum: 20 })),
	},
	{ additionalProperties: false }
);

const GrammarPropertiesSchema = Type.Object(
	{
		n: Type.Optional(Type.Union([Type.Literal('s'), Type.Literal('p')])),
		g: Type.Optional(
			Type.Union([Type.Literal('m'), Type.Literal('f'), Type.Literal('n')])
		),
		pe: Type.Optional(
			Type.Union([Type.Literal(1), Type.Literal(2), Type.Literal(3)])
		),
		t: Type.Optional(TenseSchema),
		aux: Type.Optional(Type.Union([Type.Literal('av'), Type.Literal('êt')])),
		typ: Type.Optional(SentenceTypeSchema),
		pos: Type.Optional(Type.Union([Type.Literal('pre'), Type.Literal('post')])),
		pro: Type.Optional(Type.Literal(true)),
		c: Type.Optional(
			Type.Union(
				['nom', 'acc', 'dat', 'gen', 'refl'].map((value) => Type.Literal(value))
			)
		),
		ow: Type.Optional(Type.Union([Type.Literal('s'), Type.Literal('p')])),
		cap: Type.Optional(Type.Union([Type.Boolean(), Type.Literal('tit')])),
		lier: Type.Optional(Type.Literal(true)),
		maje: Type.Optional(Type.Boolean()),
		nat: Type.Optional(Type.Boolean()),
		dOpt: Type.Optional(DisplayOptionsSchema),
		a: Type.Optional(Type.String({ maxLength: 64 })),
		b: Type.Optional(Type.String({ maxLength: 64 })),
		en: Type.Optional(Type.String({ maxLength: 64 })),
		ba: Type.Optional(Type.String({ maxLength: 64 })),
	},
	{
		additionalProperties: false,
		description:
			'Allowlisted jsRealB options. Arbitrary method names, JavaScript expressions, HTML tags, and Markdown directives are rejected.',
	}
);

const TerminalNodeSchema = Type.Object(
	{
		terminal: TerminalKindSchema,
		lemma: Type.Union([
			Type.String({ minLength: 1, maxLength: 4096 }),
			Type.Number(),
		]),
		props: Type.Optional(GrammarPropertiesSchema),
	},
	{ additionalProperties: false }
);

export const ConstituentNodeSchema = Type.Recursive(
	(This) =>
		Type.Union([
			Type.Object(
				{
					phrase: PhraseKindSchema,
					elements: Type.Array(This, { maxItems: 256 }),
					props: Type.Optional(GrammarPropertiesSchema),
				},
				{ additionalProperties: false }
			),
			TerminalNodeSchema,
		]),
	{ $id: 'ConstituentNode' }
);

export const DependentNodeSchema = Type.Recursive(
	(This) =>
		Type.Object(
			{
				dependent: DependencyKindSchema,
				terminal: TerminalNodeSchema,
				dependents: Type.Array(This, { maxItems: 256 }),
				props: Type.Optional(GrammarPropertiesSchema),
			},
			{ additionalProperties: false }
		),
	{ $id: 'DependentNode' }
);

const ConstituentInputSchema = Type.Object(
	{
		representation: Type.Literal('constituent'),
		structure: Type.Ref(ConstituentNodeSchema),
	},
	{ additionalProperties: false }
);

const DependencyInputSchema = Type.Object(
	{
		representation: Type.Literal('dependency'),
		structure: Type.Ref(DependentNodeSchema),
	},
	{ additionalProperties: false }
);

export const SurfaceRealizationRequestSchema = Type.Object(
	{
		mode: Type.Literal('surface_realization'),
		backend: Type.Literal('jsrealb'),
		language: Type.Union([Type.Literal('en'), Type.Literal('fr')]),
		input: Type.Union([ConstituentInputSchema, DependencyInputSchema]),
	},
	{
		additionalProperties: false,
		$id: 'SurfaceRealizationRequest',
		description:
			'JSON-only structured realisation request. JavaScript source expressions are never accepted.',
	}
);

export const JsonValueSchema = Type.Recursive(
	(This) =>
		Type.Union([
			Type.String({ maxLength: 16_384 }),
			Type.Number(),
			Type.Boolean(),
			Type.Null(),
			Type.Array(This, { maxItems: 256 }),
			Type.Record(Type.String({ minLength: 1, maxLength: 128 }), This, {
				maxProperties: 256,
			}),
		]),
	{ $id: 'JsonValue' }
);

const TemplateInputSchema = Type.Object(
	{
		template: Type.String({ minLength: 1, maxLength: 65_536 }),
		data: Type.Record(
			Type.String({ minLength: 1, maxLength: 128 }),
			Type.Ref(JsonValueSchema),
			{ maxProperties: 256 }
		),
		seed: Type.Optional(
			Type.Integer({ minimum: 0, maximum: 4_294_967_295, default: 0 })
		),
	},
	{
		additionalProperties: false,
		description:
			'Trusted RosaeNLG/Pug template source, JSON data locals, and an optional deterministic random seed.',
	}
);

export const TemplateGenerationRequestSchema = Type.Object(
	{
		mode: Type.Literal('template_generation'),
		backend: Type.Literal('rosaenlg'),
		language: TemplateLanguageSchema,
		input: TemplateInputSchema,
	},
	{
		additionalProperties: false,
		$id: 'TemplateGenerationRequest',
		description:
			'Template/data-to-text request executed by the legacy RosaeNLG backend. Template source is executable and must be trusted.',
	}
);

export const GenerateRequestSchema = Type.Union(
	[
		Type.Ref(SurfaceRealizationRequestSchema),
		Type.Ref(TemplateGenerationRequestSchema),
	],
	{ $id: 'GenerateRequest' }
);

export const SurfaceRealizationResponseSchema = Type.Object(
	{
		text: Type.String(),
		mode: Type.Literal('surface_realization'),
		backend: Type.Literal('jsrealb'),
		language: Type.Union([Type.Literal('en'), Type.Literal('fr')]),
		metadata: Type.Object(
			{
				engineVersion: Type.String(),
				representation: Type.Union([
					Type.Literal('constituent'),
					Type.Literal('dependency'),
				]),
				nodeCount: Type.Integer({ minimum: 1 }),
			},
			{ additionalProperties: false }
		),
	},
	{ additionalProperties: false, $id: 'SurfaceRealizationResponse' }
);

export const TemplateGenerationResponseSchema = Type.Object(
	{
		text: Type.String(),
		mode: Type.Literal('template_generation'),
		backend: Type.Literal('rosaenlg'),
		language: TemplateLanguageSchema,
		metadata: Type.Object(
			{
				engineVersion: Type.String(),
				seed: Type.Integer({ minimum: 0, maximum: 4_294_967_295 }),
			},
			{ additionalProperties: false }
		),
	},
	{ additionalProperties: false, $id: 'TemplateGenerationResponse' }
);

export const GenerateResponseSchema = Type.Union(
	[
		Type.Ref(SurfaceRealizationResponseSchema),
		Type.Ref(TemplateGenerationResponseSchema),
	],
	{ $id: 'GenerateResponse' }
);

export const ProblemSchema = Type.Object(
	{
		type: Type.String(),
		title: Type.String(),
		status: Type.Integer(),
		detail: Type.String(),
		code: Type.String(),
		instance: Type.Optional(Type.String()),
	},
	{ additionalProperties: false, $id: 'Problem' }
);

export const HealthSchema = Type.Object(
	{ status: Type.Literal('ok') },
	{ additionalProperties: false, $id: 'Health' }
);

export const CapabilitiesSchema = Type.Object(
	{
		engines: Type.Array(
			Type.Object(
				{
					name: Type.String(),
					version: Type.String(),
					maintenance: Type.Union([
						Type.Literal('active'),
						Type.Literal('archived'),
					]),
				},
				{ additionalProperties: false }
			)
		),
		modes: Type.Object(
			{
				surface_realization: Type.Object(
					{
						backends: Type.Array(Type.Literal('jsrealb')),
						languages: Type.Array(Type.String()),
						representations: Type.Array(Type.String()),
						features: Type.Array(Type.String()),
					},
					{ additionalProperties: false }
				),
				template_generation: Type.Object(
					{
						backends: Type.Array(Type.Literal('rosaenlg')),
						languages: Type.Array(Type.String()),
						features: Type.Array(Type.String()),
						trustedTemplateRequired: Type.Literal(true),
					},
					{ additionalProperties: false }
				),
			},
			{ additionalProperties: false }
		),
		coverage: Type.Object(
			{
				directCapabilityFamilies: Type.Literal(15),
				totalCapabilityFamilies: Type.Literal(15),
				percentage: Type.Literal(100),
			},
			{ additionalProperties: false }
		),
		phraseKinds: Type.Array(Type.String()),
		terminalKinds: Type.Array(Type.String()),
		dependencyKinds: Type.Array(Type.String()),
		limits: Type.Object({
			maxBodyBytes: Type.Integer(),
			maxNodes: Type.Integer(),
			maxDepth: Type.Integer(),
			maxOutputBytes: Type.Integer(),
			templateTimeoutMs: Type.Integer(),
			maxConcurrentWorkers: Type.Integer(),
			realizationTimeoutMs: Type.Integer(),
		}),
	},
	{ additionalProperties: false, $id: 'Capabilities' }
);

export type SurfaceRealizationRequest = Static<
	typeof SurfaceRealizationRequestSchema
>;
export type TemplateGenerationRequest = Static<
	typeof TemplateGenerationRequestSchema
>;
export type GenerateRequest = Static<typeof GenerateRequestSchema>;
export type SurfaceRealizationResponse = Static<
	typeof SurfaceRealizationResponseSchema
>;
export type TemplateGenerationResponse = Static<
	typeof TemplateGenerationResponseSchema
>;
export type GenerateResponse = Static<typeof GenerateResponseSchema>;
