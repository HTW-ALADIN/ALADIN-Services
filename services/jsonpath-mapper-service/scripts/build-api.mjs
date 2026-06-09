#!/usr/bin/env node
import { build } from 'esbuild';
import { readFileSync, cpSync, rmSync } from 'fs';

// Read version and description from package.json
const pkg = JSON.parse(readFileSync('./package.json', 'utf8'));
const PKG_VERSION = pkg.version;
const PKG_DESCRIPTION = pkg.description;

const shared = {
  bundle: true,
  platform: 'node',
  target: 'node22',
  format: 'cjs',
  minify: true,
};

// Clean dist directory
rmSync('dist', { recursive: true, force: true });

await Promise.all([
  // API server bundle
  build({
    ...shared,
    entryPoints: ['src/api/index.ts'],
    outfile: 'dist/api.cjs',
    // Shim import.meta.url → pathToFileURL(__filename) so that packages like
    // @fastify/swagger-ui can resolve __dirname for their static assets.
    inject: ['./import-meta-url.js'],
    define: {
      'import.meta.url': 'import_meta_url',
      '__PKG_VERSION__': JSON.stringify(PKG_VERSION),
      '__PKG_DESCRIPTION__': JSON.stringify(PKG_DESCRIPTION),
    },
  }),
  // CLI bundle
  build({
    ...shared,
    entryPoints: ['src/cli.ts'],
    outfile: 'dist/cli.cjs',
  }),
]);

// Copy @fastify/swagger-ui static files so they can be served at runtime
cpSync('node_modules/@fastify/swagger-ui/static', 'dist/static', { recursive: true });
