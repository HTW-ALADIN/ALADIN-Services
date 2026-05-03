export type EnvVarAppEnvironment = 'production' | 'development' | 'test';
export type EnvVarDbBackend = 'neo4j' | 'memory';

export interface AppEnvConfig {
	APP_ENV: EnvVarAppEnvironment;
	DB_BACKEND: EnvVarDbBackend;
}

export function getAppEnvConfig(): AppEnvConfig {
	const { APP_ENV, DB_BACKEND } = process.env as Record<string, string>;

	return {
		APP_ENV: (APP_ENV as EnvVarAppEnvironment) ?? 'production',
		DB_BACKEND: (DB_BACKEND as EnvVarDbBackend) ?? 'memory',
	};
}
