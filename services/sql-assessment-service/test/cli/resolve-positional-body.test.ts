import { describe, it, expect } from 'vitest';
import { resolvePositionalBody } from '../../src/cli/index';

describe('resolvePositionalBody', () => {
	it('returns undefined for empty args', () => {
		expect(resolvePositionalBody([])).toBeUndefined();
	});

	it('returns undefined when args contains only the command', () => {
		expect(resolvePositionalBody(['query:execute'])).toBeUndefined();
	});

	it('returns undefined when all args are flags', () => {
		expect(resolvePositionalBody(['query:execute', '--stdin'])).toBeUndefined();
		expect(
			resolvePositionalBody(['query:execute', '--list', '--help']),
		).toBeUndefined();
	});

	it('returns JSON when it is immediately after the command (args[1])', () => {
		const json = '{"query":"SELECT 1"}';
		expect(resolvePositionalBody(['query:execute', json])).toBe(json);
	});

	it('skips --init-sql-file and its value, returns subsequent JSON', () => {
		const json = '{"query":"SELECT 1"}';
		expect(
			resolvePositionalBody([
				'query:execute',
				'--init-sql-file',
				'schema.sql',
				json,
			]),
		).toBe(json);
	});

	it('skips -f and its value, returns subsequent JSON', () => {
		const json = '{"query":"SELECT 1"}';
		expect(
			resolvePositionalBody(['query:execute', '-f', 'body.json', json]),
		).toBe(json);
	});

	it('skips --file and its value, returns subsequent JSON', () => {
		const json = '{"query":"SELECT 1"}';
		expect(
			resolvePositionalBody(['query:execute', '--file', 'body.json', json]),
		).toBe(json);
	});

	it('skips multiple flags-with-values before the JSON', () => {
		const json = '{"query":"SELECT 1"}';
		expect(
			resolvePositionalBody([
				'query:execute',
				'--init-sql-file',
				'schema.sql',
				'-f',
				'body.json',
				json,
			]),
		).toBe(json);
	});

	it('skips boolean flags interspersed before the JSON', () => {
		const json = '{"query":"SELECT 1"}';
		expect(
			resolvePositionalBody([
				'query:execute',
				'--init-sql-file',
				'schema.sql',
				'--verbose',
				json,
			]),
		).toBe(json);
	});

	it('returns undefined when a flags-with-values flag has no following value', () => {
		// --init-sql-file is last; no positional follows
		expect(
			resolvePositionalBody(['query:execute', '--init-sql-file']),
		).toBeUndefined();
	});
});
