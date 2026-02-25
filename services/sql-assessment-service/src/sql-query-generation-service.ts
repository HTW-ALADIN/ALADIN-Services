import { DataSource, QueryFailedError, QueryRunner } from 'typeorm';
import { createQueryRunner, isValidForAggregation, random, randomBoolean, shuffle } from './helper-functions';
import { AST, ColumnRefItem, Expr, ExpressionValue, Parser, Value } from 'node-sql-parser';
import {
  ITaskConfiguration,
  IParsedTable,
  IParsedColumn,
  IJoinPaths,
  IPath,
  aggregateTypes,
  numericTypes,
  textTypes,
  dateTypes,
  booleanTypes,
  orderableTypes,
  operationColumnTypes,
  operationType,
  joinType,
  aggregateColumnType,
  aggregateByColumnTypes,
  aggregateType,
  operationTypes,
  joinTypes,
} from './interfaces';
import { SelectASTBuilder } from './select-ast-builder';
import { error, table } from 'console';
import { ASTBuilder } from './ast-builder';
import { databaseMetadata, selfJoinDatabaseMetadata } from './internal-memory';
import { QueryGenerationDirector } from './query-generation-director';

export class SQLQueryGenerationService {
  queryGenerationDirector: QueryGenerationDirector;
  private maxShuffleCounter = 10;

  constructor(queryGenerationDirector: QueryGenerationDirector) {
    this.queryGenerationDirector = queryGenerationDirector;
  }


  public validateConfiguration(config: any): [boolean, string] {
    return this.queryGenerationDirector.validateConfiguration(config);
  }

  public async generateContextBasedQuery(
    context: ITaskConfiguration,
    databasekey: string,
    datasource: DataSource,
    schema: string
  ): Promise<[string, AST]> {

    let metadata = context.joinTypes.includes('SELF JOIN') ? this.getSelfJoinMetadata(databasekey) : this.getMetadata(databasekey);

    const filteredTables = this.filterTables(context, metadata);
    if (!filteredTables || filteredTables.length < 1) {
      console.log("Invalid Confiuration: Database does not meet required join depth, please adjust the configuration");
      throw new Error("Invalid Confiuration: Database does not meet required join depth, please adjust the configuration");
    }

    return this.queryGenerationDirector.buildQuery(context, metadata, filteredTables, datasource, schema, 0);
  }

  private filterTables(context: ITaskConfiguration, metadata: IParsedTable[]): IParsedTable[] {
    return context.joinDepth == 0 ? metadata : metadata
      .map(table => {
        const filteredPaths = table.joinPaths.filter(
          joinPath => context.joinTypes.includes('SELF JOIN') ? joinPath.depth >= context.joinDepth && joinPath.selfJoinDepth <= context.joinDepth : joinPath.depth >= context.joinDepth
        );

        if (filteredPaths.length > 0) {
          return {
            name: table.name,
            joinPaths: filteredPaths,
            columns: table.columns
          };
        }
        return {
          name: table.name,
          joinPaths: [],
          columns: table.columns
        };
      })
      .filter(table => table.joinPaths.length >= 1);
  }

  private getMetadata(databasekey: string) {
    let metadata = databaseMetadata.get(databasekey);
    if (!metadata) {
      console.log("No metadata found, please register database");
      throw new Error("No metadata found, please register database");
    }

    if (metadata.length < 1) {
      console.log("Database with empty tables");
      throw new Error("Database with empty tables");
    }
    return metadata;
  }

  private getSelfJoinMetadata(databasekey: string) {
    let metadata = selfJoinDatabaseMetadata.get(databasekey);
    if (!metadata) {
      console.log("No metadata found, please register database");
      throw new Error("No metadata found, please register database");
    }

    if (metadata.length < 1) {
      console.log("Database with empty tables");
      throw new Error("Database with empty tables");
    }
    return metadata;
  }

}
