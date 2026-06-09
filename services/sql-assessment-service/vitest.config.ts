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
		testTimeout: 8000,
		hookTimeout: 8000,
	},
});
