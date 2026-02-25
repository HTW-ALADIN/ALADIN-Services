import { AST, Select } from 'node-sql-parser';
import { JoinComparator } from '../join-comparator';
import { AssembledFeedback, FeedbackEntry } from '../../shared/interfaces/feedback';

// ---------------------------------------------------------------------------
// Result types
// ---------------------------------------------------------------------------

export interface LimitComparisonResult {
    match: boolean;
    ast: AssembledFeedback['ast'];
}

export interface ASTComparisonResult {
    /**
     * Whether the SELECT column lists are semantically equivalent
     * (same tables, same column names, same aggregate functions).
     */
    columnsMatch: boolean;
    /**
     * Whether the student query uses a structural pattern that the execution-plan
     * comparator can handle.  Returns false only for FROM-clause derived-table
     * subqueries, which are too complex for the current plan-diffing pipeline.
     *
     * DISTINCT, WHERE/HAVING subqueries, CTEs, LIMIT and window functions are
     * all supported and will NOT set this flag to false.
     */
    supported: boolean;
    /** Whether the LIMIT / OFFSET clauses match between both queries. */
    limitMatch: boolean;
    ast: AssembledFeedback['ast'];
    /** Alias→real-table map derived from the student query's FROM clause. */
    studentAliasMap: Record<string, string>;
    /** Alias→real-table map derived from the reference query's FROM clause. */
    referenceAliasMap: Record<string, string>;
}

// ---------------------------------------------------------------------------
// ASTComparator
// ---------------------------------------------------------------------------

/**
 * Compares two parsed SQL query ASTs at the structural level.
 *
 * Responsibilities:
 *  - Detect FROM-clause derived-table subqueries (the only remaining unsupported pattern).
 *  - Build alias→table maps from the FROM/JOIN clauses.
 *  - Compare the SELECT column lists (plain columns and aggregate functions).
 *  - Compare LIMIT / OFFSET clauses directly from the AST.
 *
 * The following patterns that were previously marked "unsupported" are now
 * handled by the execution-plan comparator and are no longer short-circuited here:
 *  - SELECT DISTINCT
 *  - WHERE / HAVING scalar subqueries
 *  - CTEs (WITH …)
 */
export class ASTComparator {

    constructor(private readonly joinComparator: JoinComparator) {}

    /**
     * Compares the AST of a student query against a reference query.
     *
     * Both ASTs must already be parsed by the caller; this class performs no
     * SQL parsing itself.
     */
    public compare(studentAST: AST, referenceAST: AST): ASTComparisonResult {
        const ast: AssembledFeedback['ast'] = {};
        const emptyMaps = { studentAliasMap: {}, referenceAliasMap: {} };
        const defaultLimitMatch = true;

        // ── Unsupported structure: FROM-clause derived-table subqueries ───────
        // These produce a complex nested plan that the current diffing pipeline
        // cannot meaningfully compare — fall back to result-set-only grading.

        if (this.hasDerivedTableSubquery(studentAST)) {
            return {
                columnsMatch: false,
                supported:    false,
                limitMatch:   defaultLimitMatch,
                ast,
                ...emptyMaps,
            };
        }

        // ── SELECT-only guard ────────────────────────────────────────────────

        if (studentAST.type !== 'select' || referenceAST.type !== 'select') {
            ast.selectStatement = { message: 'Error: Not a select statement.' };
            return {
                columnsMatch: false,
                supported:    false,
                limitMatch:   defaultLimitMatch,
                ast,
                ...emptyMaps,
            };
        }

        const studentSelect   = studentAST  as Select;
        const referenceSelect = referenceAST as Select;

        if (!studentSelect.columns || !referenceSelect.columns) {
            ast.selectStatement = { message: 'Error: Not a select statement.' };
            return {
                columnsMatch: false,
                supported:    false,
                limitMatch:   defaultLimitMatch,
                ast,
                ...emptyMaps,
            };
        }

        // ── Alias maps ───────────────────────────────────────────────────────

        const studentAliasMap   = this.buildAliasMap(studentSelect.from  as any[]);
        const referenceAliasMap = this.buildAliasMap(referenceSelect.from as any[]);

        // ── Column comparison ────────────────────────────────────────────────

        const [sameColumns, columnFeedbackMsg] = this.areColumnsEqual(
            studentSelect.columns,
            referenceSelect.columns,
            studentAliasMap,
            referenceAliasMap
        );

        if (!sameColumns) {
            const solutionParts: string[] = [];
            referenceSelect.columns.forEach((column: any) => {
                if (column?.expr?.type === 'column_ref') {
                    solutionParts.push(
                        `${column?.expr?.table}.${column?.expr?.column?.expr?.value}`
                    );
                }
                if (column?.expr?.type === 'aggr_func') {
                    solutionParts.push(
                        `${column?.expr?.name}(${column?.expr?.args?.expr?.table}.${column?.expr?.args?.expr?.column?.expr?.value})`
                    );
                }
            });

            const entry: FeedbackEntry = {
                message: `The column selection is incorrect: ${columnFeedbackMsg}`,
            };
            if (solutionParts.length > 0) {
                entry.solution = `The task requires the selection of the following columns: ${solutionParts.join(', ')}`;
            }
            ast.columns = entry;
        }

        // ── LIMIT / OFFSET comparison ────────────────────────────────────────

        const limitResult = this.compareLimitOffset(studentSelect, referenceSelect);
        if (limitResult.ast?.limit) ast.limit   = limitResult.ast.limit;
        if (limitResult.ast?.offset) ast.offset = limitResult.ast.offset;

        return {
            columnsMatch:     sameColumns,
            supported:        true,
            limitMatch:       limitResult.match,
            ast,
            studentAliasMap,
            referenceAliasMap,
        };
    }

    // =========================================================================
    // Structure detection
    // =========================================================================

    /**
     * Returns true when the student query uses a FROM-clause derived-table
     * subquery (e.g. `SELECT … FROM (SELECT …) AS sub`).
     *
     * node-sql-parser represents this as a FROM entry whose `expr.ast.type`
     * is `'select'` (the inner query is wrapped in an `expr` with `parentheses: true`).
     *
     * This is the *only* pattern that causes `supported: false` after this
     * refactor.  WHERE/HAVING scalar subqueries, DISTINCT and CTEs are handled
     * by the execution-plan comparator.
     */
    public hasDerivedTableSubquery(ast: AST): boolean {
        if (ast.type !== 'select') return false;
        const select = ast as Select;
        if (!select.from) return false;

        return (select.from as any[]).some((entry: any) =>
            // node-sql-parser wraps derived tables as: { expr: { ast: { type: 'select', ... }, parentheses: true }, as: '...' }
            entry?.expr?.ast?.type === 'select'
        );
    }

    /**
     * Returns true when the query uses SELECT DISTINCT.
     * node-sql-parser sets `distinct` to `{ type: 'DISTINCT' }` (not `true`).
     * (No longer causes `supported: false`.)
     */
    public hasDistinct(ast: AST): boolean {
        const d = (ast as any).distinct;
        if (!d) return false;
        // node-sql-parser v5+: distinct is { type: 'DISTINCT' } when present
        if (typeof d === 'object' && d.type === 'DISTINCT') return true;
        // older versions may use boolean true
        if (d === true) return true;
        return false;
    }

    /**
     * Returns true when the query uses one or more CTEs (WITH … AS …).
     * (No longer causes `supported: false`.)
     */
    public hasCTE(ast: AST): boolean {
        return Array.isArray((ast as any).with) && (ast as any).with.length > 0;
    }

    /**
     * Returns true when the query contains any subquery in WHERE, HAVING,
     * SELECT columns, etc. — but NOT in the FROM clause (those are caught
     * by hasDerivedTableSubquery).
     *
     * Used by SQLQueryGradingService to know that subplan diffing is expected.
     */
    public hasScalarSubquery(ast: AST): boolean {
        if (ast.type !== 'select') return false;
        const select = ast as Select;

        const nonFromLocations = ['where', 'having', 'columns', 'orderby', 'groupby'];
        for (const loc of nonFromLocations) {
            if (this.containsSubquery((select as any)[loc])) return true;
        }
        return false;
    }

    private containsSubquery(node: any): boolean {
        if (!node || typeof node !== 'object') return false;
        if (node.type === 'select') return true;

        if (Array.isArray(node)) {
            return node.some(child => this.containsSubquery(child));
        }

        return Object.values(node).some(value => this.containsSubquery(value));
    }

    // =========================================================================
    // LIMIT / OFFSET
    // =========================================================================

    /**
     * Compares the LIMIT and OFFSET AST nodes of two SELECT statements.
     *
     * The comparison is purely AST-based because EXPLAIN (FORMAT JSON) without
     * VERBOSE does not expose the limit value — only the presence of a Limit
     * node.  The execution-plan comparator checks presence only; this method
     * checks the actual values.
     */
    public compareLimitOffset(
        studentSelect: Select,
        referenceSelect: Select
    ): LimitComparisonResult {
        const ast: AssembledFeedback['ast'] = {};

        const stuLimit  = this.parseLimitClause((studentSelect  as any).limit).limit;
        const refLimit  = this.parseLimitClause((referenceSelect as any).limit).limit;
        const stuOffset = this.parseLimitClause((studentSelect  as any).limit).offset;
        const refOffset = this.parseLimitClause((referenceSelect as any).limit).offset;

        let match = true;

        if (stuLimit !== refLimit) {
            match = false;
            ast.limit = {
                message:  'Incorrect LIMIT value.',
                solution: `Expected LIMIT ${refLimit ?? 'none'}, got ${stuLimit ?? 'none'}.`,
            };
        }

        if (stuOffset !== refOffset) {
            match = false;
            ast.offset = {
                message:  'Incorrect OFFSET value.',
                solution: `Expected OFFSET ${refOffset ?? 'none'}, got ${stuOffset ?? 'none'}.`,
            };
        }

        return { match, ast };
    }

    /**
     * Parses a node-sql-parser `limit` AST node into { limit, offset }.
     *
     * node-sql-parser (v5+) represents:
     *   LIMIT n            → { seperator: '',       value: [{ type: 'number', value: n }] }
     *   LIMIT n OFFSET m   → { seperator: 'offset', value: [{ type: 'number', value: n }, { type: 'number', value: m }] }
     *   (no LIMIT)         → { seperator: '',       value: [] }  or  null
     */
    private parseLimitClause(limitNode: any): { limit: number | null; offset: number | null } {
        if (!limitNode || !Array.isArray(limitNode.value) || limitNode.value.length === 0) {
            return { limit: null, offset: null };
        }
        const limit  = limitNode.value[0]?.value ?? null;
        const offset = limitNode.value.length > 1 ? (limitNode.value[1]?.value ?? null) : null;
        return { limit, offset };
    }

    // =========================================================================
    // Alias map
    // =========================================================================

    /**
     * Builds an alias→table-name map from a FROM/JOIN array.
     * Handles self-joins by appending a "0"/"1" suffix so each alias resolves
     * to a distinct logical name.
     */
    public buildAliasMap(from: any[]): Record<string, string> {
        const aliasMap: Record<string, string> = {};
        let previousJoinedTable = '';
        let previousJoinedAlias = '';

        if (!from) return aliasMap;

        from.forEach((entry: any) => {
            const alias = entry.as;
            if (alias) {
                const table      = entry.table;
                const isSelfJoin = table === previousJoinedTable;
                if (isSelfJoin) {
                    const selfJoinTable = entry.join === 'RIGHT JOIN' ? `${table}0` : `${table}1`;
                    aliasMap[alias]               = selfJoinTable;
                    aliasMap[previousJoinedAlias] =
                        entry.join === 'RIGHT JOIN'
                            ? `${previousJoinedTable}1`
                            : `${previousJoinedTable}0`;
                } else {
                    aliasMap[alias] = table;
                }
                previousJoinedAlias = alias;
                previousJoinedTable = table;
            }
        });

        return aliasMap;
    }

    // =========================================================================
    // Column equality
    // =========================================================================

    private areColumnsEqual(
        student: any[],
        reference: any[],
        studentAliasMap:   Record<string, string>,
        referenceAliasMap: Record<string, string>
    ): [boolean, string] {
        if (student.length !== reference.length) {
            return [false, 'Incorrect number of columns selected.'];
        }

        let allSame = true;
        let firstMismatch = '';
        reference.forEach((refCol) => {
            const found = student.find((stuCol: any) => {
                if (refCol?.expr?.type === 'aggr_func') {
                    const refTable = this.joinComparator.normalizeTableName(
                        refCol?.expr?.args?.expr?.table, referenceAliasMap
                    );
                    const stuTable = this.joinComparator.normalizeTableName(
                        stuCol?.expr?.args?.expr?.table, studentAliasMap
                    );
                    return (
                        refTable === stuTable &&
                        stuCol.expr?.name === refCol.expr?.name &&
                        stuCol?.expr?.args?.expr?.column?.expr?.value ===
                            refCol?.expr?.args?.expr?.column?.expr?.value
                    );
                } else if (refCol?.expr?.type === 'column_ref') {
                    const refTable = this.joinComparator.normalizeTableName(
                        refCol?.expr?.table, referenceAliasMap
                    );
                    const stuTable = this.joinComparator.normalizeTableName(
                        stuCol?.expr?.table, studentAliasMap
                    );
                    return (
                        refTable === stuTable &&
                        refCol?.expr?.column?.expr?.value ===
                            stuCol?.expr?.column?.expr?.value
                    );
                }
                return false;
            });

            if (!found) {
                allSame = false;
                if (!firstMismatch) firstMismatch = 'Incorrect columns selected.';
            }
        });

        return [allSame, firstMismatch];
    }

    // =========================================================================
    // Legacy compatibility: hasUnsupportedQueryStructure
    // =========================================================================

    /**
     * @deprecated Use hasDerivedTableSubquery() directly.
     * Kept so external callers compiled against the old API continue to work.
     */
    public hasUnsupportedQueryStructure(ast: AST): boolean {
        return this.hasDerivedTableSubquery(ast);
    }
}
