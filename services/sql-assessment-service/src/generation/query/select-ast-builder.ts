import {
	Select,
	Expr,
	ExpressionValue,
	ExprList,
	ColumnRefItem,
} from 'node-sql-parser';
import { ASTBuilder } from './ast-builder';
import { IParsedColumn, IPath } from '../../shared/interfaces/domain';
import { joinType, randomJoinTypes } from '../../shared/constants';
import { random, randomBoolean } from '../../shared/utils/random';
import { quoteIdentifier } from '../../shared/utils/identifier-quoting';

// Re-export for consumers that imported these from the old interfaces location
export type { joinType };

export class SelectASTBuilder implements ASTBuilder {
	private generatedAST: Select;
	private aliasedTables: string[] = [];

	constructor() {
		this.generatedAST = {
			type: 'select',
			columns: [],
			distinct: null,
			from: null,
			groupby: { columns: [], modifiers: [] },
			having: null,
			limit: null,
			options: null,
			orderby: null,
			where: null,
			with: null,
		};
	}

	buildSelect(selectColumns: IParsedColumn[], isGroupBy = false) {
		const columnArray: any[] = [];
		selectColumns.forEach((column) => {
			if (column.aggregation)
				columnArray.push({
					expr: {
						type: 'aggr_func',
						name: column.aggregation,
						args: {
							expr: {
								type: 'column_ref',
								table:
									isGroupBy &&
									this.generatedAST?.groupby?.columns?.length &&
									this.generatedAST?.groupby?.columns?.length > 0
										? (this.generatedAST?.groupby?.columns[0] as ColumnRefItem)
												.table
										: this.getAlias(column.tableName),
								column: column.name,
							},
						},
					},
				});
			else
				columnArray.push({
					expr: {
						type: 'column_ref',
						table:
							isGroupBy &&
							this.generatedAST?.groupby?.columns?.length &&
							this.generatedAST?.groupby?.columns?.length > 0
								? (this.generatedAST?.groupby?.columns[0] as ColumnRefItem)
										.table
								: this.getAlias(column.tableName),
						column: column.name,
					},
				});
		});
		this.generatedAST.columns = columnArray;
	}

	buildSelectAll() {
		this.generatedAST.columns = [
			{ expr: { type: 'column_ref', table: null, column: '*' } },
		];
	}

	buildFromWithJoin(
		schema: string,
		tableName: string,
		joinPath: IPath[],
		configuredJoinTypes: joinType[],
		depth: number,
	) {
		const join = [];
		const otherJoins = configuredJoinTypes.filter((val) => val !== 'SELF JOIN');
		let isFromSelfJoin = false;
		let isPreviousSelfJoin: boolean | undefined;
		for (let i = 0; i < depth; i++) {
			const currentTable = joinPath[i].tableName;
			const previousTable = joinPath[i - 1]?.tableName;
			const nextTable = joinPath[i + 1]?.tableName;
			if (!isFromSelfJoin) isFromSelfJoin = currentTable == tableName;
			const isSelfJoin =
				currentTable === previousTable ||
				currentTable == tableName ||
				currentTable == nextTable;
			const currentAlias =
				currentTable == tableName || currentTable == previousTable ? 2 : 1;
			if (isSelfJoin) {
				if (!this.aliasedTables.includes(currentTable))
					this.aliasedTables.push(currentTable);
			}
			const joinType =
				otherJoins.pop() || randomJoinTypes[random(randomJoinTypes.length)];

			join.push({
				db: schema,
				table: currentTable,
				as: isSelfJoin ? `${currentTable.charAt(0)}${currentAlias}` : null,
				join: joinType,
				on:
					joinType == 'CROSS JOIN'
						? null
						: isSelfJoin
							? this.buildJoinConditionOn(
									joinPath[i].relationKey,
									currentTable,
								)
							: isPreviousSelfJoin
								? this.buildJoinConditionOn(
										joinPath[i].relationKey,
										undefined,
										previousTable,
									)
								: this.buildJoinConditionOn(joinPath[i].relationKey),
			});
			isPreviousSelfJoin = isSelfJoin;
		}

		const from = [
			{
				db: schema,
				table: tableName,
				as: isFromSelfJoin ? `${tableName.charAt(0)}1` : null,
			},
			...join,
		];
		this.generatedAST.from = from;
	}

	private buildConjunctedWhere(expressionList: Expr[]): any {
		if (expressionList.length == 1) {
			return expressionList[0];
		}

		return {
			type: 'binary_expr',
			operator: randomBoolean() ? 'AND' : 'OR',
			left: expressionList.shift(),
			right: this.buildConjunctedWhere(expressionList),
		};
	}

	buildWhere(expressionList: Expr[]) {
		if (expressionList.length == 0) return;
		if (expressionList.length == 1) this.generatedAST.where = expressionList[0];
		else this.generatedAST.where = this.buildConjunctedWhere(expressionList);
	}

	buildWhereConstraint(
		operator: string,
		tableName: string,
		columnName: string,
		valueType: string,
		val: any,
	): Expr {
		return {
			type: 'binary_expr',
			operator: operator,
			left: {
				type: 'column_ref',
				table: this.getAlias(tableName),
				column: columnName,
			},
			right: { type: valueType, value: val },
		};
	}

	buildWhereConstraintValueList(
		operator: string,
		tableName: string,
		columnName: string,
		values: any[],
	): Expr {
		const valueList: ExpressionValue[] = [];
		values.forEach((value) => {
			valueList.push({ type: value.type, value: value.value });
		});

		const exprList: ExprList = { type: 'expr_list', value: valueList };
		return {
			type: 'binary_expr',
			operator: operator,
			left: {
				type: 'column_ref',
				table: this.getAlias(tableName),
				column: columnName,
			},
			right: exprList,
		};
	}

	buildFrom(schema: string, tableName: string) {
		const from = [
			{
				db: schema,
				table: tableName,
				as: null,
			},
		];
		this.generatedAST.from = from;
	}

	buildHaving(
		operator: string,
		aggregateType: string,
		tableName: string,
		columnName: string,
		val: any,
		type: string,
	) {
		this.generatedAST.having = {
			type: 'binary_expr',
			operator: operator,
			left: {
				type: 'aggr_func',
				name: aggregateType,
				args: {
					expr: {
						type: 'column_ref',
						table: this.getAlias(tableName),
						column: columnName,
					},
				},
			},
			right: { type: type, value: val },
		} as any;
	}

	buildGroupBy(tableName: string, columnName: string) {
		this.generatedAST.groupby = {
			columns: [
				{
					type: 'column_ref',
					table: this.getAlias(tableName),
					column: columnName,
				},
			],
			modifiers: [],
		};
	}

	buildOrderBy(
		orderType: 'ASC' | 'DESC',
		tableName: string,
		columnName: string,
	) {
		this.generatedAST.orderby = [
			{
				type: orderType,
				expr: {
					type: 'column_ref',
					table: this.getAlias(tableName),
					column: columnName,
				},
			},
		];
	}

	buildAggregatedOrderByClause(
		orderType: 'ASC' | 'DESC',
		tableName: string,
		columnName: string,
		aggregateType: string,
	) {
		this.generatedAST.orderby = [
			{
				type: orderType,
				expr: {
					type: 'aggr_func',
					name: aggregateType,
					args: {
						expr: {
							type: 'column_ref',
							table: this.getAlias(tableName),
							column: columnName,
						},
					},
				},
			},
		];
	}

	getGeneratedAST(): Select {
		return this.generatedAST;
	}

	/**
	 * Builds the ON condition for a join from the analyzer's relation key.
	 *
	 * Relation keys always have the shape `T1.C1 = T2.C2`. The returned string
	 * carries every identifier double-quoted (with embedded quotes doubled) so
	 * that node-sql-parser's `sqlify`, which passes `on` strings through
	 * verbatim, resolves case-sensitive identifiers exactly as declared.
	 *
	 * Self-join alias substitution mirrors the previous regex-based helpers:
	 * references to `selfJoinTable` become `<first-char>1` (first side) and
	 * `<first-char>2` (second side); references to a previously self-joined
	 * table become `<first-char>2`.
	 */
	private buildJoinConditionOn(
		relationKey: string,
		selfJoinTable?: string,
		previousTable?: string,
	): string {
		const match = relationKey.match(
			/^\s*([^\s.]+)\.([^\s.=]+)\s*=\s*([^\s.]+)\.([^\s.=]+)\s*$/,
		);
		if (!match) return relationKey;

		const [, leftTable, leftColumn, rightTable, rightColumn] = match;
		let resolvedLeftTable = leftTable;
		let resolvedRightTable = rightTable;

		if (selfJoinTable) {
			if (leftTable === selfJoinTable)
				resolvedLeftTable = `${selfJoinTable.charAt(0)}1`;
			if (rightTable === selfJoinTable)
				resolvedRightTable = `${selfJoinTable.charAt(0)}2`;
		}
		if (previousTable) {
			const previousAlias = `${previousTable.charAt(0)}2`;
			if (leftTable === previousTable) resolvedLeftTable = previousAlias;
			if (rightTable === previousTable) resolvedRightTable = previousAlias;
		}

		return (
			`${quoteIdentifier(resolvedLeftTable)}.${quoteIdentifier(leftColumn)}` +
			` = ${quoteIdentifier(resolvedRightTable)}.${quoteIdentifier(rightColumn)}`
		);
	}

	getAlias(tableName: string) {
		if (this.aliasedTables.includes(tableName))
			return randomBoolean()
				? `${tableName.charAt(0)}${1}`
				: `${tableName.charAt(0)}${2}`;
		return tableName;
	}
}
