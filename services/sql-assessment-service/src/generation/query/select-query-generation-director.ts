import {
	aggregateColumnType,
	joinType,
	joinTypes,
	operationTypes,
	orderableTypes,
} from '../../shared/constants';
import {
	IParsedColumn,
	IParsedTable,
	IPath,
	ITaskConfiguration,
} from '../../shared/interfaces/domain';
import { QueryGenerationDirector } from './query-generation-director';
import { SelectASTBuilder } from './select-ast-builder';
import { PredicateGenerationService } from './predicate-generation-service';
import { AST, ColumnRefItem, Parser, Select } from 'node-sql-parser';
import { RowQueryFn } from '../../shared/utils/database-utils';
import { isValidForAggregation } from '../../shared/utils/validation';
import { random, randomBoolean, shuffle } from '../../shared/utils/random';

export class SelectQueryGenerationDirector implements QueryGenerationDirector {
	astBuilder: SelectASTBuilder;
	private predicateService: PredicateGenerationService;
	private readonly maxShuffleCounter = 10;

	constructor() {
		this.astBuilder = new SelectASTBuilder();
		this.predicateService = new PredicateGenerationService(this.astBuilder);
	}

	public async buildQuery(
		context: ITaskConfiguration,
		metadata: IParsedTable[],
		filteredTables: IParsedTable[],
		runQuery: RowQueryFn,
		schema: string,
		shuffleCounter: number,
	): Promise<[string, AST]> {
		// Re-instantiate builder and service each query attempt to start from a clean AST state
		this.astBuilder = new SelectASTBuilder();
		this.predicateService = new PredicateGenerationService(this.astBuilder);

		if (shuffleCounter >= this.maxShuffleCounter) {
			console.log(
				'Invalid configuration: Unable to generate a valid query for the given configuration and database.',
			);
			throw new Error(
				'Invalid configuration: Unable to generate a valid query for the given configuration and database.',
			);
		}
		const parser = new Parser();

		const randomTable = filteredTables[random(filteredTables.length)];
		let mergedColumns: IParsedColumn[];
		let joinPath: IPath[] = [];

		if (context.joinDepth > 0) {
			joinPath = this.selectJoinPath(
				randomTable,
				context.joinDepth,
				context.joinTypes,
			);
			mergedColumns = this.selectColumnsFromJoinPath(
				randomTable,
				metadata,
				joinPath,
				context.joinDepth,
			);
		} else {
			mergedColumns = randomTable.columns.map((col) => ({ ...col }));
		}

		if (
			mergedColumns.length < context.predicateCount ||
			mergedColumns.length < context.columnCount
		) {
			console.log(`Shuffle ${shuffleCounter}`);
			return await this.buildQuery(
				context,
				metadata,
				filteredTables,
				runQuery,
				schema,
				shuffleCounter + 1,
			);
		}

		if (context.aggregation) {
			if (
				!this.areAllAggregationColumnsAvailable(
					mergedColumns,
					context.columnCount,
				)
			) {
				console.log(`Shuffle ${shuffleCounter}`);
				return await this.buildQuery(
					context,
					metadata,
					filteredTables,
					runQuery,
					schema,
					shuffleCounter + 1,
				);
			}
		}

		let aggregationSelect = false;
		let groupByColumn: IParsedColumn | undefined;

		if (context.joinDepth > 0 && randomTable.joinPaths.length > 0) {
			this.astBuilder.buildFromWithJoin(
				schema,
				randomTable.name,
				joinPath,
				context.joinTypes,
				context.joinDepth,
			);
		} else {
			this.astBuilder.buildFrom(schema, randomTable.name);
		}

		if (context.predicateCount > 0) {
			const missingTypes = this.areAllPredicateTypesAvailable(
				context,
				mergedColumns,
			);
			if (missingTypes.length > 0) {
				// console.log(`Shuffle ${shuffleCounter}`);
				return await this.buildQuery(
					context,
					metadata,
					filteredTables,
					runQuery,
					schema,
					shuffleCounter + 1,
				);
			}

			try {
				const constraints = await this.predicateService.generatePredicates(
					mergedColumns,
					context.predicateCount,
					runQuery,
					schema,
					context.operationTypes,
				);
				this.astBuilder.buildWhere(constraints);
			} catch {
				console.log(`Shuffle ${shuffleCounter}`);
				return await this.buildQuery(
					context,
					metadata,
					filteredTables,
					runQuery,
					schema,
					shuffleCounter + 1,
				);
			}
		}

		if (context.groupby) {
			try {
				groupByColumn = context.having
					? await this.predicateService.generateHavingClauseAndReturnGroupByColumn(
							mergedColumns,
							runQuery,
							schema,
						)
					: this.predicateService.generateGroupByClauseAndReturnColumn(
							mergedColumns,
						);
			} catch {
				console.log(`Shuffle ${shuffleCounter}`);
				return await this.buildQuery(
					context,
					metadata,
					filteredTables,
					runQuery,
					schema,
					shuffleCounter + 1,
				);
			}

			if (context.columnCount > 1 && context.aggregation) {
				const reducedColumns = this.prepareReducedColumnsForSelectClause(
					mergedColumns,
					context.columnCount,
					context.aggregation,
				);
				if (reducedColumns[0].aggregation) {
					this.astBuilder.buildSelect(reducedColumns);
					aggregationSelect = true;
				}
			} else {
				this.astBuilder.buildSelect([groupByColumn!], true);
			}
		} else if (context.columnCount == 0) {
			this.astBuilder.buildSelectAll();
		} else {
			const reducedColumns = this.prepareReducedColumnsForSelectClause(
				mergedColumns,
				context.columnCount,
				context.aggregation,
			);
			if (reducedColumns[0].aggregation) {
				aggregationSelect = true;
			}
			this.astBuilder.buildSelect(reducedColumns);
		}

		if (context.orderby) {
			if (aggregationSelect) {
				this.generateOrderByClause(mergedColumns, true, false);
			} else if (groupByColumn) {
				const bool = randomBoolean();
				const bools = [bool, !bool];
				this.generateOrderByClause([groupByColumn], ...bools);
			} else {
				this.generateOrderByClause(mergedColumns, false, false);
			}
		}

		const ast: Select = this.astBuilder.getGeneratedAST();
		const query = parser.sqlify(ast, { database: 'postgresql' });

		try {
			const result = await runQuery(query);
			console.log('Successful execution of generated query');

			if (result.length <= 0) {
				console.log('Generated query returns empty result set.');
				console.log(`Shuffle ${shuffleCounter}`);
				return await this.buildQuery(
					context,
					metadata,
					filteredTables,
					runQuery,
					schema,
					shuffleCounter + 1,
				);
			}
		} catch (error) {
			console.log('Unable to execute generated query.');
			throw error;
		}

		return [query, ast];
	}

	public validateConfiguration(config: ITaskConfiguration): [boolean, string] {
		if (!this.isITaskConfiguration(config)) {
			return [false, 'Invalid Configuration: Invalid task configuration'];
		}

		if (config.aggregation && config.columnCount < 1) {
			return [
				false,
				'Invalid Configuration: Aggregation is not possible if column count is smaller than 1',
			];
		}

		if (config.groupby && !config.aggregation && config.columnCount > 1) {
			return [
				false,
				'Invalid Configuration: For a groupby generation with a column count larger than 1, aggregation needs to be activated',
			];
		}

		if (!config.groupby && config.having) {
			return [
				false,
				'Invalid Configuration: Having required group by to be activated',
			];
		}

		if (config.joinDepth < config.joinTypes.length) {
			return [
				false,
				'Invalid Configuration: More join types selected than configured join depth',
			];
		}

		if (config.predicateCount < config.operationTypes.length) {
			return [
				false,
				'Invalid Configuration: More operation types selected than configured predicate count',
			];
		}

		if (
			config.joinDepth < 0 ||
			config.columnCount < 0 ||
			config.predicateCount < 0
		) {
			return [false, 'Invalid Configuration: Negative count value'];
		}

		if (this.areInvalidTypesIncluded(config.joinTypes, joinTypes)) {
			return [false, 'Invalid Configuration: Unsupported Join type'];
		}

		if (
			this.areInvalidTypesIncluded(
				config.operationTypes,
				Object.keys(operationTypes),
			)
		) {
			return [false, 'Invalid Configuration: Unsupported operation type'];
		}

		return [true, ''];
	}

	private isITaskConfiguration(obj: any): boolean {
		return (
			obj != null &&
			typeof obj.aggregation === 'boolean' &&
			typeof obj.orderby === 'boolean' &&
			typeof obj.joinDepth === 'number' &&
			Array.isArray(obj.joinTypes) &&
			typeof obj.predicateCount === 'number' &&
			typeof obj.groupby === 'boolean' &&
			typeof obj.having === 'boolean' &&
			typeof obj.columnCount === 'number' &&
			Array.isArray(obj.operationTypes)
		);
	}

	private areInvalidTypesIncluded(array: any[], typesArray: any): boolean {
		const invalidValues = array.filter((value) => !typesArray.includes(value));
		return invalidValues.length > 0;
	}

	private areAllAggregationColumnsAvailable(
		mergedColumns: IParsedColumn[],
		columnCount: number,
	): boolean {
		const aggregatableColumns = mergedColumns.filter(
			(column: IParsedColumn) =>
				aggregateColumnType.includes(column.type) &&
				isValidForAggregation(column.name),
		);
		return aggregatableColumns.length >= columnCount;
	}

	private areAllPredicateTypesAvailable(
		context: ITaskConfiguration,
		mergedColumns: IParsedColumn[],
	): string[] {
		const missingTypes: string[] = [];
		const usedColumns = new Set<string>();

		for (const operation of context.operationTypes) {
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
				usedColumns.add(column.name);
			} else {
				missingTypes.push(operation);
			}
		}
		return missingTypes;
	}

	private selectColumnsFromJoinPath(
		selectedTable: IParsedTable,
		allTables: IParsedTable[],
		path: IPath[],
		depth: number,
	): IParsedColumn[] {
		const columns: IParsedColumn[] = [];
		columns.push(...selectedTable.columns.map((col) => ({ ...col })));

		for (let i = 0; i < depth; i++) {
			const nextTableInPath = allTables.find(
				(table) => table.name == path[i].tableName,
			);
			if (nextTableInPath) {
				columns.push(...nextTableInPath.columns.map((col) => ({ ...col })));
			}
		}

		return columns;
	}

	/**
	 * Selects an appropriate join path for the given table and depth.
	 * Bug fix: previously the self-join branch result was unconditionally overwritten on the next line.
	 */
	private selectJoinPath(
		randomTable: IParsedTable,
		joinDepth: number,
		joinTypes: joinType[],
	): IPath[] {
		let filteredPaths;
		if (joinTypes.includes('SELF JOIN')) {
			filteredPaths = randomTable.joinPaths.filter(
				(path) => path?.depth >= joinDepth && path?.selfJoinDepth <= joinDepth,
			);
		} else {
			filteredPaths = randomTable.joinPaths.filter(
				(path) => path?.depth >= joinDepth,
			);
		}
		return filteredPaths[random(filteredPaths.length)]?.path;
	}

	private prepareReducedColumnsForSelectClause(
		mergedColumns: IParsedColumn[],
		columnCount: number,
		aggregation: boolean,
	): IParsedColumn[] {
		let reducedColumns: IParsedColumn[] = [];
		if (aggregation) {
			const aggregatableColumns = mergedColumns.filter(
				(column: IParsedColumn) =>
					aggregateColumnType.includes(column.type) &&
					isValidForAggregation(column.name),
			);

			if (aggregatableColumns.length >= columnCount) {
				reducedColumns = shuffle(aggregatableColumns).slice(0, columnCount);
				reducedColumns.forEach((column) => {
					column.aggregation =
						this.predicateService.returnAggregateType(column);
				});
			}
		} else {
			reducedColumns = shuffle(mergedColumns).slice(0, columnCount);
		}
		return reducedColumns;
	}

	private generateOrderByClause(
		mergedColumns: IParsedColumn[],
		aggregate = false,
		groupby = false,
	) {
		const sortOrder: 'ASC' | 'DESC' = randomBoolean() ? 'ASC' : 'DESC';
		if (aggregate) {
			const aggregatedOrderbyColumn = shuffle(mergedColumns).find(
				(column: IParsedColumn) =>
					aggregateColumnType.includes(column.type) &&
					orderableTypes.includes(column.type),
			);
			if (aggregatedOrderbyColumn) {
				const aggType = this.predicateService.returnAggregateType(
					aggregatedOrderbyColumn,
				);
				this.astBuilder.buildAggregatedOrderByClause(
					sortOrder,
					aggregatedOrderbyColumn.tableName,
					aggregatedOrderbyColumn.name,
					aggType as string,
				);
			}
		} else {
			const orderbyColumn: IParsedColumn | undefined = shuffle(
				mergedColumns,
			).find((column) => orderableTypes.includes(column.type));
			if (!orderbyColumn) return;
			const currentAST = this.astBuilder.getGeneratedAST();
			const tablename: string =
				groupby &&
				currentAST?.groupby?.columns?.length &&
				currentAST.groupby?.columns?.length > 0
					? ((currentAST?.groupby?.columns[0] as ColumnRefItem).table as string)
					: this.astBuilder.getAlias(orderbyColumn.tableName);
			this.astBuilder.buildOrderBy(sortOrder, tablename, orderbyColumn.name);
		}
	}
}
