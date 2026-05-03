import { describe, it, expect } from 'vitest';
import { resolveFileFlag } from '../../src/cli/index';

describe('resolveFileFlag', () => {
	it('returns -1 when neither flag is present', () => {
		expect(resolveFileFlag([])).toBe(-1);
		expect(resolveFileFlag(['query:execute', '--stdin'])).toBe(-1);
	});

	it('returns the index of -f when only -f is present', () => {
		expect(resolveFileFlag(['cmd', '-f', 'body.json'])).toBe(1);
	});

	it('returns the index of --file when only --file is present', () => {
		expect(resolveFileFlag(['cmd', '--file', 'body.json'])).toBe(1);
	});

	it('prefers -f over --file when both are present (-f first)', () => {
		// args: ['cmd', '-f', 'a.json', '--file', 'b.json']
		const args = ['cmd', '-f', 'a.json', '--file', 'b.json'];
		const idx = resolveFileFlag(args);
		expect(idx).toBe(1);
		expect(args[idx + 1]).toBe('a.json');
	});

	it('prefers -f over --file when both are present (--file first)', () => {
		// args: ['cmd', '--file', 'a.json', '-f', 'b.json']
		const args = ['cmd', '--file', 'a.json', '-f', 'b.json'];
		const idx = resolveFileFlag(args);
		expect(idx).toBe(3);
		expect(args[idx + 1]).toBe('b.json');
	});
});
