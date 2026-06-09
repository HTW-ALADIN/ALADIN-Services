import { AST } from 'node-sql-parser';
import {
	ITaskConfiguration,
	IParsedTable,
} from '../../shared/interfaces/domain';
import {
	databaseMetadata,
	selfJoinDatabaseMetadata,
} from '../../database/internal-memory';
import { QueryGenerationDirector } from './query-generation-director';
import { RowQueryFn } from '../../shared/utils/database-utils';

export class SQLQueryGenerationService {
	queryGenerationDirector: QueryGenerationDirector;

	constructor(queryGenerationDirector: QueryGenerationDirector) {
		this.queryGenerationDirector = queryGenerationDirector;
	}

	public validateConfiguration(config: any): [boolean, string] {
		return this.queryGenerationDirector.validateConfiguration(config);
	}

	public async generateContextBasedQuery(
		context: ITaskConfiguration,
		databasekey: string,
		runQuery: RowQueryFn,
		schema: string,
	): Promise<[string, AST]> {
		const metadata = context.joinTypes.includes('SELF JOIN')
			? this.getSelfJoinMetadata(databasekey)
			: this.getMetadata(databasekey);

		const filteredTables = this.filterTables(context, metadata);
		if (!filteredTables || filteredTables.length < 1) {
			console.log(
				'Invalid Configuration: Database does not meet required join depth, please adjust the configuration',
			);
			throw new Error(
				'Invalid Configuration: Database does not meet required join depth, please adjust the configuration',
			);
		}

		return this.queryGenerationDirector.buildQuery(
			context,
			metadata,
			filteredTables,
			runQuery,
			schema,
			0,
		);
	}

	private filterTables(
		context: ITaskConfiguration,
		metadata: IParsedTable[],
	): IParsedTable[] {
		return context.joinDepth == 0
			? metadata
			: metadata
					.map((table) => {
						const filteredPaths = table.joinPaths.filter((joinPath) =>
							context.joinTypes.includes('SELF JOIN')
								? joinPath.depth >= context.joinDepth &&
									joinPath.selfJoinDepth <= context.joinDepth
								: joinPath.depth >= context.joinDepth,
						);

						return filteredPaths.length > 0
							? { ...table, joinPaths: filteredPaths }
							: { ...table, joinPaths: [] };
					})
					.filter((table) => table.joinPaths.length >= 1);
	}

	private getMetadata(databasekey: string): IParsedTable[] {
		const metadata = databaseMetadata.get(databasekey);
		if (!metadata) {
			console.log('No metadata found, please register database');
			throw new Error('No metadata found, please register database');
		}
		if (metadata.length < 1) {
			console.log('Database with empty tables');
			throw new Error('Database with empty tables');
		}
		return metadata;
	}

	private getSelfJoinMetadata(databasekey: string): IParsedTable[] {
		const metadata = selfJoinDatabaseMetadata.get(databasekey);
		if (!metadata) {
			console.log('No metadata found, please register database');
			throw new Error('No metadata found, please register database');
		}
		if (metadata.length < 1) {
			console.log('Database with empty tables');
			throw new Error('Database with empty tables');
		}
		return metadata;
	}
}
