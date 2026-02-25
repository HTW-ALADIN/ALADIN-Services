
import { DataSource } from "typeorm";
import { invalidAggregationPatterns, ITaskConfiguration } from "./interfaces";
import { databaseMetadata } from "./internal-memory";
import { Column } from "node-sql-parser";

export function random(length: number) {
    return Math.floor(Math.random() * length);
}

export function randomBoolean() {
    return Math.random() < 0.5;
}

export function shuffle(array: any[]) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

export function createQueryRunner(dataSource: DataSource) {
    if (!dataSource) {
        console.log("Undefined datasource, please establish a database connection")
        return undefined;
    }

    return dataSource.createQueryRunner();
}

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

export function isDatabaseRegistered(databaseKey: string): boolean {
    return databaseMetadata.has(databaseKey);
}

export function isValidForAggregation(columnName: string): boolean {
    return !invalidAggregationPatterns.test(columnName);
}