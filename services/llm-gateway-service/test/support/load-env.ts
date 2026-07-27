import { existsSync, readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ENV_FILE = resolve(__dirname, '../../.env');

/**
 * Minimal `.env` parser used only by tests that need real credentials for a
 * live external service (see `test/integration/real-provider.test.ts`).
 *
 * Intentionally does not mutate `process.env` — callers read the returned
 * map explicitly, so this can't accidentally leak real credentials into
 * unrelated tests that happen to run in the same process.
 *
 * Returns an empty object (all keys undefined) when `.env` does not exist,
 * so callers can decide to skip rather than fail.
 */
export function loadEnvFile(path: string = ENV_FILE): Record<string, string> {
	if (!existsSync(path)) {
		return {};
	}

	const result: Record<string, string> = {};
	const raw = readFileSync(path, 'utf-8');

	for (const line of raw.split('\n')) {
		const trimmed = line.trim();
		if (!trimmed || trimmed.startsWith('#')) {
			continue;
		}

		const eqIndex = trimmed.indexOf('=');
		const key = eqIndex === -1 ? trimmed : trimmed.slice(0, eqIndex);
		const value = eqIndex === -1 ? '' : trimmed.slice(eqIndex + 1);

		if (key) {
			result[key.trim()] = value.trim();
		}
	}

	return result;
}
