// ---------------------------------------------------------------------------
// Primitive feedback unit
// ---------------------------------------------------------------------------

/**
 * A single piece of feedback for the student.
 *
 * `message`  — the user-facing hint that does not reveal the solution.
 * `solution` — an optional detail that discloses the expected / correct answer.
 *              When collapsed from a list (e.g. expected column names), values
 *              are joined into a single comma-separated string.
 */
export interface FeedbackEntry {
    message: string;
    solution?: string;
}

// ---------------------------------------------------------------------------
// Execution-plan feedback block (non-optional form used internally)
// ---------------------------------------------------------------------------

/**
 * The shape of the execution-plan feedback block.  Defined as a standalone
 * interface so the execution-plan comparator can use it as a concrete (non-
 * optional) parameter type without the `| undefined` that comes from
 * `AssembledFeedback['executionPlan']`.
 */
export interface ExecutionPlanFeedback {
    planRetrieval?:   FeedbackEntry;
    groupKey?:        FeedbackEntry;
    having?:          FeedbackEntry;
    orderBy?:         FeedbackEntry;
    where?:           FeedbackEntry;
    join?:            FeedbackEntry;
    distinct?:        FeedbackEntry;
    distinctStrategy?: FeedbackEntry;
    cte?:             FeedbackEntry;
    limit?:           FeedbackEntry;
    window?:          FeedbackEntry;
    windowPartition?: FeedbackEntry;
    windowOrderBy?:   FeedbackEntry;
    subqueryCount?:   FeedbackEntry;
    subplans?: {
        [subplanName: string]: SubplanFeedback;
    };
}

// ---------------------------------------------------------------------------
// Per-subplan feedback block (used recursively inside executionPlan)
// ---------------------------------------------------------------------------

export interface SubplanFeedback {
    /** InitPlan vs SubPlan type mismatch */
    type?:            FeedbackEntry;
    groupKey?:        FeedbackEntry;
    having?:          FeedbackEntry;
    orderBy?:         FeedbackEntry;
    where?:           FeedbackEntry;
    join?:            FeedbackEntry;
    distinct?:        FeedbackEntry;
    /** Informational only — different DISTINCT strategy, no grade penalty */
    distinctStrategy?: FeedbackEntry;
    cte?:             FeedbackEntry;
    limit?:           FeedbackEntry;
    window?:          FeedbackEntry;
    windowPartition?: FeedbackEntry;
    windowOrderBy?:   FeedbackEntry;
}

// ---------------------------------------------------------------------------
// Assembled feedback object
// ---------------------------------------------------------------------------

/**
 * The structured feedback object produced by FeedbackAssembler and returned
 * as part of ComparisonResult.
 *
 * Each top-level key corresponds to one comparator stage (or a cross-cutting
 * concern).  Every value is either a FeedbackEntry or a nested block of them.
 * Keys are only present when there is something to report — absent keys mean
 * "no issue found in this area".
 */
export interface AssembledFeedback {
    /**
     * Early-exit or cross-cutting messages that are not tied to a specific
     * comparator (executability errors, AST parse failures, wrong clause type).
     */
    general?: {
        executability?: FeedbackEntry;
        astParsing?:    FeedbackEntry;
        astArray?:      FeedbackEntry;
        sqlClauseType?: FeedbackEntry;
    };

    /** Result-set equality verdict. Always present on a normal grading run. */
    resultSet?: {
        verdict: FeedbackEntry;
    };

    /** AST-level structural comparison (columns, LIMIT, OFFSET). */
    ast?: {
        selectStatement?: FeedbackEntry;
        columns?:         FeedbackEntry;
        limit?:           FeedbackEntry;
        offset?:          FeedbackEntry;
    };

    /** Execution-plan diff feedback. */
    executionPlan?: ExecutionPlanFeedback;

    /**
     * Natural-language description of what the student query does.
     * Appended post-grading when the student query is not equivalent.
     */
    taskDescription?: {
        description: FeedbackEntry;
    };
}
