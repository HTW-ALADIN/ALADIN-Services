import { expect } from 'chai';
import { afterEach, beforeEach, describe, it } from 'node:test';
import { DEFAULT_LIMITS, loadLimits } from '../src/config.js';

describe('configuration', () => {
	const keys = [
		'NLG_MAX_BODY_BYTES',
		'NLG_MAX_NODES',
		'NLG_MAX_DEPTH',
		'NLG_MAX_OUTPUT_BYTES',
		'NLG_TEMPLATE_TIMEOUT_MS',
	];
	const saved = new Map<string, string | undefined>();

	beforeEach(() => {
		for (const key of keys) {
			saved.set(key, process.env[key]);
			delete process.env[key];
		}
	});

	afterEach(() => {
		for (const key of keys) {
			const value = saved.get(key);
			if (value === undefined) delete process.env[key];
			else process.env[key] = value;
		}
	});

	it('uses defaults and accepts positive overrides', () => {
		expect(loadLimits()).to.deep.equal(DEFAULT_LIMITS);
		process.env.NLG_MAX_NODES = '25';
		expect(loadLimits().maxNodes).to.equal(25);
		process.env.NLG_TEMPLATE_TIMEOUT_MS = '250';
		expect(loadLimits().templateTimeoutMs).to.equal(250);
	});

	it('rejects invalid values', () => {
		for (const value of ['0', '-1', '1.5', 'word']) {
			process.env.NLG_MAX_DEPTH = value;
			expect(() => loadLimits()).to.throw('positive safe integer');
		}
	});
});
