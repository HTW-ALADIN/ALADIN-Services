import { DataSource, Table } from 'typeorm';
import 'reflect-metadata';
import {
  IParsedColumn,
  IParsedTable,
  IJoinPaths,
  IPath,
} from './interfaces';
import { databaseMetadata, selfJoinDatabaseMetadata } from './internal-memory';
export class DatabaseAnalyzer {


  public async extractDatabaseSchema(
    dataSource: DataSource,
    schema: string,
    databaseKey: string
  ): Promise<boolean> {
    try {
      const queryRunner = dataSource.createQueryRunner();

      const tables: Table[] = await queryRunner.getTables();

      await queryRunner.release();

      const filteredTables = tables.filter(
        table => table.schema === schema
      );

      if (filteredTables.length == 0)
        return false;

      let parsedTables: IParsedTable[] = [];
      let selfJoinTable: IParsedTable[] = [];
      filteredTables.forEach(table => {
        const tableName = this.getTableName(table.name);
        const parsedColumns: IParsedColumn[] = [];
        table.columns.forEach(column => {
          parsedColumns.push({
            name: column.name,
            tableName: tableName,
            type: column.type,
            isNullable: column.isNullable,
          });
        });

        const joinPaths = this.findJoinPaths(
          tableName,
          [],
          0,
          new Set(),
          filteredTables,
          schema,
          false
        );

        let selfJoinPaths;
        let otherPaths;
        [selfJoinPaths, otherPaths] = this.separateSelfAndNonSelfJoinPaths(joinPaths);


        parsedTables.push({
          name: tableName,
          joinPaths: this.filterJoinPaths(tableName, otherPaths),
          columns: parsedColumns,
        });
        selfJoinTable.push({
          name: tableName,
          joinPaths: this.filterJoinPaths(tableName, selfJoinPaths),
          columns: parsedColumns,
        })
      });
      databaseMetadata.set(databaseKey, parsedTables);
      selfJoinDatabaseMetadata.set(databaseKey, selfJoinTable)
      return true;
    } catch (error: any) {
      console.log("Unable to parse database schema", error);
      return false;
    }
  }

  private findJoinPaths(
    tableName: string,
    path: IPath[],
    depth: number,
    visited: Set<string>,
    tables: Table[],
    schema: string,
    isPreviousPathSelfJoin: boolean
  ): IJoinPaths[] {
    const results: IJoinPaths[] = [];
    const visitedPaths = new Set(visited);

    const table = tables.find(
      (table) => table.name === `${schema}.${tableName}` || table.name === tableName
    );

    if (!table) return results;

    const relatedTables = table.foreignKeys.map((fk) => ({
      tableName: this.getTableName(fk.referencedTableName),
      relationKey: `${this.getTableName(table.name)}.${fk.columnNames[0]} = ${this.getTableName(fk.referencedTableName)}.${fk.referencedColumnNames[0]}`
    }));

    for (const relation of relatedTables) {
      const newPath: IPath[] = [...path, { tableName: relation.tableName, relationKey: relation.relationKey }];
      const pathKey = `${tableName}-${relation.relationKey}-${relation.tableName}`;

      if (visitedPaths.has(pathKey)) continue; // Avoid duplicates
      visitedPaths.add(pathKey);

      const newDepth = depth + 1;
      const isSelfJoin = isPreviousPathSelfJoin || tableName === relation.tableName;

      results.push({
        path: newPath,
        depth: newDepth,
        isSelfJoin: isSelfJoin,
        selfJoinDepth: 0
      });

      const recursivePaths = this.findJoinPaths(
        relation.tableName,
        newPath,
        newDepth,
        new Set(visitedPaths),
        tables,
        schema,
        isSelfJoin
      );

      results.push(...recursivePaths);
    }

    return results;
  }

  private separateSelfAndNonSelfJoinPaths(paths: IJoinPaths[]): [selfPaths: IJoinPaths[], otherPaths: IJoinPaths[]] {
    const selfJoinTables: IParsedTable[] = [];
    const nonSelfJoinTables: IParsedTable[] = [];

    let selfPaths = paths.filter(path => path.isSelfJoin);
    let otherPaths = paths.filter(path => !path.isSelfJoin);

    return [selfPaths, otherPaths];
  }

  private filterJoinPaths(currentTableName: string, paths: IJoinPaths[]): IJoinPaths[] {
    const uniquePaths = new Map<string, IJoinPaths>();

    for (const path of paths) {
      const key = path.path.map(p => p.tableName).join('->');

      let selfJoinDepth: number = 0;
      let selfJoinCount = 0;
      if (path.isSelfJoin) {
        const tableNames = new Set<string>();
        for (let i = 0; i < path.path.length; i++) {

          const tableName = path.path[i].tableName;

          if (currentTableName === tableName) {
            selfJoinDepth = i + 1;
          }
          if (tableNames.has(tableName)) {
            selfJoinCount = 2;

            if (selfJoinCount === 2) {
              selfJoinDepth = i + 1;
            }
          } else {
            tableNames.add(tableName);
          }
        }
      }
      const pathWithSelfJoinDepth: IJoinPaths = {
        ...path,
        selfJoinDepth: selfJoinDepth,
      };

      const existingPath = uniquePaths.get(key);
      if (!existingPath || existingPath.depth < path.depth) {
        uniquePaths.set(key, pathWithSelfJoinDepth);
      }
    }

    const sortedPaths = Array.from(uniquePaths.values()).sort((a, b) => b.depth - a.depth);

    const finalPaths: IJoinPaths[] = [];
    const seenKeys = new Set<string>();

    for (const path of sortedPaths) {
      const key = path.path.map(p => p.tableName).join('->');

      let isSubPath = false;
      for (const existingKey of seenKeys) {
        if (existingKey.startsWith(key)) {
          isSubPath = true;
          break;
        }
      }

      if (!isSubPath) {
        finalPaths.push(path);
        seenKeys.add(key);
      }
    }

    return finalPaths;
  }

  private getTableName(tableName: string) {
    const names = tableName.split('.');
    return names.length > 1 ? names[1] : names[0];
  }

}