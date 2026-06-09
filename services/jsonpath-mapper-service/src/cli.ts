#!/usr/bin/env node

import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import mapJson from './json-mapper.js';
import type { MappingTemplate } from './models/Template.js';

function usage(): never {
	console.error(`Usage: jsonpath-mapper <data.json> <template.json> [-o output.json]

Arguments:
  data.json       Path to the source JSON file
  template.json   Path to the mapping template JSON file

Options:
  -o, --output    Write result to a file instead of stdout
  -h, --help      Show this help message

Note: Template values that require JavaScript functions ($formatting,
$return, $disable) cannot be expressed in JSON. Use the npm library
directly for those cases.`);
	process.exit(1);
}

function main() {
	const args = process.argv.slice(2);

	if (args.includes('-h') || args.includes('--help') || args.length < 2) {
		usage();
	}

	let dataPath: string | undefined;
	let templatePath: string | undefined;
	let outputPath: string | undefined;

	for (let i = 0; i < args.length; i++) {
		if (args[i] === '-o' || args[i] === '--output') {
			outputPath = args[++i];
			if (!outputPath) {
				console.error('Error: -o requires a file path argument');
				process.exit(1);
			}
		} else if (!dataPath) {
			dataPath = args[i];
		} else if (!templatePath) {
			templatePath = args[i];
		} else {
			console.error(`Error: unexpected argument "${args[i]}"`);
			usage();
		}
	}

	if (!dataPath || !templatePath) {
		usage();
	}

	let data: unknown;
	try {
		const raw =
			dataPath === '-'
				? readFileSync(0, 'utf-8')
				: readFileSync(resolve(dataPath), 'utf-8');
		data = JSON.parse(raw);
	} catch (err) {
		console.error(
			`Error reading data file "${dataPath}":`,
			(err as Error).message
		);
		process.exit(1);
	}

	let template: MappingTemplate<unknown>;
	try {
		template = JSON.parse(readFileSync(resolve(templatePath), 'utf-8'));
	} catch (err) {
		console.error(
			`Error reading template file "${templatePath}":`,
			(err as Error).message
		);
		process.exit(1);
	}

	const result = mapJson(data, template);
	const output = JSON.stringify(result, null, 2);

	if (outputPath) {
		writeFileSync(resolve(outputPath), output + '\n', 'utf-8');
	} else {
		console.log(output);
	}
}

main();
