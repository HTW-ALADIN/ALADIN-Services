import { DataSource } from "typeorm";
import { PostgresConnectionOptions } from "typeorm/driver/postgres/PostgresConnectionOptions";

export type aggregateType = typeof aggregateTypes[number];
export const aggregateTypes = [
    'MAX',
    'MIN',
    'AVG',
    'COUNT',
    'SUM',
] as const;

export const invalidAggregationPatterns = /(_ID$|^ID_|-ID$|^ID-|_KEY$|^KEY_|-KEY$|^KEY-|_IMAGE$|^IMAGE_|-IMAGE$|^IMAGE-|_FILE$|^FILE_|-FILE$|^FILE-|_BLOB$|^BLOB_|-BLOB$|^BLOB-|_DATA$|^DATA_|-DATA$|^DATA-|_AT$|^AT_|-AT$|^AT-|_SYSTEM_|-SYSTEM-|^SYSTEM_|_META_|-META-|^META_|_LOG$|^LOG_|-LOG$|^LOG-|_FLAG$|^FLAG_|-FLAG$|^FLAG-|_STATUS$|^STATUS_|-STATUS$|^STATUS-|_IS_|-IS-|TEMP|TEST|DEBUG|(?<![a-zA-Z])Id(?![a-zA-Z])|(?<![a-zA-Z])Key(?![a-zA-Z])|(?<![a-zA-Z])Flag(?![a-zA-Z])|(?<![a-zA-Z])Status(?![a-zA-Z])|(?<![a-zA-Z])At(?![a-zA-Z])|\b[a-zA-Z]+(id|key)\b)/i;

export type joinType = typeof joinTypes[number];
export const joinTypes = [
    'LEFT JOIN',
    'FULL JOIN',
    'RIGHT JOIN',
    'CROSS JOIN',
    'INNER JOIN',
    'SELF JOIN'
] as const;

export const randomJoinTypes = [
    'LEFT JOIN',
    'FULL JOIN',
    'RIGHT JOIN',
    'INNER JOIN',
];

export const numericTypes = [
    'smallint',
    'integer',
    'bigint',
    'real',
    'double precision',
    'numeric',
    'decimal',
];
export const textTypes = [
    'char',
    'varchar',
    'text',
    'citext',
    'character varying',
    'character',
];
export const dateTypes = [
    'date',
    'time',
    'timetz',
    'timestamp',
    'timestamptz',
    'interval',
    'time without time zone',
    'time with time zone',
    'timestamp without time zone',
    'timestamp with time zone',
];
export const booleanTypes = ['boolean', 'bool'];
export const orderableTypes = [
    'bigint',
    'int8',
    'bigserial',
    'serial8',
    'bit',
    'bit varying',
    'varbit',
    'boolean',
    'bool',
    'box',
    'bytea',
    'character',
    'char',
    'character varying',
    'varchar',
    'cidr',
    'circle',
    'date',
    'double precision',
    'float8',
    'inet',
    'integer',
    'int',
    'int4',
    'interval',
    'json',
    'jsonb',
    'line',
    'lseg',
    'macaddr',
    'money',
    'numeric',
    'decimal',
    'path',
    'pg_lsn',
    'point',
    'polygon',
    'real',
    'float4',
    'smallint',
    'int2',
    'smallserial',
    'serial2',
    'serial',
    'serial4',
    'text',
    'time',
    'time without time zone',
    'time with time zone',
    'timestamp',
    'timestamp without time zone',
    'timestamp with time zone',
    'tsquery',
    'tsvector',
    'txid_snapshot',
    'uuid',
    'xml',
];

export const operationTypes =
{
    "EQUAL": [...textTypes, ...numericTypes, ...dateTypes],
    "COMPARISON": [...textTypes, ...numericTypes, ...dateTypes],
    "IN": [...textTypes, ...numericTypes, ...dateTypes],
    "IS_NULL": [],
    "LIKE": [...textTypes],
    "BETWEEN": [...textTypes, ...numericTypes, ...dateTypes],
    "IS_BOOLEAN": [...booleanTypes],
};

export const operationColumnTypes = [
    ...textTypes,
    ...numericTypes,
    ...dateTypes,
    ...booleanTypes
];

export type operationType = keyof typeof operationTypes;

export const aggregateColumnType = [...numericTypes, ...textTypes, ...dateTypes];

export const aggregateByColumnTypes: Record<'numericTypes' | 'textTypes' | 'dateTypes', aggregateType[]> = {
    numericTypes: ['MAX', 'MIN', 'AVG', 'COUNT', 'SUM'],
    textTypes: ['MAX', 'MIN', 'COUNT'],
    dateTypes: ['MAX', 'MIN', 'COUNT'],
};

export interface IParsedTable {
    name: string;
    joinPaths: IJoinPaths[];
    columns: IParsedColumn[];
}

export interface IParsedColumn {
    name: string;
    type: string;
    tableName: string;
    aggregation?: aggregateType;
    isNullable: boolean;
}

export interface IJoinPaths {
    path: IPath[];
    isSelfJoin: boolean;
    depth: number;
    selfJoinDepth: number
}

export interface IPath {
    tableName: string;
    relationKey: string;
}

export enum GptOptions {
    Creative = "creative",
    MultiStep = "multi-step",
    Default = "default"
}

export enum GenerationOptions {
    Template = "template",
    LLM = "llm",
    Hybrid = "hybrid"
}

export interface ITaskConfiguration {
    aggregation: boolean;
    orderby: boolean;
    joinDepth: number;
    joinTypes: joinType[];
    predicateCount: number;
    groupby: boolean;
    having: boolean;
    columnCount: number;
    operationTypes: operationType[]
}

export interface IRequestTaskOptions {
    connectionInfo: PostgresConnectionOptions,
    taskConfiguration: ITaskConfiguration
}


export interface IRequestGradingOptions {
    connectionInfo: PostgresConnectionOptions,
    gradingRequest: GradingRequest
}

export interface IParsedExecutionPlan {
    groupKey?: string[],
    havingFilter?: string;
    sortKey?: string[];
    whereFilter?: string[];
    joinStatement?: JoinStatement;
}

export interface JoinStatement {
    joinType?: string;
    tableName: string;
    joinedTable?: JoinStatement;
    joinCondition?: string;
}

export interface QueryPlanNode {
    "Node Type"?: string;
    "Strategy"?: string;
    "Partial Mode"?: string;
    "Parallel Aware"?: boolean;
    "Startup Cost"?: number;
    "Total Cost"?: number;
    "Plan Rows"?: number;
    "Plan Width"?: number;
    "Group Key"?: string[];
    "Filter"?: string;
    "Plans"?: QueryPlanNode[];
    "Parent Relationship": string;
    "Sort Key"?: string[];
    "Join Type"?: string;
    "Join Filter": string;
    "Inner Unique"?: boolean;
    "Hash Cond"?: string;
    "Alias"?: string;
    "Relation Name"?: string;
    "Index Cond"?: string;
    "Recheck Cond"?: string;
}

export type QueryPlanKeys = "Node Type" | "Strategy" | "Partial Mode" | "Parallel Aware" | "Startup Cost" | "Total Cost" | "Plan Rows" | "Plan Width" | "Group Key" | "Filter" | "Plans" | "Parent Relationship" | "Sort Key" | "Join Type" | "Join Filter" | "Inner Unique" | "Hash Cond" | "Alias" | "Relation Name" | "Index Cond" | "Recheck Cond";

export interface QueryPlan {
    "QUERY PLAN": Plan[];
}

export interface Plan {
    "Plan": QueryPlanNode;
}

export interface ComparisonResult {
    feedback: string[];
    feedbackWithSolution: string[];
    grade: number;
    equivelant: boolean;
    supportedQueryType: boolean;
}

export interface TaskResponse {
    templateBasedDescription: string;
    gptEntityRelationshipDescription: string;
    gptSchemaBasedDescription: string,
    hybridDescription: string,
    query: string;
    gptCreativeDescription?: string,
}

export interface GradingRequest {
    referenceQuery: string;
    studentQuery: string;
}