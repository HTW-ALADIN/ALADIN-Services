import { defineConfig } from 'vitest/config';

export default defineConfig({
	test: {
		// Look for tests only in the /test directory
		include: ['test/**/*.test.ts'],
		// Run global setup before any test file
		setupFiles: ['test/setup.ts'],
		// Node environment — no DOM needed for a backend service
		environment: 'node',
		// Show a detailed per-test reporter in the terminal
		reporters: ['verbose'],
		coverage: {
			provider: 'v8',
			include: ['src/**/*.ts'],
			exclude: ['src/index.ts', 'src/test-page/**'],
			reporter: ['text', 'lcov'],
		},
		// PGlite starts a WASM Postgres instance per suite. Under parallel
		// workers the initialisation + DDL in beforeAll hooks can exceed the
		// default budget on slower CI runners, so allow generous headroom.
		testTimeout: 8000,
		hookTimeout: 30000,
	},
});
