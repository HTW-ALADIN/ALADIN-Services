import { DataSource, QueryRunner } from 'typeorm';
import { IAliasMap, IParsedTable } from '../interfaces/domain';

export function generateDatabaseKey(host: string, port: number, schema: string): string {
    return `${host}${port}${schema}`;
}

export async function connectToDatabase(dataSource: DataSource): Promise<boolean> {
    let isConnected = false;
    await dataSource
        .initialize()
        .then(() => {
            console.log(`Data Source ${dataSource} has been initialized!`);
            isConnected = true;
        })
        .catch(err => {
            console.error(
                `Error during Data Source ${dataSource} initialization`,
                err
            );
            isConnected = false;
        });
    return isConnected;
}

export function createQueryRunner(dataSource: DataSource): QueryRunner | undefined {
    if (!dataSource) {
        console.log('Undefined datasource, please establish a database connection');
        return undefined;
    }
    return dataSource.createQueryRunner();
}

/**
 * Reconstructs an {@link IAliasMap} from the `alternativeName` fields that
 * were burned into `IParsedTable` / `IParsedColumn` records at analysis time.
 *
 * Only entries that actually have an `alternativeName` are included, so the
 * result is `undefined` when no alias data is present (no analysis with an
 * aliasMap was performed).
 */
export function buildAliasMapFromTables(tables: IParsedTable[]): IAliasMap | undefined {
    const tableAliases: Record<string, string> = {};
    const columnAliases: Record<string, Record<string, string>> = {};

    for (const table of tables) {
        if (table.alternativeName) {
            tableAliases[table.name] = table.alternativeName;
        }

        for (const col of table.columns) {
            if (col.alternativeName) {
                if (!columnAliases[table.name]) {
                    columnAliases[table.name] = {};
                }
                columnAliases[table.name][col.name] = col.alternativeName;
            }
        }
    }

    const hasTableAliases  = Object.keys(tableAliases).length  > 0;
    const hasColumnAliases = Object.keys(columnAliases).length > 0;

    if (!hasTableAliases && !hasColumnAliases) return undefined;

    return {
        ...(hasTableAliases  ? { tables:  tableAliases  } : {}),
        ...(hasColumnAliases ? { columns: columnAliases } : {}),
    };
}
