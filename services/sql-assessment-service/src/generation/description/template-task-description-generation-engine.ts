import {
	AST,
	BaseFrom,
	Binary,
	ColumnRefItem,
	Join,
	Select,
} from 'node-sql-parser';
import { getTemplates } from './sql-templates';
import {
	EntityType,
	IAliasMap,
	IParsedTable,
} from '../../shared/interfaces/domain';
import { SupportedLanguage } from '../../shared/i18n';
import { SurfaceRealizationService } from './surface-realization-service';

// ---------------------------------------------------------------------------
// Internal helper types
// ---------------------------------------------------------------------------

/** One hop in a normalised JOIN chain, produced before entity-type filtering. */
interface JoinHop {
	table: string;
	joinType: string;
	condition: Binary | string | undefined;
}

// ---------------------------------------------------------------------------
// Engine
// ---------------------------------------------------------------------------

export class TemplateTaskDescriptionGenerationEngine {
	private readonly columnPattern = /([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)/g;
	private readonly aggregateFunctionPattern =
		/(MAX|MIN|SUM|AVG|COUNT)\((.*?)\)/i;

	private readonly surfaceRealization = new SurfaceRealizationService();

	// -------------------------------------------------------------------------
	// Public API
	// -------------------------------------------------------------------------

	/**
	 * Converts a parsed SQL AST into a human-readable task description.
	 *
	 * @param query          - The root AST node returned by node-sql-parser.
	 * @param schema         - Database / schema name used in sentence framing.
	 * @param schemaAliasMap - Optional display-name overrides for tables / columns.
	 * @param tables         - Optional full schema metadata; when provided the engine
	 *                         uses entity-type information (weak / associative entities)
	 *                         to simplify JOIN descriptions.
	 * @param lang           - Language code for the output description (default: 'en').
	 */
	public generateTaskFromQuery(config: {
		query: AST;
		schema: string;
		schemaAliasMap?: IAliasMap;
		tables?: IParsedTable[];
		lang?: SupportedLanguage;
	}): string {
		const { query, schema, schemaAliasMap, tables } = config;
		const lang = config.lang ?? 'en';
		return this.traverseAST(query, schema, schemaAliasMap, tables, lang);
	}

	// -------------------------------------------------------------------------
	// AST traversal
	// -------------------------------------------------------------------------

	private traverseAST(
		node: AST,
		schema: string,
		schemaAliasMap?: IAliasMap,
		tables?: IParsedTable[],
		lang: SupportedLanguage = 'en',
	): string {
		if (!node) return '';

		switch (node.type) {
			case 'select':
				return this.handleSelect(node, schema, schemaAliasMap, tables, lang);
			default:
				return getTemplates(lang).UNSUPPORTED_QUERY;
		}
	}

	private handleSelect(
		node: Select,
		schema: string,
		schemaAliasMap?: IAliasMap,
		tables?: IParsedTable[],
		lang: SupportedLanguage = 'en',
	): string {
		const T = getTemplates(lang);
		let result = '';
		const isSelectAll =
			node.columns.length === 1 &&
			(node.columns[0] as any).expr?.column === '*';
		// node-sql-parser emits distinct as { type: 'DISTINCT' } when present.
		const isDistinct = (node as any).distinct?.type === 'DISTINCT';

		// Build an alias→table map so that column references using SQL aliases
		// (e.g. e1.first_name in a self-join) resolve to the real table name.
		const aliasMap = this.buildAliasMap(
			Array.isArray(node.from) ? node.from : [],
		);

		if (Array.isArray(node.from)) {
			if ((node.from as Join[]).some((fromItem) => fromItem?.join)) {
				// ── JOIN query ────────────────────────────────────────────────
				const columns = isSelectAll
					? '*'
					: (node.columns as any[])
							.map((col) =>
								this.getColumnName(col.expr, aliasMap, schemaAliasMap, lang),
							)
							.join(` ${T.AND_JOINER} `);

				if (isSelectAll) {
					result += T.SELECT_ALL_JOIN.replace('{database}', schema);
				} else if (isDistinct) {
					result += T.SELECT_DISTINCT_COLUMNS_JOIN.replace(
						'{columns}',
						columns,
					).replace('{database}', schema);
				} else {
					result += T.SELECT_COLUMNS_JOIN.replace('{columns}', columns).replace(
						'{database}',
						schema,
					);
				}

				// Collect all JOIN hops first so we can look-ahead for weak entities.
				const baseTableRaw =
					(node.from[0] as BaseFrom)?.table || 'an unknown table';
				const hops: JoinHop[] = (node.from as Join[])
					.filter((j) => j.join)
					.map((j) => ({
						table: j.table,
						joinType: j.join!.toUpperCase(),
						condition: j.on,
					}));

				result += this.renderJoinHops(
					baseTableRaw,
					hops,
					aliasMap,
					schemaAliasMap,
					tables,
					lang,
				);
			} else if (
				(node.from as BaseFrom[]).every((fromItem) => fromItem?.table)
			) {
				// ── Simple (no JOIN) query ────────────────────────────────────
				const table = (node.from[0] as BaseFrom)?.table || 'an unknown table';
				const columns = isSelectAll
					? '*'
					: (node.columns as any[])
							.map((col) =>
								this.getColumnName(col.expr, aliasMap, schemaAliasMap, lang),
							)
							.join(` ${T.AND_JOINER} `);

				if (isSelectAll) {
					result += T.SELECT_ALL.replace(
						'{table}',
						this.formatTableName(table, schemaAliasMap, lang),
					).replace('{database}', schema);
				} else if (isDistinct) {
					result += T.SELECT_DISTINCT_COLUMNS.replace(
						'{columns}',
						columns,
					).replace('{database}', schema);
				} else {
					result += T.SELECT_COLUMNS.replace('{columns}', columns)
						.replace(
							'{table}',
							this.formatTableName(table, schemaAliasMap, lang),
						)
						.replace('{database}', schema);
				}
			} else {
				result += T.UNSUPPORTED_FROM;
			}
		} else {
			result += T.INVALID_FROM;
		}

		// ── Clauses ──────────────────────────────────────────────────────────

		if (node.where) {
			const condition = this.handleCondition(
				node.where,
				aliasMap,
				schemaAliasMap,
				tables,
				lang,
			);
			result += ' ' + T.WHERE.replace('{condition}', condition);
		}

		if (
			node.groupby &&
			(node.groupby as any).columns &&
			(node.groupby as any).columns.length > 0
		) {
			const groupByColumns = (node.groupby as any).columns
				.map((col: any) =>
					this.getColumnName(col, aliasMap, schemaAliasMap, lang),
				)
				.join(', ');
			result += ' ' + T.GROUP_BY.replace('{columns}', groupByColumns);
		}

		if (node.having) {
			const havingCondition = this.handleCondition(
				node.having,
				aliasMap,
				schemaAliasMap,
				tables,
				lang,
			);
			result += ' ' + T.HAVING.replace('{condition}', havingCondition);
		}

		if (node.orderby) {
			const orderByColumns = (node.orderby as any[])
				.map((col: any) => {
					const columnName = this.getColumnName(
						col.expr,
						aliasMap,
						schemaAliasMap,
						lang,
					);
					const orderLabel =
						col.type?.toUpperCase() === 'DESC' ? T.ORDER_DESC : T.ORDER_ASC;
					return T.ORDER_BY_COLUMN.replace('{column}', columnName).replace(
						'{direction}',
						orderLabel,
					);
				})
				.join(', ');
			result += ' ' + T.ORDER_BY.replace('{columns}', orderByColumns);
		}

		// ── LIMIT / OFFSET ───────────────────────────────────────────────────
		result += this.handleLimit(node, lang);

		// ── Set operations (UNION / INTERSECT / EXCEPT) ──────────────────────
		const nodeAny = node as any;
		if (nodeAny._next && nodeAny.set_op) {
			const setOpKey = (nodeAny.set_op as string)
				.toUpperCase()
				.replace(/ /g, '_');
			const rightDesc = this.traverseAST(
				nodeAny._next as AST,
				schema,
				schemaAliasMap,
				tables,
				lang,
			);
			const template = T[setOpKey];
			result = template
				? template.replace('{left}', result).replace('{right}', rightDesc)
				: `${result} ${nodeAny.set_op.toUpperCase()} ${rightDesc}`;
		}

		return result;
	}

	// -------------------------------------------------------------------------
	// JOIN rendering — with weak / associative entity skipping
	// -------------------------------------------------------------------------

	/**
	 * Renders the JOIN portion of the description.
	 *
	 * When `tables` is provided the method inspects each hop's entity type.
	 * A weak or associative entity that acts as a bridge between two strong
	 * entities is skipped; the flanking strong-entity pair is described using
	 * the WEAK_BRIDGE template instead.
	 */
	private renderJoinHops(
		baseTableRaw: string,
		hops: JoinHop[],
		aliasMap: Record<string, string>,
		schemaAliasMap?: IAliasMap,
		tables?: IParsedTable[],
		lang: SupportedLanguage = 'en',
	): string {
		const T = getTemplates(lang);
		let result = '';
		let prevStrongTableRaw = baseTableRaw;
		let i = 0;

		while (i < hops.length) {
			const hop = hops[i];
			const isSelf =
				this.formatTableName(prevStrongTableRaw, schemaAliasMap, lang) ===
				this.formatTableName(hop.table, schemaAliasMap, lang);

			// ── SELF JOIN ────────────────────────────────────────────────────
			if (isSelf) {
				const baseDisplay = this.formatTableName(
					prevStrongTableRaw,
					schemaAliasMap,
					lang,
				);
				const condition = this.handleJoinCondition(
					hop.condition,
					aliasMap,
					schemaAliasMap,
					lang,
				);
				result +=
					' ' +
					T.SELF_JOIN.replace('{table}', baseDisplay).replace(
						'{condition}',
						condition,
					);
				i++;
				continue;
			}

			// ── Weak / associative bridge detection ──────────────────────────
			if (tables && this.isWeakOrAssociative(hop.table, tables)) {
				// Look ahead: is there a next hop to bridge to?
				const nextHop = hops[i + 1];
				if (nextHop && !this.isWeakOrAssociative(nextHop.table, tables)) {
					// Emit a single WEAK_BRIDGE sentence for prev → next
					const t1 = this.formatTableName(
						prevStrongTableRaw,
						schemaAliasMap,
						lang,
					);
					const t2 = this.formatTableName(nextHop.table, schemaAliasMap, lang);
					result +=
						' ' + T.WEAK_BRIDGE.replace('{table1}', t1).replace('{table2}', t2);
					prevStrongTableRaw = nextHop.table;
					i += 2; // consume both the bridge and the next hop
					continue;
				}
				// If the weak entity is the last hop (explicitly targeted), fall
				// through to the normal rendering path below.
			}

			// ── Normal JOIN ──────────────────────────────────────────────────
			const joinTemplate = this.getJoinTemplate(hop.joinType, lang);
			const t1 = this.formatTableName(prevStrongTableRaw, schemaAliasMap, lang);
			const t2 = this.formatTableName(hop.table, schemaAliasMap, lang);
			const condition = this.handleJoinCondition(
				hop.condition,
				aliasMap,
				schemaAliasMap,
				lang,
			);

			result +=
				' ' +
				joinTemplate
					.replace('{table1}', t1)
					.replace('{table}', t1)
					.replace('{table2}', t2)
					.replace('{condition}', condition);

			prevStrongTableRaw = hop.table;
			i++;
		}

		return result;
	}

	// -------------------------------------------------------------------------
	// LIMIT / OFFSET
	// -------------------------------------------------------------------------

	private handleLimit(node: Select, lang: SupportedLanguage = 'en'): string {
		const T = getTemplates(lang);
		const limitNode = (node as any).limit;
		if (!limitNode) return '';

		// node-sql-parser stores limit as { seperator: '', value: [LimitValue, ...] }
		// When LIMIT n OFFSET m is present, value has two elements.
		const values: any[] = limitNode.value ?? [];
		if (values.length === 0) return '';

		const limitVal: number | null = values[0]?.value ?? null;
		const offsetVal: number | null = values[1]?.value ?? null;

		if (limitVal !== null && offsetVal !== null) {
			return (
				' ' +
				T.LIMIT_OFFSET.replace('{count}', String(limitVal)).replace(
					'{offset}',
					String(offsetVal),
				)
			);
		}
		if (limitVal !== null) {
			return ' ' + T.LIMIT.replace('{count}', String(limitVal));
		}
		return '';
	}

	// -------------------------------------------------------------------------
	// Alias map
	// -------------------------------------------------------------------------

	private buildAliasMap(from: any[]): Record<string, string> {
		const map: Record<string, string> = {};
		for (const entry of from) {
			if (entry.as && entry.table) {
				map[entry.as] = entry.table;
			}
		}
		return map;
	}

	// -------------------------------------------------------------------------
	// JOIN condition
	// -------------------------------------------------------------------------

	private handleJoinCondition(
		on: string | any,
		aliasMap: Record<string, string> = {},
		schemaAliasMap?: IAliasMap,
		lang: SupportedLanguage = 'en',
	): string {
		const T = getTemplates(lang);
		let left: any, operator: string, right: any;
		if (typeof on === 'string') {
			[left, operator, right] = this.parseConditionString(on);
		} else if (on?.operator) {
			left = on.left;
			right = on.right;
			operator = on.operator;
		} else {
			return T.UNSPECIFIED_CONDITION;
		}
		const operatorTemplate = T[operator!] || `{left} ${operator!} {right}`;
		const formattedLeft = this.getColumnName(
			left,
			aliasMap,
			schemaAliasMap,
			lang,
		);
		const formattedRight =
			right?.value ?? this.getColumnName(right, aliasMap, schemaAliasMap, lang);

		return operatorTemplate
			.replace('{left}', formattedLeft)
			.replace('{right}', formattedRight);
	}

	// -------------------------------------------------------------------------
	// WHERE / HAVING condition
	// -------------------------------------------------------------------------

	private handleCondition(
		condition: any,
		aliasMap: Record<string, string> = {},
		schemaAliasMap?: IAliasMap,
		tables?: IParsedTable[],
		lang: SupportedLanguage = 'en',
	): string {
		const T = getTemplates(lang);
		if (!condition) return T.UNSPECIFIED_CONDITION;

		// AND / OR
		if (condition.operator === 'AND' || condition.operator === 'OR') {
			const left = this.handleCondition(
				condition.left,
				aliasMap,
				schemaAliasMap,
				tables,
				lang,
			);
			const right = this.handleCondition(
				condition.right,
				aliasMap,
				schemaAliasMap,
				tables,
				lang,
			);
			const template =
				T[condition.operator.toUpperCase()] ||
				`{left} ${condition.operator} {right}`;
			return template.replace('{left}', left).replace('{right}', right);
		}

		// EXISTS / NOT EXISTS
		// node-sql-parser emits EXISTS as a function node:
		//   { type: 'function', name: { name: [{ value: 'EXISTS' }] }, args: { type: 'expr_list', value: [{ ast: Select }] } }
		if (condition.type === 'function') {
			const funcName: string = (
				condition.name?.name?.[0]?.value ?? ''
			).toUpperCase();
			if (funcName === 'EXISTS' || funcName === 'NOT EXISTS') {
				const templateKey = funcName === 'EXISTS' ? 'EXISTS' : 'NOT_EXISTS';
				const subAst = condition.args?.value?.[0]?.ast;
				const subDesc = subAst
					? this.traverseAST(subAst as AST, '', schemaAliasMap, tables, lang)
					: T.UNSPECIFIED_CONDITION;
				return T[templateKey].replace('{condition}', subDesc);
			}
		}

		if (condition.type === 'binary_expr') {
			// IS NULL / IS NOT NULL
			if (['IS', 'IS NOT'].includes(condition.operator)) {
				if (condition.right?.type === 'null') {
					const operatorTemplate = T[`${condition.operator} NULL`];
					const left = this.getColumnName(
						condition.left,
						aliasMap,
						schemaAliasMap,
						lang,
					);
					return operatorTemplate.replace('{left}', left);
				}
			}

			const operatorTemplate =
				T[condition.operator] || `{left} ${condition.operator} {right}`;
			const left = this.getColumnName(
				condition.left,
				aliasMap,
				schemaAliasMap,
				lang,
			);
			let right =
				condition.right?.value ??
				this.getColumnName(condition.right, aliasMap, schemaAliasMap, lang);

			if (
				condition.operator === 'BETWEEN' &&
				Array.isArray(condition.right?.value)
			) {
				right = `${condition.right.value[0].value} and ${condition.right.value[1].value}`;
			}

			// Fix: IN and NOT IN both need the array-to-list treatment.
			// node-sql-parser stores the list as an expr_list node: { type: 'expr_list', value: [...] }
			if (
				(condition.operator === 'IN' || condition.operator === 'NOT IN') &&
				condition.right?.type === 'expr_list' &&
				Array.isArray(condition.right.value)
			) {
				right = condition.right.value.map((item: any) => item.value).join(', ');
			}

			return operatorTemplate
				.replace('{left}', left)
				.replace('{right}', String(right));
		}

		return T.UNSPECIFIED_CONDITION;
	}

	// -------------------------------------------------------------------------
	// Column / expression name resolution
	// -------------------------------------------------------------------------

	private getColumnName(
		column: any,
		aliasMap: Record<string, string> = {},
		schemaAliasMap?: IAliasMap,
		lang: SupportedLanguage = 'en',
	): string {
		const T = getTemplates(lang);
		if (!column) return T.UNKNOWN_COLUMN;

		const table = column.table ?? column.args?.expr?.table ?? undefined;
		const col = column.column ?? column.args?.expr?.column ?? undefined;

		const resolvedTable = table ? aliasMap[table] ?? table : null;
		const { resolvedColumnName, resolved } = this.resolveColumnDisplayName(
			resolvedTable,
			col,
			schemaAliasMap,
			lang,
		);

		const columnName =
			resolved || (!resolved && typeof resolvedColumnName == 'string')
				? resolvedColumnName
				: column.name?.toUpperCase();

		// ── Aggregate function ───────────────────────────────────────────────
		if (column.type === 'aggr_func') {
			const func = column.name;
			const arg = column.args?.expr;
			if (func && arg) {
				const aggTemplate = T[func] ?? func.toLowerCase();
				const col = resolved
					? columnName
					: typeof arg.column === 'string'
						? arg.column
						: arg.column?.expr?.value;
				return aggTemplate.replace(
					'{column}',
					this.surfaceRealization.formatName(
						col || T.UNKNOWN_COLUMN,
						lang,
						func,
					),
				);
			}
		}

		// ── Non-aggregate scalar function (e.g. COALESCE, UPPER, NOW) ───────
		if (column.type === 'function') {
			return this.handleScalarFunction(column, aliasMap, schemaAliasMap, lang);
		}

		// ── CASE expression ──────────────────────────────────────────────────
		if (column.type === 'case') {
			return this.handleCaseExpression(column, aliasMap, schemaAliasMap, lang);
		}

		// ── Plain column reference ───────────────────────────────────────────
		if (column.column) {
			const resolvedTable = column.table
				? aliasMap[column.table] ?? column.table
				: null;

			if (typeof column.column === 'string') {
				const displayTable = resolvedTable
					? this.resolveTableDisplayName(resolvedTable, schemaAliasMap, lang)
					: null;
				const { resolvedColumnName, resolved } = this.resolveColumnDisplayName(
					resolvedTable,
					column.column,
					schemaAliasMap,
					lang,
				);
				if (resolved) {
					return resolvedColumnName;
				}
				const tablePart = displayTable
					? `${T.COLUMN_PREFIX}${displayTable} `
					: '';
				return `${tablePart}${resolvedColumnName}`;
			} else if (column.column.expr) {
				const displayTable = resolvedTable
					? this.resolveTableDisplayName(resolvedTable, schemaAliasMap, lang)
					: null;
				const { resolvedColumnName, resolved } = this.resolveColumnDisplayName(
					resolvedTable,
					column.column.expr.value,
					schemaAliasMap,
					lang,
				);
				if (resolved) {
					return resolvedColumnName;
				}
				const tablePart = displayTable
					? `${T.COLUMN_PREFIX}${displayTable} `
					: '';
				return `${tablePart}${resolvedColumnName}`;
			}
		}

		// ── Boolean literal ──────────────────────────────────────────────────
		if (column.type === 'bool') {
			return String(column.value);
		}

		return T.UNAVAILABLE;
	}

	// -------------------------------------------------------------------------
	// Scalar function handler
	// -------------------------------------------------------------------------

	/**
	 * Produces a readable label for a non-aggregate SQL scalar function call.
	 *
	 * Well-known functions get a natural-language phrase from the template
	 * catalogue; all others fall back to "<function_name>(<arg1>, ...)"
	 * in lower-case.
	 */
	private handleScalarFunction(
		column: any,
		aliasMap: Record<string, string>,
		schemaAliasMap?: IAliasMap,
		lang: SupportedLanguage = 'en',
	): string {
		const T = getTemplates(lang);

		// node-sql-parser stores function name as: { name: [{ type, value }] }
		const funcName: string = (
			column.name?.name?.[0]?.value ??
			column.name ??
			''
		).toUpperCase();

		// Args are stored as an expr_list: { type: 'expr_list', value: [...] }
		const rawArgs: any[] =
			column.args?.value ?? (Array.isArray(column.args) ? column.args : []);

		const resolvedArgs = rawArgs.map((a: any) =>
			this.getColumnName(a, aliasMap, schemaAliasMap, lang),
		);

		const arg0 = resolvedArgs[0] ?? T.UNKNOWN_COLUMN;
		const arg1 = resolvedArgs[1] ?? T.UNKNOWN_COLUMN;

		switch (funcName) {
			case 'COALESCE':
				return T.FUNC_COALESCE.replace('{args}', resolvedArgs.join(', '));
			case 'NULLIF':
				return T.FUNC_NULLIF.replace('{arg1}', arg0).replace('{arg2}', arg1);
			case 'IFNULL':
			case 'ISNULL':
			case 'NVL':
				return T.FUNC_IFNULL.replace('{arg1}', arg0).replace('{arg2}', arg1);
			case 'UPPER':
				return T.FUNC_UPPER.replace('{arg}', arg0);
			case 'LOWER':
				return T.FUNC_LOWER.replace('{arg}', arg0);
			case 'TRIM':
				return T.FUNC_TRIM.replace('{arg}', arg0);
			case 'LENGTH':
			case 'LEN':
				return T.FUNC_LENGTH.replace('{arg}', arg0);
			case 'ROUND':
				return resolvedArgs[1]
					? T.FUNC_ROUND_DECIMAL.replace('{arg}', arg0).replace(
							'{decimals}',
							arg1,
						)
					: T.FUNC_ROUND.replace('{arg}', arg0);
			case 'ABS':
				return T.FUNC_ABS.replace('{arg}', arg0);
			case 'NOW':
			case 'CURRENT_TIMESTAMP':
				return T.FUNC_NOW;
			case 'CURRENT_DATE':
				return T.FUNC_CURRENT_DATE;
			case 'CONCAT':
				return T.FUNC_CONCAT.replace('{args}', resolvedArgs.join(', '));
			case 'SUBSTRING':
			case 'SUBSTR':
				return T.FUNC_SUBSTRING.replace('{arg}', arg0);
			case 'REPLACE':
				return T.FUNC_REPLACE.replace('{arg}', arg0);
			case 'CAST':
				return T.FUNC_CAST.replace('{arg}', arg0);
			default:
				return `${funcName.toLowerCase()}(${resolvedArgs.join(', ')})`;
		}
	}

	// -------------------------------------------------------------------------
	// CASE expression handler
	// -------------------------------------------------------------------------

	private handleCaseExpression(
		column: any,
		aliasMap: Record<string, string>,
		schemaAliasMap?: IAliasMap,
		lang: SupportedLanguage = 'en',
	): string {
		const T = getTemplates(lang);
		const args: any[] = column.args ?? [];
		const clauses: string[] = [];

		for (const arg of args) {
			if (arg.type === 'when') {
				const cond = this.handleCondition(
					arg.cond ?? arg.condition,
					aliasMap,
					schemaAliasMap,
					undefined,
					lang,
				);
				const result = this.getColumnName(
					arg.result ?? arg.then,
					aliasMap,
					schemaAliasMap,
					lang,
				);
				clauses.push(`${T.CASE_WHEN} ${cond} ${T.CASE_THEN} ${result}`);
			} else if (arg.type === 'else') {
				const result = this.getColumnName(
					arg.result ?? arg.value,
					aliasMap,
					schemaAliasMap,
					lang,
				);
				clauses.push(`${T.CASE_ELSE} ${result}`);
			}
		}

		const conditions =
			clauses.length > 0 ? clauses.join(', ') : T.VARIOUS_CONDITIONS;
		return T.CASE.replace('{conditions}', conditions);
	}

	// -------------------------------------------------------------------------
	// Condition string parser (fallback for raw string conditions)
	// -------------------------------------------------------------------------

	private parseConditionString(
		condition: string,
	): [ColumnRefItem, string, ColumnRefItem] {
		const operators = [
			'=',
			'!=',
			'<',
			'>',
			'<=',
			'>=',
			'LIKE',
			'IN',
			'BETWEEN',
			'NOT LIKE',
			'NOT IN',
		];

		let operator: string | null = null;
		for (const op of operators) {
			if (condition.includes(op)) {
				operator = op;
				break;
			}
		}

		if (!operator) {
			throw new Error('No valid operator found in condition');
		}

		const [left, right] = condition.split(operator).map((part) => part.trim());

		const parseColumn = (columnString: string): ColumnRefItem => {
			const match = columnString.match(/^([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)$/);
			if (match) {
				return { table: match[1], column: match[2], type: 'column_ref' };
			}
			return { table: '', column: columnString, type: 'column_ref' };
		};

		return [parseColumn(left), operator, parseColumn(right)];
	}

	// -------------------------------------------------------------------------
	// Display name helpers
	// -------------------------------------------------------------------------

	private formatTableName(
		tableName: string,
		schemaAliasMap?: IAliasMap,
		lang: SupportedLanguage = 'en',
	): string {
		const alias = schemaAliasMap?.tables?.[tableName];
		return this.surfaceRealization.formatName(alias ?? tableName, lang);
	}

	private resolveColumnDisplayName(
		tableName: string | null,
		columnName: string,
		schemaAliasMap?: IAliasMap,
		lang: SupportedLanguage = 'en',
	) {
		const alias = tableName
			? schemaAliasMap?.columns?.[tableName]?.[columnName]
			: undefined;
		return {
			resolved: !!alias,
			resolvedColumnName: this.surfaceRealization.formatName(
				alias ?? columnName,
				lang,
			),
		};
	}

	private resolveTableDisplayName(
		tableName: string,
		schemaAliasMap?: IAliasMap,
		lang: SupportedLanguage = 'en',
	): string {
		const alias = schemaAliasMap?.tables?.[tableName];
		return this.surfaceRealization.formatName(alias ?? tableName, lang);
	}

	// -------------------------------------------------------------------------
	// Entity type helpers
	// -------------------------------------------------------------------------

	/**
	 * Returns true if the named table is classified as Weak or Associative
	 * in the provided schema metadata. Returns false when `tables` is absent
	 * or the table is not found (safe default — no skipping).
	 */
	private isWeakOrAssociative(
		tableName: string,
		tables: IParsedTable[],
	): boolean {
		const entry = tables.find((t) => t.name === tableName);
		if (!entry) return false;
		return (
			entry.entityType === EntityType.Weak ||
			entry.entityType === EntityType.Associative
		);
	}

	// -------------------------------------------------------------------------
	// JOIN type → template
	// -------------------------------------------------------------------------

	private getJoinTemplate(
		joinType: string,
		lang: SupportedLanguage = 'en',
	): string {
		const T = getTemplates(lang);
		switch (joinType) {
			case 'INNER JOIN':
				return T.INNER_JOIN;
			case 'JOIN':
				return T.INNER_JOIN;
			case 'LEFT JOIN':
				return T.LEFT_JOIN;
			case 'RIGHT JOIN':
				return T.RIGHT_JOIN;
			case 'FULL JOIN':
				return T.FULL_JOIN;
			case 'SELF JOIN':
				return T.SELF_JOIN;
			case 'CROSS JOIN':
				return T.CROSS_JOIN;
			default:
				return T.UNSPECIFIED_JOIN;
		}
	}
}
