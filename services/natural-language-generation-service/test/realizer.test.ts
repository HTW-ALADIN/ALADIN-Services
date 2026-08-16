import { expect } from 'chai';
import { describe, it } from 'node:test';
import { EventEmitter } from 'node:events';
import type { Worker } from 'node:worker_threads';
import { DEFAULT_LIMITS } from '../src/config.js';
import { ServiceError } from '../src/errors.js';
import {
	capabilities,
	inspectRequestStructure,
	realize,
} from '../src/realizer.js';
import {
	runTemplateWorker,
	type TemplateWorkerPayload,
} from '../src/template-realizer.js';
import {
	englishRequest,
	frenchRequest,
	templateRequest,
	throwUnknown,
} from './fixtures.js';

async function rejection(promise: Promise<unknown>): Promise<unknown> {
	try {
		await promise;
	} catch (error) {
		return error;
	}
	throw new Error('expected promise to reject');
}

function workerPayload(): TemplateWorkerPayload {
	return {
		template: 'p Hello',
		data: {},
		language: 'en_US',
		seed: 0,
	};
}

function fakeWorker(events: EventEmitter): Worker {
	return Object.assign(events, {
		terminate: async () => 0,
	}) as unknown as Worker;
}

describe('realizer', () => {
	it('realises an English constituent structure', async () => {
		const result = await realize(englishRequest(), DEFAULT_LIMITS);
		expect(result.text).to.equal('The cat chases the mouse.');
		expect(result.metadata).to.include({ representation: 'constituent' });
		expect(result.metadata.nodeCount).to.equal(9);
	});

	it('realises a French dependency structure', async () => {
		const result = await realize(frenchRequest(), DEFAULT_LIMITS);
		expect(result.text).to.equal('Le chat aime.');
		expect(result.metadata.representation).to.equal('dependency');
	});

	it('renders trusted templates with lexical variation and anaphora', async () => {
		const lexical = templateRequest();
		delete lexical.input.seed;
		lexical.input.template = `p
			synz
				syn
					| Hello #{name}
				syn
					| Hi #{name}`;
		const lexicalResult = await realize(lexical, DEFAULT_LIMITS);
		expect(lexicalResult).to.include({
			text: '<p>Hi Alice</p>',
			mode: 'template_generation',
			backend: 'rosaenlg',
		});
		expect(lexicalResult.metadata).to.include({ seed: 0 });
		lexical.input.seed = 1;
		expect((await realize(lexical, DEFAULT_LIMITS)).text).to.equal(
			'<p>Hello Alice</p>'
		);

		const anaphora = templateRequest();
		anaphora.input.template = `- const person = { name: name };
			mixin personRef(obj, params)
				| #{obj.name}
			mixin personRefexpr(obj, params)
				| they
			- person.ref = personRef
			- person.refexpr = personRefexpr
			p
				| #[+value(person)] arrived. #[+value(person)] smiled.`;
		expect((await realize(anaphora, DEFAULT_LIMITS)).text).to.equal(
			'<p>Alice arrived. They smiled.</p>'
		);

		for (const language of [
			'en_US',
			'fr_FR',
			'de_DE',
			'it_IT',
			'es_ES',
		] as const) {
			const multilingual = templateRequest();
			multilingual.language = language;
			expect((await realize(multilingual, DEFAULT_LIMITS)).language).to.equal(
				language
			);
		}
	});

	it('normalises non-Error template failures', async () => {
		const request = templateRequest();
		request.input.template = `- throw 'legacy renderer failed'`;
		const error = await rejection(realize(request, DEFAULT_LIMITS));
		expect(error).to.be.instanceOf(ServiceError);
		expect(error).to.have.property('message', 'legacy renderer failed');
	});

	it('normalises worker startup, runtime, and early-exit failures', async () => {
		const startup = await rejection(
			runTemplateWorker(workerPayload(), 100, () =>
				throwUnknown('worker creation failed')
			)
		);
		expect(startup).to.have.property('code', 'internal-error');

		const runtimeEvents = new EventEmitter();
		const runtime = runTemplateWorker(workerPayload(), 100, () =>
			fakeWorker(runtimeEvents)
		);
		queueMicrotask(() => {
			runtimeEvents.emit('error', new Error('worker failed'));
			runtimeEvents.emit('exit', 1);
		});
		expect(await rejection(runtime)).to.have.property('code', 'internal-error');

		const exitEvents = new EventEmitter();
		const exited = runTemplateWorker(workerPayload(), 100, () =>
			fakeWorker(exitEvents)
		);
		queueMicrotask(() => exitEvents.emit('exit', 1));
		expect(await rejection(exited)).to.have.property('code', 'internal-error');
	});

	it('applies allowlisted grammatical properties', async () => {
		const request = englishRequest();
		request.input.structure = {
			phrase: 'S',
			props: { typ: { neg: true } },
			elements: [
				{ terminal: 'Pro', lemma: 'I', props: { pe: 1 } },
				{
					phrase: 'VP',
					elements: [{ terminal: 'V', lemma: 'eat', props: { t: 'ps' } }],
				},
			],
		};
		expect((await realize(request, DEFAULT_LIMITS)).text).to.equal(
			'I did not eat.'
		);
	});

	it('enforces node, depth, and output limits', async () => {
		const request = englishRequest();
		for (const limits of [
			{ ...DEFAULT_LIMITS, maxNodes: 2 },
			{ ...DEFAULT_LIMITS, maxDepth: 1 },
			{ ...DEFAULT_LIMITS, maxOutputBytes: 2 },
		]) {
			expect(await rejection(realize(request, limits))).to.have.property(
				'code',
				'resource-limit'
			);
		}
	});

	it('enforces template boundaries and normalises template failures', async () => {
		const oversized = templateRequest();
		expect(
			await rejection(
				realize(oversized, { ...DEFAULT_LIMITS, maxOutputBytes: 2 })
			)
		).to.have.property('code', 'resource-limit');

		const excessiveData = templateRequest();
		excessiveData.input.data = { items: [1, 2, 3] };
		expect(
			await rejection(
				realize(excessiveData, { ...DEFAULT_LIMITS, maxNodes: 2 })
			)
		).to.have.property('code', 'resource-limit');
		expect(
			await rejection(
				realize(excessiveData, { ...DEFAULT_LIMITS, maxDepth: 1 })
			)
		).to.have.property('code', 'resource-limit');

		const reserved = templateRequest();
		reserved.input.data = { language: 'fr_FR' };
		expect(await rejection(realize(reserved, DEFAULT_LIMITS))).to.have.property(
			'code',
			'invalid-request'
		);

		const fileAccess = templateRequest();
		fileAccess.input.template = 'include /etc/passwd';
		expect(
			await rejection(realize(fileAccess, DEFAULT_LIMITS))
		).to.have.property('code', 'invalid-request');

		const invalid = templateRequest();
		invalid.input.template = 'p= {';
		expect(await rejection(realize(invalid, DEFAULT_LIMITS))).to.have.property(
			'code',
			'realisation-error'
		);

		const looping = templateRequest();
		looping.input.template = '- while (true) {}';
		expect(
			await rejection(
				realize(looping, { ...DEFAULT_LIMITS, templateTimeoutMs: 100 })
			)
		).to.have.property('code', 'resource-limit');
	});

	it('normalises upstream errors without mutating requests', async () => {
		const request = englishRequest();
		request.input.structure = { terminal: 'N', lemma: 'not-in-the-lexicon' };
		const before = structuredClone(request);
		expect(await rejection(realize(request, DEFAULT_LIMITS))).to.be.instanceOf(
			ServiceError
		);
		expect(request).to.deep.equal(before);
	});

	it('ignores incomplete envelopes during the structural pre-check', () => {
		for (const value of [
			null,
			{ input: null },
			{ input: { structure: null } },
		]) {
			expect(inspectRequestStructure(value, DEFAULT_LIMITS)).to.equal(
				undefined
			);
		}
		expect(inspectRequestStructure(templateRequest(), DEFAULT_LIMITS)).to.equal(
			2
		);
	});

	it('normalises an empty structure rejected by the upstream engine', async () => {
		const request = englishRequest();
		request.input.structure = {} as never;
		expect(await rejection(realize(request, DEFAULT_LIMITS))).to.have.property(
			'code',
			'realisation-error'
		);
	});

	it('reports its engine, features, and active limits', () => {
		const result = capabilities(DEFAULT_LIMITS);
		expect(result.engines.map((engine) => engine.name)).to.deep.equal([
			'jsRealB',
			'RosaeNLG',
		]);
		expect(result.modes.surface_realization.languages).to.deep.equal([
			'en',
			'fr',
		]);
		expect(result.modes.surface_realization.representations).to.include(
			'dependency'
		);
		expect(result.modes.template_generation.features).to.include('anaphora');
		expect(result.coverage.percentage).to.equal(100);
		expect(result.limits.maxNodes).to.equal(DEFAULT_LIMITS.maxNodes);
		expect(result.limits.templateTimeoutMs).to.equal(
			DEFAULT_LIMITS.templateTimeoutMs
		);
	});
});
