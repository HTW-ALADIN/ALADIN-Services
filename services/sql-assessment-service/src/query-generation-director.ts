import { AST } from "node-sql-parser";
import { ASTBuilder } from "./ast-builder";
import { IParsedTable, ITaskConfiguration } from "./interfaces";
import { DataSource } from "typeorm";

export interface QueryGenerationDirector {
    astBuilder: ASTBuilder;
    buildQuery(context: ITaskConfiguration, metadata: IParsedTable[],
        filteredTables: IParsedTable[],
        datasource: DataSource,
        schema: string,
        shuffleCounter: number): Promise<[string, AST]>;

    validateConfiguration(configuration: any): [boolean, string];
}
