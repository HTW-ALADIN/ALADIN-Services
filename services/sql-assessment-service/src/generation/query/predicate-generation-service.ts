import { Expr } from 'node-sql-parser';
import {
	aggregateColumnType,
	aggregateType,
	booleanTypes,
	dateTypes,
	numericTypes,
	operationTypes,
	operationType,
	textTypes,
} from '../../shared/constants';
import { IParsedColumn } from '../../shared/interfaces/domain';
import { RowQueryFn } from '../../shared/utils/database-utils';
import { isValidForAggregation } from '../../shared/utils/validation';
import { random, randomBoolean, shuffle } from '../../shared/utils/random';
import { SelectASTBuilder } from './select-ast-builder';

/**
 * Handles all predicate/constraint generation logic for SQL queries.
 * Extracted from SelectQueryGenerationDirector to satisfy the Single Responsibility Principle.
 */
export class PredicateGenerationService {
	constructor(private readonly astBuilder: SelectASTBuilder) {}

	async generatePredicates(
		mergedColumns: IParsedColumn[],
		constraintCount: number,
		runQuery: RowQueryFn,
		schema: string,
		configuredOperationTypes: operationType[],
	): Promise<Expr[]> {
		const constraintColumns: IParsedColumn[] = shuffle(mergedColumns);
		const whereConstraints: Expr[] = [];
		const usedColumns = new Set<string>();

		for (const operation of configuredOperationTypes) {
			let column: IParsedColumn | undefined;
			if (operation === 'IS_NULL') {
				column = mergedColumns.find(
					(col) => col.isNullable && !usedColumns.has(col.name),
				);
			} else {
				column = mergedColumns.find(
					(col) =>
						operationTypes[operation].includes(col.type) &&
						!usedColumns.has(col.name),
				);
			}

			if (column) {
				const constraint = await this.generatePredicateByOperationType(
					column,
					operation,
					runQuery,
					schema,
				);
				if (constraint) whereConstraints.push(constraint);
				usedColumns.add(column.name);
			}
		}

		const unusedColumns: IParsedColumn[] = constraintColumns.filter(
			(column) => !usedColumns.has(column.name),
		);

		for (
			let i = 0;
			i < unusedColumns.length && whereConstraints.length < constraintCount;
			i++
		) {
			const constraint = await this.generatePredicateByColumnType(
				unusedColumns[i],
				runQuery,
				schema,
			);
			if (constraint) whereConstraints.push(constraint);
		}

		if (whereConstraints.length < constraintCount) {
			throw Error('Unable to generate the expected predicate count');
		}
		return whereConstraints;
	}

	async generateHavingClauseAndReturnGroupByColumn(
		mergedColumns: IParsedColumn[],
		runQuery: RowQueryFn,
		schema: string,
	): Promise<IParsedColumn> {
		const havingColumn: IParsedColumn | undefined = shuffle(mergedColumns).find(
			(column: IParsedColumn) =>
				aggregateColumnType.includes(column.type) &&
				isValidForAggregation(column.name),
		);
		if (!havingColumn) throw Error('Unable to find having column, reshuffle');
		havingColumn.aggregation = this.returnAggregateType(havingColumn);
		if (!havingColumn.aggregation)
			throw Error('Unable to find having column, reshuffle');

		await this.generateHavingPredicate(havingColumn, runQuery, schema);

		return this.generateGroupByClauseAndReturnColumn(
			mergedColumns,
			havingColumn,
		);
	}

	generateGroupByClauseAndReturnColumn(
		mergedColumns: IParsedColumn[],
		havingColumn?: IParsedColumn,
	): IParsedColumn {
		const groupbyColumn: IParsedColumn | undefined = havingColumn
			? shuffle(mergedColumns).find(
					(column: IParsedColumn) =>
						column.name != havingColumn.name && !column.aggregation,
				)
			: shuffle(mergedColumns).find(
					(column: IParsedColumn) => !column.aggregation,
				);

		if (!groupbyColumn) {
			throw new Error('Unable to find group by column, reshuffle');
		}

		this.astBuilder.buildGroupBy(groupbyColumn.tableName, groupbyColumn.name);
		return groupbyColumn;
	}

	returnAggregateType(column: IParsedColumn): aggregateType | undefined {
		if (numericTypes.includes(column.type)) {
			return ['MAX', 'MIN', 'AVG', 'COUNT', 'SUM'][random(5)] as aggregateType;
		} else if (textTypes.includes(column.type)) {
			return ['MAX', 'MIN', 'COUNT'][random(3)] as aggregateType;
		} else if (dateTypes.includes(column.type)) {
			return ['MAX', 'MIN', 'COUNT'][random(3)] as aggregateType;
		}
	}

	private generateNullableConstraint(column: IParsedColumn): Expr {
		const operator = randomBoolean() ? 'IS' : 'IS NOT';
		return this.astBuilder.buildWhereConstraint(
			operator,
			column.tableName,
			column.name,
			'null',
			null,
		);
	}

	private async generateLikeConstraint(
		column: IParsedColumn,
		type: string,
		runQuery: RowQueryFn,
		schema: string,
	): Promise<Expr | undefined> {
		const randomValue = await this.getRandomValueFromDatabase(
			column.name,
			column.type,
			runQuery,
			`SELECT ${column.name} FROM ${schema}.${column.tableName} ORDER BY RANDOM() LIMIT 1`,
		);

		if (randomValue) {
			const completeString = randomValue;
			const operator = randomBoolean() ? 'LIKE' : 'NOT LIKE';

			let start = random(completeString.length - 1);
			let end = random(completeString.length - 1);

			if (start > end) [start, end] = [end, start];
			if (start === end && completeString.length > 2) {
				if (end === 0) end++;
				if (start === completeString.length - 1) start--;
			}

			let substring = completeString.substring(start, end);
			if (end !== completeString.length - 1) substring += '%';
			if (start !== 0) substring = '%' + substring;

			const value = this.checkForSpecialCharacters(type, substring);
			return this.astBuilder.buildWhereConstraint(
				operator,
				column.tableName,
				column.name,
				type,
				value,
			);
		}
		return undefined;
	}

	private async generateLargerConstraint(
		column: IParsedColumn,
		type: string,
		runQuery: RowQueryFn,
		schema: string,
	): Promise<Expr | undefined> {
		const randomValue = await this.getRandomValueFromDatabase(
			column.name,
			column.type,
			runQuery,
			`SELECT ${column.name} FROM ${schema}.${column.tableName} WHERE ${column.name} NOT IN (SELECT MAX(${column.name}) FROM  ${schema}.${column.tableName}) ORDER BY RANDOM() LIMIT 1`,
		);

		if (randomValue) {
			const operator = randomBoolean() ? '>' : '>=';
			const value = this.checkForSpecialCharacters(type, randomValue);
			return this.astBuilder.buildWhereConstraint(
				operator,
				column.tableName,
				column.name,
				type,
				value,
			);
		}
		return undefined;
	}

	private async generateSmallerConstraint(
		column: IParsedColumn,
		type: string,
		runQuery: RowQueryFn,
		schema: string,
	): Promise<Expr | undefined> {
		const randomValue = await this.getRandomValueFromDatabase(
			column.name,
			column.type,
			runQuery,
			`SELECT ${column.name} FROM ${schema}.${column.tableName} WHERE ${column.name} NOT IN (SELECT MIN(${column.name}) FROM  ${schema}.${column.tableName}) ORDER BY RANDOM() LIMIT 1`,
		);

		if (randomValue) {
			const operator = randomBoolean() ? '<' : '<=';
			const value = this.checkForSpecialCharacters(type, randomValue);
			return this.astBuilder.buildWhereConstraint(
				operator,
				column.tableName,
				column.name,
				type,
				value,
			);
		}
		return undefined;
	}

	private async generateEqualityConstraint(
		column: IParsedColumn,
		type: string,
		runQuery: RowQueryFn,
		schema: string,
	): Promise<Expr | undefined> {
		const randomValue = await this.getRandomValueFromDatabase(
			column.name,
			column.type,
			runQuery,
			`SELECT ${column.name} FROM ${schema}.${column.tableName} ORDER BY RANDOM() LIMIT 1`,
		);

		if (randomValue) {
			const operator = randomBoolean() ? '=' : '!=';
			const value = this.checkForSpecialCharacters(type, randomValue);
			return this.astBuilder.buildWhereConstraint(
				operator,
				column.tableName,
				column.name,
				type,
				value,
			);
		}
		return undefined;
	}

	private async generateBetweenConstraint(
		column: IParsedColumn,
		type: string,
		runQuery: RowQueryFn,
		schema: string,
	): Promise<Expr | undefined> {
		const randomValue = await this.getRandomValuesFromDatabase(
			column,
			runQuery,
			`WITH selected_rows AS ( SELECT ${column.name}, LEAD(${column.name}) OVER (ORDER BY RANDOM()) as next_value, LAG(${column.name}) OVER (ORDER BY RANDOM()) as prev_value FROM ${schema}.${column.tableName} ) SELECT ${column.name} FROM selected_rows WHERE ${column.name} IS DISTINCT FROM next_value AND ${column.name} IS DISTINCT FROM prev_value ORDER BY RANDOM() LIMIT 2;`,
		);

		if (randomValue && randomValue.length > 1) {
			const valueList = [];
			for (let i = 0; i < 2; i++) {
				const val = this.checkForSpecialCharacters(type, randomValue[i]);
				valueList.push({ type: type, value: val });
			}
			return this.astBuilder.buildWhereConstraintValueList(
				'BETWEEN',
				column.tableName,
				column.name,
				valueList,
			);
		}
		return undefined;
	}

	private async generateINConstraint(
		column: IParsedColumn,
		type: string,
		runQuery: RowQueryFn,
		schema: string,
	): Promise<Expr | undefined> {
		const randomValue = await this.getRandomValuesFromDatabase(
			column,
			runQuery,
			`WITH row_count AS ( SELECT COUNT(*) AS total_rows FROM ${schema}.${column.tableName} ), random_selection AS ( SELECT ${column.name} FROM ${schema}.${column.tableName} ORDER BY RANDOM() LIMIT 4 ) SELECT ${column.name} FROM random_selection WHERE (SELECT total_rows FROM row_count) >= 2 LIMIT LEAST((SELECT total_rows FROM row_count), 4);`,
		);

		if (randomValue && randomValue.length > 1) {
			const valueList: any[] = [];
			randomValue.forEach((val: any) => {
				const value = this.checkForSpecialCharacters(type, val);
				valueList.push({ type: type, value: value });
			});
			return this.astBuilder.buildWhereConstraintValueList(
				'IN',
				column.tableName,
				column.name,
				valueList,
			);
		}
		return undefined;
	}

	private generateBooleanConstraint(column: IParsedColumn): Expr {
		const value = randomBoolean() ? true : false;
		return this.astBuilder.buildWhereConstraint(
			'IS',
			column.tableName,
			column.name,
			'bool',
			value,
		);
	}

	async generateHavingPredicate(
		column: IParsedColumn,
		runQuery: RowQueryFn,
		schema: string,
	): Promise<void> {
		if (!column.aggregation)
			throw new Error(
				'Error in selecting aggregation type for Having predicate',
			);

		const type = numericTypes.includes(column.type)
			? 'number'
			: 'single_quote_string';
		const operators = ['>', '>=', '<', '<=', '=', '!='];
		const operator = operators[random(operators.length)];

		let randomValue = await this.getRandomValueFromDatabase(
			'aggvalue',
			column.type,
			runQuery,
			`SELECT ${column.aggregation}(${column.name}) AS aggvalue FROM ${schema}.${column.tableName}`,
			true,
		);

		if (randomValue) {
			if (dateTypes.includes(column.type) && column.aggregation !== 'COUNT') {
				const date = new Date(randomValue);
				randomValue = date.toISOString().split('T')[0];
			}

			const value = this.checkForSpecialCharacters(type, randomValue);
			this.astBuilder.buildHaving(
				operator,
				column.aggregation,
				column.tableName,
				column.name,
				value,
				type,
			);
		} else {
			throw new Error('Error in finding a Random Value for Having');
		}
	}

	private async generatePredicateByOperationType(
		column: IParsedColumn,
		operation: operationType,
		runQuery: RowQueryFn,
		schema: string,
	): Promise<Expr | undefined> {
		const type = numericTypes.includes(column.type)
			? 'number'
			: 'single_quote_string';
		switch (operation) {
			case 'EQUAL':
				return this.generateEqualityConstraint(column, type, runQuery, schema);
			case 'COMPARISON':
				return randomBoolean()
					? this.generateLargerConstraint(column, type, runQuery, schema)
					: this.generateSmallerConstraint(column, type, runQuery, schema);
			case 'IN':
				return this.generateINConstraint(column, type, runQuery, schema);
			case 'IS_NULL':
				return this.generateNullableConstraint(column);
			case 'LIKE':
				return this.generateLikeConstraint(column, type, runQuery, schema);
			case 'BETWEEN':
				return this.generateBetweenConstraint(column, type, runQuery, schema);
			case 'IS_BOOLEAN':
				return this.generateBooleanConstraint(column);
		}
	}

	private async generatePredicateByColumnType(
		column: IParsedColumn,
		runQuery: RowQueryFn,
		schema: string,
	): Promise<Expr | undefined> {
		const textFunctions = [
			this.generateLargerConstraint.bind(this),
			this.generateSmallerConstraint.bind(this),
			this.generateEqualityConstraint.bind(this),
			this.generateBetweenConstraint.bind(this),
			this.generateINConstraint.bind(this),
			this.generateLikeConstraint.bind(this),
		];
		const numberFunctions = [
			this.generateLargerConstraint.bind(this),
			this.generateSmallerConstraint.bind(this),
			this.generateEqualityConstraint.bind(this),
			this.generateBetweenConstraint.bind(this),
			this.generateINConstraint.bind(this),
		];
		const dateFunctions = [
			this.generateLargerConstraint.bind(this),
			this.generateSmallerConstraint.bind(this),
			this.generateEqualityConstraint.bind(this),
			this.generateBetweenConstraint.bind(this),
			this.generateINConstraint.bind(this),
		];

		switch (true) {
			case column.isNullable && randomBoolean():
				return this.generateNullableConstraint(column);
			case textTypes.includes(column.type): {
				const fn = textFunctions[random(textFunctions.length)];
				return await fn(column, 'single_quote_string', runQuery, schema);
			}
			case numericTypes.includes(column.type): {
				const fn = numberFunctions[random(numberFunctions.length)];
				return await fn(column, 'number', runQuery, schema);
			}
			case dateTypes.includes(column.type): {
				const fn = dateFunctions[random(dateFunctions.length)];
				return await fn(column, 'single_quote_string', runQuery, schema);
			}
			case booleanTypes.includes(column.type):
				return this.generateBooleanConstraint(column);
			default:
				return undefined;
		}
	}

	private checkForSpecialCharacters(type: string, value: any): any {
		if (type === 'single_quote_string' && typeof value === 'string') {
			return value.replace("'", "''");
		}
		return value;
	}

	private async getRandomValueFromDatabase(
		columnName: string,
		columnType: string,
		runQuery: RowQueryFn,
		query: string,
		isHaving = false,
	): Promise<any> {
		const randomValue = await runQuery(query);

		if (randomValue && randomValue.length > 0) {
			const value = randomValue[0][`${columnName}`];

			if (!isHaving && value && dateTypes.includes(columnType)) {
				const date = new Date(value);
				return date.toISOString().split('T')[0];
			}

			return value;
		}
		return undefined;
	}

	private async getRandomValuesFromDatabase(
		column: IParsedColumn,
		runQuery: RowQueryFn,
		query: string,
	): Promise<any[] | undefined> {
		const randomValue = await runQuery(query);

		if (randomValue && randomValue.length > 0) {
			const formattedValues = [];
			for (let i = 0; i < randomValue.length; i++) {
				const value = randomValue[i][`${column.name}`];

				if (value && dateTypes.includes(column.type)) {
					const date = new Date(value);
					formattedValues.push(date.toISOString().split('T')[0]);
				} else {
					formattedValues.push(value);
				}
			}
			return formattedValues;
		}
		return undefined;
	}
}
