import { SupportedLanguage } from '../../shared/i18n';
import { SQL_TEMPLATES_DE } from './sql-templates-de';

/**
 * Returns the SQL template map for the given language.
 * Falls back to English for any unsupported language.
 */
export function getTemplates(lang: SupportedLanguage): { [key: string]: string } {
    if (lang === 'de') return SQL_TEMPLATES_DE;
    return SQL_TEMPLATES;
}

export const SQL_TEMPLATES: { [key: string]: string } = {
    // -------------------------------------------------------------------------
    // SELECT — simple (no JOIN)
    // -------------------------------------------------------------------------
    "SELECT_ALL": "Retrieve all information about the {table} in the {database} database.",
    "SELECT_COLUMNS": "Retrieve {columns} in the {database} database.",
    /** DISTINCT variants — used when SELECT DISTINCT is present */
    "SELECT_DISTINCT_COLUMNS": "Retrieve unique {columns} in the {database} database.",

    // -------------------------------------------------------------------------
    // SELECT — with JOIN
    // -------------------------------------------------------------------------
    "SELECT_ALL_JOIN": "Retrieve all information about the following data combination in the {database} database.",
    "SELECT_COLUMNS_JOIN": "Retrieve {columns} from the following data combination in the {database} database.",
    /** DISTINCT variant for JOIN queries */
    "SELECT_DISTINCT_COLUMNS_JOIN": "Retrieve unique {columns} from the following data combination in the {database} database.",

    // -------------------------------------------------------------------------
    // Structural words used inline by the engine (not sentence-level templates)
    // -------------------------------------------------------------------------
    /**
     * Definite article placed before a table or column display name.
     * e.g. "the employees first name"
     */
    "COLUMN_PREFIX": "the ",
    /** Word used to join two items in a column list (e.g. "col1 and col2"). */
    "AND_JOINER": "and",
    /** Sort direction label for ASC. */
    "ORDER_ASC": "ascending",
    /** Sort direction label for DESC. */
    "ORDER_DESC": "descending",
    /** CASE expression structural words. */
    "CASE_WHEN": "when",
    "CASE_THEN": "then",
    "CASE_ELSE": "otherwise",

    // -------------------------------------------------------------------------
    // Boolean operators (used when combining WHERE / HAVING sub-conditions)
    // -------------------------------------------------------------------------
    "AND": "{left} and {right}",
    "OR": "{left} or {right}",

    // -------------------------------------------------------------------------
    // JOIN types
    // -------------------------------------------------------------------------
    "SELF_JOIN": "Match records within the {table} table where {condition}.",
    "INNER_JOIN": "Combine the data from the {table1} table and the {table2} table.",
    "LEFT_JOIN": "Include all data from the {table1} table and the matching data from the {table2} table.",
    "RIGHT_JOIN": "Include all data from the {table2} table and the matching data from the {table1} table.",
    "FULL_JOIN": "Include all records from both the {table1} table and the {table2} table.",
    "CROSS_JOIN": "Combine each record from the {table1} table with each record from the {table2} table.",
    /**
     * Used when a weak or associative entity is skipped in a JOIN chain.
     * The two placeholders represent the flanking strong entities.
     */
    "WEAK_BRIDGE": "Retrieve {table2} data related to each {table1}.",

    // -------------------------------------------------------------------------
    // Aggregate functions
    // -------------------------------------------------------------------------
    "AVG": "the average of {column}",
    "SUM": "the sum of {column}",
    "COUNT": "the number of {column}",
    "MAX": "the maximum {column}",
    "MIN": "the minimum {column}",

    // -------------------------------------------------------------------------
    // Comparison / predicate operators
    // -------------------------------------------------------------------------
    "=": "{left} equals {right}",
    ">": "{left} is greater than {right}",
    "<": "{left} is less than {right}",
    ">=": "{left} is greater than or equal to {right}",
    "<=": "{left} is less than or equal to {right}",
    "!=": "{left} does not equal {right}",
    "LIKE": "{left} matches the pattern {right}",
    "NOT LIKE": "{left} does not match the pattern {right}",
    "IN": "{left} is one of {right}",
    "NOT IN": "{left} is not one of {right}",
    "BETWEEN": "{left} is between {right}",
    "IS NULL": "{left} is not defined",
    "IS NOT NULL": "{left} is defined",
    "IS": "{left} is {right}",
    "IS NOT": "{left} is not {right}",

    // -------------------------------------------------------------------------
    // Subquery existence predicates
    // -------------------------------------------------------------------------
    "EXISTS": "there exists a related record where {condition}",
    "NOT_EXISTS": "there is no related record where {condition}",

    // -------------------------------------------------------------------------
    // CASE expression (in SELECT column list)
    // -------------------------------------------------------------------------
    "CASE": "a conditional value based on {conditions}",

    // -------------------------------------------------------------------------
    // Clauses that follow the FROM / JOIN block
    // -------------------------------------------------------------------------
    "WHERE": "Filter the results where {condition}.",
    "GROUP_BY": "Group the results based on {columns}.",
    "HAVING": "Filter the grouped results where {condition}.",
    "ORDER_BY": "Sort the results by {columns}.",

    // -------------------------------------------------------------------------
    // LIMIT / OFFSET
    // -------------------------------------------------------------------------
    "LIMIT": "Limit the results to {count} record(s).",
    "OFFSET": "Skip the first {count} record(s).",
    "LIMIT_OFFSET": "Limit the results to {count} record(s), starting from record {offset}.",

    // -------------------------------------------------------------------------
    // Set operations — chained via node._next in the AST
    // -------------------------------------------------------------------------
    "UNION": "{left} Additionally retrieve: {right}",
    "UNION_ALL": "{left} Additionally retrieve (including duplicates): {right}",
    "INTERSECT": "{left} Only include results that also appear in: {right}",
    "EXCEPT": "{left} Excluding results that appear in: {right}",
};
