import { build } from 'esbuild';
import { chmod, cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const distDir = resolve('dist');
const staticSourceDir = resolve('src/static');
const staticTargetDir = resolve(distDir, 'static');
const swaggerUiStaticDir = resolve('node_modules/@fastify/swagger-ui/static');

const sharedOptions = {
	bundle: true,
	format: 'cjs',
	minify: true,
	platform: 'node',
	target: 'node22',
	// @grafeo-db/js ships a native Rust addon (.node file) that esbuild cannot bundle
	external: ['@grafeo-db/js', '@grafeo-db/js-linux-x64-gnu', '@grafeo-db/js-linux-arm64-gnu'],
};

await rm(distDir, { force: true, recursive: true });
await mkdir(distDir, { recursive: true });

await Promise.all([
	build({
		...sharedOptions,
		entryPoints: ['src/index.ts'],
		outfile: 'dist/index.js',
	}),
	build({
		...sharedOptions,
		entryPoints: ['src/cli.ts'],
		outfile: 'dist/cli.js',
	}),
]);

const cliEntry = resolve(distDir, 'cli.js');
const cliContent = await readFile(cliEntry, 'utf8');
if (!cliContent.startsWith('#!/usr/bin/env node')) {
	await writeFile(cliEntry, `#!/usr/bin/env node\n${cliContent}`, 'utf8');
}

await mkdir(staticTargetDir, { recursive: true });
// Copy src/static (project's own static files)
await cp(staticSourceDir, staticTargetDir, { recursive: true });
// Copy @fastify/swagger-ui static files for Swagger UI
await cp(swaggerUiStaticDir, staticTargetDir, { recursive: true });
await chmod(cliEntry, 0o755);
