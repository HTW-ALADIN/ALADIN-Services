import { DataSource } from "typeorm";
import { aggregateByColumnTypes, aggregateColumnType, aggregateType, booleanTypes, dateTypes, IParsedColumn, IParsedTable, IPath, ITaskConfiguration, joinType, joinTypes, numericTypes, operationType, operationTypes, orderableTypes, textTypes } from "./interfaces";
import { QueryGenerationDirector } from "./query-generation-director";
import { SelectASTBuilder } from "./select-ast-builder";
import { AST, ColumnRefItem, Expr, Parser, Select } from "node-sql-parser";
import { createQueryRunner, isValidForAggregation, random, randomBoolean, shuffle } from "./helper-functions";
import { databaseMetadata, selfJoinDatabaseMetadata } from "./internal-memory";

export class SelectQueryGenerationDirector implements QueryGenerationDirector {
    astBuilder: SelectASTBuilder;
    private maxShuffleCounter = 10;

    constructor() {
        this.astBuilder = new SelectASTBuilder();
    }

    public async buildQuery(context: ITaskConfiguration,
        metadata: IParsedTable[],
        filteredTables: IParsedTable[],
        datasource: DataSource,
        schema: string,
        shuffleCounter: number): Promise<[string, AST]> {
        this.astBuilder = new SelectASTBuilder();
        if (shuffleCounter >= this.maxShuffleCounter) {
            console.log("Invalid configuration: Unable to generate a valid query for the given configuration and database.")
            throw new Error("Invalid configuration: Unable to generate a valid query for the given configuration and database.");
        }
        const parser = new Parser();


        const randomTable = filteredTables[random(filteredTables.length)];
        let mergedColumns;
        let joinPath: IPath[] = [];
        if (context.joinDepth > 0) {
            joinPath = this.selectJoinPath(randomTable, context.joinDepth, context.joinTypes);
            mergedColumns = this.selectColumnsFromJoinPath(
                randomTable,
                metadata,
                joinPath,
                context.joinDepth
            );
        }
        else {
            mergedColumns = [];
            mergedColumns.push(...randomTable.columns.map(col => ({ ...col })));
        }

        if (mergedColumns.length < context.predicateCount || mergedColumns.length < context.columnCount) {
            console.log(`Shuffle ${shuffleCounter}`);
            return await this.buildQuery(
                context,
                metadata,
                filteredTables,
                datasource,
                schema,
                shuffleCounter + 1
            )
        }

        if (context.aggregation) {
            if (!this.areAllAggregationColumnsAvailable(mergedColumns, context.columnCount)) {
                console.log(`Shuffle ${shuffleCounter}`);
                return await this.buildQuery(
                    context,
                    metadata,
                    filteredTables,
                    datasource,
                    schema,
                    shuffleCounter + 1
                )
            }
        }

        let aggregationSelect = false;
        let groupByColumn;

        if (context.joinDepth > 0 && randomTable.joinPaths.length > 0) {
            this.astBuilder.buildFromWithJoin(
                schema,
                randomTable.name,
                joinPath,
                context.joinTypes,
                context.joinDepth
            );
        } else {
            this.astBuilder.buildFrom(schema, randomTable.name);
        }

        if (context.predicateCount > 0) {
            const missingTypes: string[] = this.areAllPredicateTypesAvailable(context, mergedColumns);

            if (missingTypes.length > 0) {
                console.log(`Shuffle ${shuffleCounter}`);
                return await this.buildQuery(
                    context,
                    metadata,
                    filteredTables,
                    datasource,
                    schema,
                    shuffleCounter + 1
                )
            }

            try {
                const constraints = await this.generatePredicates(
                    mergedColumns,
                    context.predicateCount, datasource, schema, context.operationTypes
                );
                this.astBuilder.buildWhere(constraints);
            } catch {
                console.log(`Shuffle ${shuffleCounter}`);
                return await this.buildQuery(
                    context,
                    metadata,
                    filteredTables,
                    datasource,
                    schema,
                    shuffleCounter + 1
                )
            }
        }

        if (context.groupby) {
            try {
                groupByColumn = context.having
                    ? await this.generateHavingClauseAndReturnGroupByColumn(mergedColumns, datasource, schema)
                    : this.generateGroupByClauseAndReturnColumn(mergedColumns);
            } catch {
                console.log(`Shuffle ${shuffleCounter}`);
                return await this.buildQuery(
                    context,
                    metadata,
                    filteredTables,
                    datasource,
                    schema,
                    shuffleCounter + 1
                )
            }
            if (context.columnCount > 1 && context.aggregation) {
                const reducedColumns = this.prepareReducedColumnsForSelectClause(
                    mergedColumns,
                    context.columnCount,
                    context.aggregation
                );
                if (reducedColumns[0].aggregation) {
                    this.astBuilder.buildSelect(reducedColumns);
                    aggregationSelect = true;
                }
            } else this.astBuilder.buildSelect([groupByColumn], true);
        } else if (context.columnCount == 0) {
            this.astBuilder.buildSelectAll();
        } else {
            const reducedColumns = this.prepareReducedColumnsForSelectClause(
                mergedColumns,
                context.columnCount,
                context.aggregation
            );
            if (reducedColumns[0].aggregation) {
                aggregationSelect = true;
            }
            this.astBuilder.buildSelect(reducedColumns);
        }

        if (context.orderby) {
            if (aggregationSelect) {
                this.generateOrderByClause(mergedColumns, true, false);
            } else if (groupByColumn)
                randomBoolean() ? this.generateOrderByClause([groupByColumn], false, true) : this.generateOrderByClause(mergedColumns, true, false);
            else this.generateOrderByClause(mergedColumns, false, false);
        }

        const ast: Select = this.astBuilder.getGeneratedAST();
        let query = parser.sqlify(ast, { database: 'postgresql' });


        let queryRunner = createQueryRunner(datasource);
        if (!queryRunner) {
            console.log("No database connection, please establish a database connection")
            throw new Error("No database connection, please establish a database connection");
        }

        try {
            let result = await queryRunner.query(query);
            queryRunner.release();
            console.log("Successful execution of generated query");

            if (result.length <= 0) {
                console.log("Generated query returns empty result set.");
                console.log(`Shuffle ${shuffleCounter}`);
                return await this.buildQuery(
                    context,
                    metadata,
                    filteredTables,
                    datasource,
                    schema,
                    shuffleCounter + 1
                )
            }
        } catch (error) {
            console.log("Unable to execute generated query.");
            queryRunner.release();
            throw error;
        }

        return [query, ast];;
    }

    public validateConfiguration(config: ITaskConfiguration): [boolean, string] {

        if (!this.isITaskConfiguration(config)) {
            return [false, "Invalid Configuration: Invalid task configuration"];
        }

        if (config.aggregation && config.columnCount < 1) {
            return [false, "Invalid Configuration: Aggregation is not possible if column count is smaller than 1"];
        }

        if (config.groupby && !config.aggregation && config.columnCount > 1) {
            return [false, "Invalid Configuration: For a groupby generation with a column count larger than 1, aggregation needs to be activated"];
        }

        if (!config.groupby && config.having) {
            return [false, "Invalid Configuration: Having required group by to be activated"];
        }

        if (config.joinDepth < config.joinTypes.length) {
            return [false, "Invalid Configuration: More join types selected than configured join depth"];
        }

        if (config.predicateCount < config.operationTypes.length) {
            return [false, "Invalid Configuration: More operation types selected than configured predicate count"];
        }

        if (config.joinDepth < 0 || config.columnCount < 0 || config.predicateCount < 0) {
            return [false, "Invalid Configuration: Negative count value"];
        }

        if (this.areInvalidTypesIncluded(config.joinTypes, joinTypes)) {
            return [false, "Invalid Configuration: Unsupported Join type"];
        }

        if (this.areInvalidTypesIncluded(config.operationTypes, Object.keys(operationTypes))) {
            return [false, "Invalid Configuration: Unsupported operation type"];
        }

        return [true, ""];
    }

    private isITaskConfiguration(obj: any): boolean {
        return obj != null &&
            typeof obj.aggregation === "boolean" &&
            typeof obj.orderby === "boolean" &&
            typeof obj.joinDepth === "number" &&
            Array.isArray(obj.joinTypes) &&
            typeof obj.predicateCount === "number" &&
            typeof obj.groupby === "boolean" &&
            typeof obj.having === "boolean" &&
            typeof obj.columnCount === "number" &&
            Array.isArray(obj.operationTypes);
    }

    private areInvalidTypesIncluded(array: any[], typesArray: any): boolean {
        let invalidValues = array.filter((value) => !typesArray.includes(value));
        return invalidValues.length > 0 ? true : false;
    }

    private areAllAggregationColumnsAvailable(mergedColumns: IParsedColumn[], columnCount: number) {
        const aggregatableColumns = mergedColumns.filter(
            (column: IParsedColumn) => aggregateColumnType.includes(column.type) && isValidForAggregation(column.name)
        );

        if (aggregatableColumns.length >= columnCount) {
            return true;
        }
        else return false;
    }

    private areAllPredicateTypesAvailable(context: ITaskConfiguration, mergedColumns: IParsedColumn[]) {
        const missingTypes: string[] = [];
        const usedColumns = new Set<string>();

        for (const operation of context.operationTypes) {
            let column;
            if (operation == "IS_NULL") {
                column = mergedColumns.find(
                    col => col.isNullable && !usedColumns.has(col.name)
                );
            }
            else {

                column = mergedColumns.find(
                    col => operationTypes[operation].includes(col.type) && !usedColumns.has(col.name)
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
        depth: number
    ) {
        const columns: IParsedColumn[] = [];

        columns.push(...selectedTable.columns.map(col => ({ ...col })));

        for (let i = 0; i < depth; i++) {
            const nextTableInPath = allTables.find(
                table => table.name == path[i].tableName
            );
            if (nextTableInPath) {
                columns.push(...nextTableInPath.columns.map(col => ({ ...col })));
            }
        }

        return columns;
    }

    private selectJoinPath(randomTable: IParsedTable, joinDepth: number, joinTypes: joinType[]) {
        let filteredPaths;
        if (joinTypes.includes("SELF JOIN")) {
            filteredPaths = randomTable.joinPaths.filter(
                path => path?.depth >= joinDepth && path?.selfJoinDepth <= joinDepth
            );
        }
        filteredPaths = randomTable.joinPaths.filter(
            path => path?.depth >= joinDepth
        );
        return filteredPaths[random(filteredPaths.length)]?.path;
    }

    private prepareReducedColumnsForSelectClause(
        mergedColumns: IParsedColumn[],
        columnCount: number,
        aggregation: boolean
    ): IParsedColumn[] {

        let reducedColumns: IParsedColumn[] = [];
        if (aggregation) {
            const aggregatableColumns = mergedColumns.filter(
                (column: IParsedColumn) => aggregateColumnType.includes(column.type) && isValidForAggregation(column.name)
            );

            if (aggregatableColumns.length >= columnCount) {
                reducedColumns = shuffle(aggregatableColumns).slice(
                    0,
                    columnCount
                );

                reducedColumns.forEach(column => {
                    column.aggregation = this.returnAggregateType(column);
                });
            }
        }
        else {
            reducedColumns = shuffle(mergedColumns).slice(
                0,
                columnCount
            );
        }
        return reducedColumns;
    }

    private returnAggregateType(column: IParsedColumn): aggregateType | undefined {
        if (numericTypes.includes(column.type)) {
            return aggregateByColumnTypes.numericTypes[random(aggregateByColumnTypes.numericTypes.length)];
        } else if (textTypes.includes(column.type)) {
            return aggregateByColumnTypes.textTypes[random(aggregateByColumnTypes.textTypes.length)];
        } else if (dateTypes.includes(column.type)) {
            return aggregateByColumnTypes.dateTypes[random(aggregateByColumnTypes.dateTypes.length)];
        }
    }

    private async generatePredicates(
        mergedColumns: IParsedColumn[],
        constraintCount: number, dataSource: DataSource, schema: string, configuredOperationTypes: operationType[]
    ): Promise<Expr[]> {
        const constraintColumns: IParsedColumn[] = shuffle(mergedColumns);
        const whereConstraints: Expr[] = [];
        const usedColumns = new Set<string>();

        for (const operation of configuredOperationTypes) {
            let column;
            if (operation == "IS_NULL") {
                column = mergedColumns.find(
                    col => col.isNullable && !usedColumns.has(col.name)
                );
            }
            else {

                column = mergedColumns.find(
                    col => operationTypes[operation].includes(col.type) && !usedColumns.has(col.name)
                );
            }

            if (column) {
                const constraint = await this.generatePredicateByOperationType(column, operation, dataSource, schema);
                if (constraint) whereConstraints.push(constraint);
                usedColumns.add(column.name);
            }
        }

        const unusedColumns: IParsedColumn[] = constraintColumns.filter(column => !usedColumns.has(column.name));

        for (let i = 0; i < unusedColumns.length && whereConstraints.length < constraintCount; i++) {
            const constraint = await this.generatePredicateByColumnType(
                unusedColumns[i], dataSource, schema
            );
            if (constraint) whereConstraints.push(constraint);
        }
        if (whereConstraints.length < constraintCount) {
            throw Error("Unable to generate the expected predicate count");
        }
        return whereConstraints;
    }

    private generateNullableConstraint(column: IParsedColumn) {
        const operator = randomBoolean() ? 'IS' : 'IS NOT';
        return this.astBuilder.buildWhereConstraint(
            operator,
            column.tableName,
            column.name,
            'null',
            null
        );
    }

    private async generateLikeConstraint(
        column: IParsedColumn,
        type: string,
        dataSource: DataSource,
        schema: string
    ): Promise<Expr | undefined> {
        const randomValue = await this.getRandomValueFromDatabase(column.name, column.type, dataSource, `SELECT ${column.name} FROM ${schema}.${column.tableName} ORDER BY RANDOM() LIMIT 1`);

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
                value
            );
        }
        return undefined;
    }

    private async generateLargerConstraint(
        column: IParsedColumn,
        type: string,
        dataSource: DataSource,
        schema: string
    ): Promise<Expr | undefined> {
        const randomValue = await this.getRandomValueFromDatabase(column.name, column.type, dataSource, `SELECT ${column.name} FROM ${schema}.${column.tableName} WHERE ${column.name} NOT IN (SELECT MAX(${column.name}) FROM  ${schema}.${column.tableName}) ORDER BY RANDOM() LIMIT 1`);

        if (randomValue) {
            const operator = randomBoolean() ? '>' : '>=';
            const value = this.checkForSpecialCharacters(
                type,
                randomValue
            );
            return this.astBuilder.buildWhereConstraint(
                operator,
                column.tableName,
                column.name,
                type,
                value
            );
        }
        return undefined;
    }

    private async generateHavingPredicate(
        column: IParsedColumn,
        dataSource: DataSource,
        schema: string
    ) {
        if (!column.aggregation)
            throw new Error("Error in selecting aggregation type for Having predicate")

        let type = numericTypes.includes(column.type) ? 'number' : 'single_quote_string';
        const operators = ['>', '>=', '<', '<=', '=', "!="];

        const operator =
            operators[random(operators.length)];

        // Generate a random value based on the aggregate function
        let randomValue = await this.getRandomValueFromDatabase("aggvalue", column.type, dataSource, `SELECT ${column.aggregation}(${column.name}) AS aggvalue 
       FROM ${schema}.${column.tableName}`, true);

        if (randomValue) {
            if (dateTypes.includes(column.type) && (column.aggregation != "COUNT")) {
                const date = new Date(randomValue);
                randomValue = date.toISOString().split('T')[0];
            }

            const value = this.checkForSpecialCharacters(
                type,
                randomValue
            );

            this.astBuilder.buildHaving(
                operator,
                column.aggregation,
                column.tableName,
                column.name,
                value,
                type
            );
        }
        else throw new Error("Error in finding a Random Value for Having")
    }

    private async generateSmallerConstraint(
        column: IParsedColumn,
        type: string,
        dataSource: DataSource,
        schema: string
    ): Promise<Expr | undefined> {
        const randomValue = await this.getRandomValueFromDatabase(column.name, column.type, dataSource, `SELECT ${column.name} FROM ${schema}.${column.tableName} WHERE ${column.name} NOT IN (SELECT MIN(${column.name}) FROM  ${schema}.${column.tableName}) ORDER BY RANDOM() LIMIT 1`);

        if (randomValue) {
            const operator = randomBoolean() ? '<' : '<=';
            const value = this.checkForSpecialCharacters(
                type,
                randomValue
            );
            return this.astBuilder.buildWhereConstraint(
                operator,
                column.tableName,
                column.name,
                type,
                value
            );
        }
        return undefined;
    }

    private async getRandomValueFromDatabase(columnName: string, columnType: string, dataSource: DataSource, query: string, isHaving = false) {
        let queryRunner = createQueryRunner(dataSource);
        if (!queryRunner)
            return undefined;
        const randomValue = await queryRunner.query(query);
        queryRunner.release();

        if (randomValue && randomValue.length > 0) {

            let value = randomValue[0][`${columnName}`]

            if (!isHaving && value && dateTypes.includes(columnType)) {
                const date = new Date(value);
                const formattedDate = date.toISOString().split('T')[0];
                return formattedDate;
            }

            return value;
        }
        return undefined;
    }

    private async getRandomValuesFromDatabase(column: IParsedColumn, dataSource: DataSource, query: string) {
        let queryRunner = createQueryRunner(dataSource);
        if (!queryRunner)
            return undefined;
        const randomValue = await queryRunner.query(query);
        queryRunner.release();

        if (randomValue && randomValue.length > 0) {

            let formattedValues = [];
            for (let i = 0; i < randomValue.length; i++) {
                let value = randomValue[i][`${column.name}`]

                if (value && dateTypes.includes(column.type)) {
                    const date = new Date(value);
                    const formattedDate = date.toISOString().split('T')[0];
                    formattedValues.push(formattedDate);
                }
                else {
                    formattedValues.push(value);
                }
            }

            return formattedValues;
        }
        return undefined;
    }

    private async generateEqualityConstraint(
        column: IParsedColumn,
        type: string,
        dataSource: DataSource,
        schema: string
    ): Promise<Expr | undefined> {
        const randomValue = await this.getRandomValueFromDatabase(column.name, column.type, dataSource, `SELECT ${column.name} FROM ${schema}.${column.tableName} ORDER BY RANDOM() LIMIT 1`);

        if (randomValue) {
            const operator = randomBoolean() ? '=' : '!=';
            const value = this.checkForSpecialCharacters(
                type,
                randomValue
            );
            return this.astBuilder.buildWhereConstraint(
                operator,
                column.tableName,
                column.name,
                type,
                value
            );
        }
        return undefined;
    }

    private async generateBetweenConstraint(
        column: IParsedColumn,
        type: string,
        dataSource: DataSource,
        schema: string
    ): Promise<Expr | undefined> {
        const randomValue = await this.getRandomValuesFromDatabase(column, dataSource, `WITH selected_rows AS ( SELECT ${column.name}, LEAD(${column.name}) OVER (ORDER BY RANDOM()) as next_value, LAG(${column.name}) OVER (ORDER BY RANDOM()) as prev_value FROM ${schema}.${column.tableName} ) SELECT ${column.name} FROM selected_rows WHERE ${column.name} IS DISTINCT FROM next_value AND ${column.name} IS DISTINCT FROM prev_value ORDER BY RANDOM() LIMIT 2;`);

        if (randomValue && randomValue.length > 1) {
            const operator = 'BETWEEN';
            const valueList = [];
            for (let i = 0; i < 2; i++) {
                const val = this.checkForSpecialCharacters(
                    type,
                    randomValue[i]
                );
                valueList.push({ type: type, value: val });
            }
            return this.astBuilder.buildWhereConstraintValueList(
                operator,
                column.tableName,
                column.name,
                valueList
            );
        }
        return undefined;
    }

    private async generateINConstraint(
        column: IParsedColumn,
        type: string,
        dataSource: DataSource,
        schema: string
    ): Promise<Expr | undefined> {
        const randomValue = await this.getRandomValuesFromDatabase(column, dataSource, `WITH row_count AS ( SELECT COUNT(*) AS total_rows FROM ${schema}.${column.tableName} ), random_selection AS ( SELECT ${column.name} FROM ${schema}.${column.tableName} ORDER BY RANDOM() LIMIT 4 ) SELECT ${column.name} FROM random_selection WHERE (SELECT total_rows FROM row_count) >= 2 LIMIT LEAST((SELECT total_rows FROM row_count), 4);`
        );

        if (randomValue && randomValue.length > 1) {
            const operator = 'IN';
            const valueList: any[] = [];
            randomValue.forEach((val: any) => {
                const value = this.checkForSpecialCharacters(
                    type,
                    val
                );
                valueList.push({ type: type, value: value });
            });
            return this.astBuilder.buildWhereConstraintValueList(
                operator,
                column.tableName,
                column.name,
                valueList
            );
        }
        return undefined;
    }

    private generateBooleanConstraint(column: IParsedColumn) {
        const value = randomBoolean() ? true : false;
        return this.astBuilder.buildWhereConstraint(
            'IS',
            column.tableName,
            column.name,
            'bool',
            value
        );
    }

    private async generatePredicateByOperationType(column: IParsedColumn, operation: operationType, dataSource: DataSource, schema: string): Promise<Expr | undefined> {
        let type = numericTypes.includes(column.type) ? 'number' : 'single_quote_string';
        switch (operation) {
            case "EQUAL": {
                return this.generateEqualityConstraint(column, type, dataSource, schema);
            }
            case "COMPARISON": {
                return randomBoolean() ? this.generateLargerConstraint(column, type, dataSource, schema) : this.generateSmallerConstraint(column, type, dataSource, schema);
            }
            case "IN": {
                return this.generateINConstraint(column, type, dataSource, schema);
            }
            case "IS_NULL": {
                return this.generateNullableConstraint(column);
            }
            case "LIKE": {
                return this.generateLikeConstraint(column, type, dataSource, schema);
            }
            case "BETWEEN": {
                return this.generateBetweenConstraint(column, type, dataSource, schema);
            }
            case "IS_BOOLEAN": {
                return this.generateBooleanConstraint(column);
            }
        }
    }

    private async generatePredicateByColumnType(
        column: IParsedColumn, dataSource: DataSource, schema: string
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
            case column.isNullable && randomBoolean(): {
                return this.generateNullableConstraint(column);
            }
            case textTypes.includes(column.type): {
                const randomConstraintFunction =
                    textFunctions[random(textFunctions.length)];
                return await randomConstraintFunction(column, 'single_quote_string', dataSource, schema);
            }
            case numericTypes.includes(column.type): {
                const randomConstraintFunction =
                    numberFunctions[random(numberFunctions.length)];
                return await randomConstraintFunction(column, 'number', dataSource, schema);
            }
            case dateTypes.includes(column.type): {
                const randomConstraintFunction =
                    dateFunctions[random(dateFunctions.length)];
                return await randomConstraintFunction(column, 'single_quote_string', dataSource, schema);
            }
            case booleanTypes.includes(column.type): {
                return this.generateBooleanConstraint(column);
            }
            default: {
                return undefined;
            }
        }
    }

    private checkForSpecialCharacters(type: string, value: any) {
        if (type == 'single_quote_string' && typeof value === 'string') {
            return value.replace("'", "''");
        }
        return value;
    }

    private async generateHavingClauseAndReturnGroupByColumn(
        mergedColumns: IParsedColumn[],
        dataSource: DataSource,
        schema: string
    ): Promise<IParsedColumn> {
        //What constraints make sense here?

        const havingColumn: IParsedColumn = shuffle(mergedColumns).find(
            (column: IParsedColumn) => aggregateColumnType.includes(column.type) && isValidForAggregation(column.name)
        );
        if (!havingColumn)
            throw Error("Unable to find having column, reshuffle");
        havingColumn.aggregation = this.returnAggregateType(havingColumn);
        if (!havingColumn.aggregation)
            throw Error("Unable to find having column, reshuffle");

        await this.generateHavingPredicate(havingColumn, dataSource, schema);

        return this.generateGroupByClauseAndReturnColumn(
            mergedColumns,
            havingColumn
        );
    }

    private generateGroupByClauseAndReturnColumn(
        mergedColumns: IParsedColumn[],
        havingColumn?: IParsedColumn
    ): IParsedColumn {
        const groupbyColumn: IParsedColumn = havingColumn
            ? shuffle(mergedColumns).find(
                (column: IParsedColumn) =>
                    column.name != havingColumn.name && !column.aggregation
            )
            : shuffle(mergedColumns).find(
                (column: IParsedColumn) => !column.aggregation
            );

        if (!groupbyColumn) {
            throw new Error("Unable to find group by column, reshuffle");
        }

        this.astBuilder.buildGroupBy(
            groupbyColumn.tableName,
            groupbyColumn.name
        );
        return groupbyColumn;
    }

    private generateOrderByClause(mergedColumns: IParsedColumn[], aggregate = false, groupby = false) {
        const sortOder: 'ASC' | 'DESC' = randomBoolean() ? 'ASC' : 'DESC';
        if (aggregate) {
            const aggregatedOrderbyColumn = shuffle(mergedColumns).find(
                (column: IParsedColumn) =>
                    aggregateColumnType.includes(column.type) &&
                    orderableTypes.includes(column.type)
            );
            if (aggregatedOrderbyColumn) {
                const aggregateType = this.returnAggregateType(aggregatedOrderbyColumn);
                this.astBuilder.buildAggregatedOrderByClause(
                    sortOder,
                    aggregatedOrderbyColumn.tableName,
                    aggregatedOrderbyColumn.name,
                    aggregateType as string
                );
            }
        } else {
            const orderbyColumn: IParsedColumn = shuffle(mergedColumns).find(column =>
                orderableTypes.includes(column.type)
            );
            const currentAST = this.astBuilder.getGeneratedAST();
            let tablename: string = (groupby && currentAST?.groupby?.columns?.length && currentAST.groupby?.columns?.length > 0) ? (currentAST?.groupby?.columns[0] as ColumnRefItem).table as string : this.astBuilder.getAlias(orderbyColumn.tableName);
            this.astBuilder.buildOrderBy(
                sortOder,
                tablename,
                orderbyColumn.name
            );
        }
    }

} 