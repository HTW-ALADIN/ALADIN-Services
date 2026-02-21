import { JSONPath } from 'jsonpath-plus';
import type { AdditionalOperation, RulesLogic } from 'json-logic-js';

import { IValueInstantiator, IInstantiatorOptions } from '../types';
import { GraphSchema } from '../../../types/graph.schema';
import { logger } from '../../../utils/logger';
import { LogicEngine } from 'json-logic-engine';

type JsonLogicRule = RulesLogic<AdditionalOperation>;

export interface JsonLogicInstantiatorOptions extends IInstantiatorOptions {
	rule: RulesLogic<AdditionalOperation>; // Array of rules to evaluate
	data?: unknown; // Array of rules to evaluate
	match: GraphSchema; // Map of matches for resolving placeholders
}

export enum JsonLogicErrors {
	'RulesNotProvided' = 'JsonLogic value instantiation: "rules" parameter needs to be provided.',
	'MatchNotProvided' = 'JsonLogic value instantiation: "match" parameter needs to be provided.',
	'EvaluationFailed' = 'JsonLogic value instantiation: Evaluating jsonLogic rule failed.',
}

export enum JsonPathErrors {
	'PathAmbigous' = 'JsonLogic value instantiation: JSON Path result is ambigous.',
	'PathUndefined' = 'JsonLogic value instantiation: JSON Path result is undefined.',
	'PathUnresolvable' = 'JSON Path could not be resolved',
}

export class JsonLogicInstantiator
	implements IValueInstantiator<JsonLogicInstantiatorOptions>
{
	readonly _instantiatorKey = 'jsonLogic';

	get instantiatorKey() {
		return this._instantiatorKey;
	}

	private logicEngine = new LogicEngine();

	public instantiateValue(
		args: JsonLogicInstantiatorOptions
	): string | number | boolean {
		this.validateArgs(args);

		const { rule, data, match } = args;
		return this.resolveJsonLogicRule(rule, match, data);
	}

	public instantiate(args: JsonLogicInstantiatorOptions) {
		return this.instantiateValue(args);
	}

	private validateArgs(args: JsonLogicInstantiatorOptions) {
		if (!args.rule) {
			throw new Error(JsonLogicErrors.RulesNotProvided);
		}

		if (!args.match) {
			throw new Error(JsonLogicErrors.MatchNotProvided);
		}
	}

	private resolveJsonLogicRule(
		rule: RulesLogic<AdditionalOperation>,
		graph: GraphSchema,
		data?: unknown
	): string | number | boolean {
		logger.info(`JsonLogicInstantiator: Start instantiating JsonLogic Value`);
		if (rule && typeof rule === 'object') {
			rule = this.replacePlaceholderValues(rule, graph);
		}

		if (data && typeof data === 'object') {
			data = this.replacePlaceholderValues(data, graph);
		}

		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		if (!data && (rule as any)?.var) {
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			rule = { preserve: (rule as any).var };
		}

		try {
			// since JsonLogic results can be different data types (e.g. arrays)
			// we need to turn these into strings if not primary data type

			const result = this.logicEngine.run(rule, data);
			if (['string', 'boolean', 'number'].includes(typeof result)) {
				logger.info(
					{ result },
					`JsonLogicInstantiator: JsonValue successfully instantiated.`
				);
				return result;
			} else if (result === null) {
				logger.info(
					`JsonLogicInstantiator: JsonValue instantiation returned no result.`
				);
				return '';
			} else {
				logger.info(
					{ result },
					`JsonLogicInstantiator: JsonValue instantiated and transformed to string.`
				);
				return String(result);
			}
		} catch (err) {
			logger.error(
				{ err },
				`JsonLogicInstantiator: JsonValue instantiation failed.`
			);
			throw new Error(JsonLogicErrors.EvaluationFailed);
		}
	}

	private replacePlaceholderValues(data: object, graph: GraphSchema) {
		for (const [key, value] of Object.entries(data)) {
			if (Array.isArray(value)) {
				(data as AdditionalOperation)[key] = value.map((item) =>
					this.resolveSearchGraphValue(item, graph)
				);
			} else if (typeof value === 'string') {
				(data as AdditionalOperation)[key] = this.resolveSearchGraphValue(
					value,
					graph
				);
			}
		}
		return data;
	}

	private resolveSearchGraphValue(value: JsonLogicRule, graph: GraphSchema) {
		if (value && typeof value === 'object') {
			// eslint-disable-next-line prefer-const
			for (let [key, subValue] of Object.entries(value)) {
				if (Array.isArray(subValue)) {
					subValue = subValue.map((item) => {
						const resolvedItem = this.resolveSearchGraphValue(item, graph);
						return resolvedItem;
					});
				} else if (typeof subValue === 'string') {
					subValue = this.resolveSearchGraphValue(subValue, graph);
				}
				// TODO: fix typing?
				(value as AdditionalOperation)[key] = subValue;
			}
		}
		if (value && typeof value === 'string' && value.startsWith('$.')) {
			let result = [];

			try {
				result = JSONPath({ path: value, json: graph, wrap: false });
			} catch (error) {
				console.log(error);
				throw new Error(JsonPathErrors.PathUnresolvable);
			}

			if (!result) {
				// No result is a valid option.
				logger.debug(
					`JsonLogicInstantiator: JSON Path '${value}' not found in searchgraph match`
				);
				return '';
			}
			if (result.length > 1) {
				throw new Error(JsonPathErrors.PathAmbigous);
			}
			return result.shift();
		} else {
			return value;
		}
	}
}
