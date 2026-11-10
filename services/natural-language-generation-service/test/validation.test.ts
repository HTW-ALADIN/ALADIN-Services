import { expect } from 'chai';
import { describe, it } from 'node:test';
import { ServiceError, toProblem } from '../src/errors.js';
import { validateGenerateRequest } from '../src/validation.js';
import { englishRequest, templateRequest } from './fixtures.js';

describe('request validation', () => {
	it('accepts the documented request', () => {
		expect(validateGenerateRequest(englishRequest())).to.deep.equal(
			englishRequest()
		);
		expect(validateGenerateRequest(templateRequest())).to.deep.equal(
			templateRequest()
		);
	});

	it('rejects invalid template-mode discriminators and data', () => {
		for (const value of [
			{ ...templateRequest(), backend: 'jsrealb' },
			{ ...templateRequest(), language: 'en' },
			{
				...templateRequest(),
				input: { template: '', data: {} },
			},
			{
				...templateRequest(),
				input: { template: 'p hello', data: { value: undefined } },
			},
		]) {
			expect(() => validateGenerateRequest(value))
				.to.throw(ServiceError)
				.with.property('code', 'invalid-request');
		}
	});

	it('rejects JavaScript expressions, unknown properties, and nested languages', () => {
		for (const value of [
			null,
			{ expression: 'S(N("cat"))' },
			{
				...englishRequest(),
				input: {
					representation: 'constituent',
					structure: { terminal: 'N', lemma: 'cat', props: { eval: 'x' } },
				},
			},
			{
				...englishRequest(),
				input: {
					representation: 'constituent',
					structure: { terminal: 'N', lemma: 'cat', lang: 'fr' },
				},
			},
		]) {
			expect(() => validateGenerateRequest(value))
				.to.throw(ServiceError)
				.with.property('code', 'invalid-request');
		}
	});

	it('rejects false for action-only properties', () => {
		const request = englishRequest();
		request.input.structure = {
			terminal: 'N',
			lemma: 'cat',
			props: { pro: false } as never,
		};
		expect(() => validateGenerateRequest(request)).to.throw(ServiceError);
	});

	it('creates RFC 9457-style problem details', () => {
		const problem = toProblem(
			new ServiceError('invalid-request', 400, 'Invalid request', 'bad body'),
			'/v1/generate'
		);
		expect(problem).to.include({ status: 400, instance: '/v1/generate' });
		expect(problem.type).to.contain('#invalid-request');
	});
});
