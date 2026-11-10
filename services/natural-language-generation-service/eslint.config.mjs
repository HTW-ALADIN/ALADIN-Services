import globals from 'globals';
import js from '@eslint/js';
import ts from 'typescript-eslint';

export default [
	{ ignores: ['coverage/', 'dist/', 'node_modules/', 'openapi/'] },
	{ files: ['**/*.{js,mjs,ts}'] },
	{ languageOptions: { globals: globals.node } },
	js.configs.recommended,
	...ts.configs.recommended.map((config) => ({
		...config,
		files: ['**/*.ts'],
		rules: {
			...config.rules,
			'@typescript-eslint/no-explicit-any': 'off',
		},
	})),
];
