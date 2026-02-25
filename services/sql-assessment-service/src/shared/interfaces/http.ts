import { PostgresConnectionOptions } from 'typeorm/driver/postgres/PostgresConnectionOptions';
import { GenerationOptions, GptOptions, ITaskConfiguration } from './domain';

/**
 * Statistics attached to a reference query, recording how prior student
 * cohorts have interacted with it.  All fields are optional — callers may
 * supply as much or as little context as they have available.
 */
export interface ReferenceQueryStats {
	/**
	 * Number of times this exact query was submitted by a student across all
	 * prior attempts (across all students and sessions).
	 */
	timesFoundByStudents?: number;
	/**
	 * Average number of attempts a student needed before arriving at this query.
	 * A low value (e.g. 1–2) indicates it is a commonly reached solution;
	 * a high value suggests it is an uncommon, advanced variant.
	 */
	averageAttemptsToFind?: number;
	/** Any additional free-form metadata the caller wishes to persist. */
	[key: string]: unknown;
}

/**
 * A single reference (model) query together with optional prior-cohort
 * statistics.  Endpoints that accept a collection of reference solutions
 * use this shape for each element.
 */
export interface ReferenceQuery {
	/** The SQL string of the reference (model) solution. */
	query: string;
	/** Optional statistics from prior student cohorts. */
	stats?: ReferenceQueryStats;
}

export interface GradingRequest {
	/**
	 * A single reference query string.
	 * @deprecated Prefer `referenceQueries` (collection with optional stats).
	 *   When both are supplied `referenceQueries` takes precedence.
	 */
	referenceQuery?: string;
	/**
	 * One or more reference (model) solutions.  The grading pipeline will
	 * select the closest one to the student query before comparison.
	 * At least one of `referenceQuery` or `referenceQueries` must be present.
	 */
	referenceQueries?: ReferenceQuery[];
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
	/**
	 * Which task-description generation strategy to use when the student query
	 * is not equivalent to the reference query.  Defaults to the previous
	 * behaviour (Hybrid when the query type is supported, LLM otherwise).
	 */
	generationStrategy?: GenerationOptions;
	/**
	 * GPT option forwarded to the LLM engine when generationStrategy is
	 * GenerationOptions.LLM.  Defaults to GptOptions.Default.
	 */
	gptOption?: GptOptions;
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
	/**
	 * A single reference query string.
	 * @deprecated Prefer `referenceQueries`.  When both are supplied,
	 *   `referenceQueries` takes precedence.
	 */
	referenceQuery?: string;
	/**
	 * One or more reference solutions.  The closest one to the student query
	 * is selected automatically before the comparison is run.
	 */
	referenceQueries?: ReferenceQuery[];
	studentQuery: string;
	/** BCP 47 language code for error messages (e.g. "en", "de"). Defaults to "en". */
	languageCode?: string;
	/**
	 * Which task-description generation strategy to use.
	 * Only relevant for endpoints that generate a student task description
	 * (currently /grade).  Defaults to the previous behaviour.
	 */
	generationStrategy?: GenerationOptions;
	/**
	 * GPT option forwarded to the LLM engine when generationStrategy is
	 * GenerationOptions.LLM.  Defaults to GptOptions.Default.
	 */
	gptOption?: GptOptions;
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
