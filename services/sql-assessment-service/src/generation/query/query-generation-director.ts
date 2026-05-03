import { AST } from 'node-sql-parser';
import { ASTBuilder } from './ast-builder';
import {
	IParsedTable,
	ITaskConfiguration,
} from '../../shared/interfaces/domain';
import { RowQueryFn } from '../../shared/utils/database-utils';

export interface QueryGenerationDirector {
	astBuilder: ASTBuilder;
	buildQuery(
		context: ITaskConfiguration,
		metadata: IParsedTable[],
		filteredTables: IParsedTable[],
		runQuery: RowQueryFn,
		schema: string,
		shuffleCounter: number,
	): Promise<[string, AST]>;

	validateConfiguration(configuration: any): [boolean, string];
}
