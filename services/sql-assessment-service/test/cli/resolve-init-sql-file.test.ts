import { describe, it, expect } from 'vitest';
import * as path from 'path';
import { resolveInitSqlFile } from '../../src/cli/index';

describe('resolveInitSqlFile', () => {
	it('returns undefined when the flag is absent', () => {
		expect(resolveInitSqlFile([])).toBeUndefined();
		expect(resolveInitSqlFile(['query:execute', '--stdin'])).toBeUndefined();
	});

	it('throws when --init-sql-file is the last argument', () => {
		expect(() => resolveInitSqlFile(['--init-sql-file'])).toThrow(
			'--init-sql-file requires a path argument.',
		);
	});

	it('throws when --init-sql-file is followed by another flag', () => {
		expect(() => resolveInitSqlFile(['--init-sql-file', '--stdin'])).toThrow(
			'--init-sql-file requires a path argument.',
		);
	});

	it('returns the resolved absolute path when a valid path is provided', () => {
		const result = resolveInitSqlFile(['--init-sql-file', 'init.sql']);
		expect(result).toBe(path.resolve('init.sql'));
	});

	it('resolves the path relative to cwd for relative paths', () => {
		const result = resolveInitSqlFile([
			'--init-sql-file',
			'./fixtures/schema.sql',
		]);
		expect(result).toBe(path.resolve('./fixtures/schema.sql'));
	});

	it('passes through an already-absolute path unchanged', () => {
		const abs = '/absolute/path/to/init.sql';
		expect(resolveInitSqlFile(['--init-sql-file', abs])).toBe(abs);
	});
});
