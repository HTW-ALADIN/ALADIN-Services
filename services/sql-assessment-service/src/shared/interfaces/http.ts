import { PostgresConnectionOptions } from 'typeorm/driver/postgres/PostgresConnectionOptions';
import { ITaskConfiguration } from './domain';

export interface GradingRequest {
	referenceQuery: string;
	studentQuery: string;
}

export interface IRequestTaskOptions {
	connectionInfo: PostgresConnectionOptions;
	taskConfiguration: ITaskConfiguration;
	/** BCP 47 language code for error messages (e.g. "en", "de"). Defaults to "en". */
	languageCode?: string;
}

export interface IRequestGradingOptions {
	connectionInfo: PostgresConnectionOptions;
	gradingRequest: GradingRequest;
	/** BCP 47 language code for error messages (e.g. "en", "de"). Defaults to "en". */
	languageCode?: string;
}

export interface TaskResponse {
	templateBasedDescription: string;
	gptEntityRelationshipDescription: string;
	gptSchemaBasedDescription: string;
	hybridDescription: string;
	query: string;
	gptCreativeDescription?: string;
}

export interface ComparisonResult {
	feedback: string[];
	feedbackWithSolution: string[];
	grade: number;
	/** Whether the student query is semantically equivalent to the reference query. */
	equivalent: boolean;
	supportedQueryType: boolean;
}

export interface IRequestDescriptionOptions {
	connectionInfo: PostgresConnectionOptions;
	/** Raw SQL query string to generate a description for. */
	query: string;
	/** Whether the query involves a self-join. Defaults to false. */
	isSelfJoin?: boolean;
	/**
	 * BCP 47 language code for the desired output language (e.g. "en", "de", "nl").
	 * Defaults to "en".
	 */
	languageCode?: string;
}

export interface DescriptionResponse {
	description: string;
	/** The language code that was requested (echoes the input, defaults to "en"). */
	languageCode: string;
}

export interface IRequestQueryOptions {
	connectionInfo: PostgresConnectionOptions;
	/** Raw SQL SELECT query to execute against the registered database. */
	query: string;
	/** BCP 47 language code for error messages (e.g. "en", "de"). Defaults to "en". */
	languageCode?: string;
}

export interface QueryExecutionResult {
	/** Rows returned by the query. Each row is a plain key→value object. */
	rows: Record<string, unknown>[];
	/** Number of rows returned. */
	rowCount: number;
}

/**
 * Shared request body for all grading comparison sub-endpoints.
 * Flat (no nested gradingRequest) to keep individual comparison calls simple.
 */
export interface IRequestComparisonOptions {
	connectionInfo: PostgresConnectionOptions;
	referenceQuery: string;
	studentQuery: string;
	/** BCP 47 language code for error messages (e.g. "en", "de"). Defaults to "en". */
	languageCode?: string;
}

/** Response from POST /api/grading/compare/result-set */
export interface ResultSetComparisonResponse {
	/** Whether both queries return identical result sets. */
	match: boolean;
	feedback: string[];
}

/** Response from POST /api/grading/compare/ast */
export interface ASTComparisonResponse {
	/** Whether the SELECT column lists match. */
	columnsMatch: boolean;
	/**
	 * Whether the query uses a supported structure (no DISTINCT, no subqueries).
	 * When false, only result-set equivalence is meaningful for grading.
	 */
	supported: boolean;
	feedback: string[];
	feedbackWithSolution: string[];
}

/** Response from POST /api/grading/compare/execution-plan */
export interface ExecutionPlanComparisonResponse {
	/** Whether all compared plan elements (WHERE, GROUP BY, ORDER BY, JOIN) match. */
	plansMatch: boolean;
	feedback: string[];
	feedbackWithSolution: string[];
	/** Number of grade points deducted based on plan differences. */
	penaltyPoints: number;
}
