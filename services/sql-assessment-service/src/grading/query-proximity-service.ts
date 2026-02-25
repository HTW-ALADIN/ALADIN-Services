import { AST, Parser, Select } from 'node-sql-parser';
import { ReferenceQuery } from '../shared/interfaces/http';

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * The heuristic used to measure distance between two SQL queries.
 *
 * | Value              | Description                                                         |
 * |--------------------|---------------------------------------------------------------------|
 * | `ASTEditDistance`  | Levenshtein edit-distance over the normalised AST token sequence.   |
 *                        Alias-independent: `p.product_name` and                           |
 *                        `products.product_name` produce identical tokens.                 |
 * | `TokenLevenshtein` | Levenshtein edit-distance over the raw SQL token stream (split on   |
 *                        whitespace/punctuation).  Faster but alias-sensitive.             |
 */
export enum ProximityHeuristic {
    ASTEditDistance  = 'ast-edit-distance',
    TokenLevenshtein = 'token-levenshtein',
}

/** The result returned by {@link QueryProximityService.selectClosest}. */
export interface ProximityResult {
    /** The reference query that is closest to the student query. */
    referenceQuery: ReferenceQuery;
    /** The distance score (lower = closer). */
    distance: number;
    /** The heuristic that was used to compute the distance. */
    heuristic: ProximityHeuristic;
    /** Zero-based index of the selected entry in the original `candidates` array. */
    candidateIndex: number;
}

// ---------------------------------------------------------------------------
// QueryProximityService
// ---------------------------------------------------------------------------

/**
 * Selects the reference query that is structurally closest to a student query
 * from a collection of candidates.
 *
 * Supports multiple pluggable heuristics via {@link ProximityHeuristic}.  The
 * default heuristic is {@link ProximityHeuristic.ASTEditDistance}, which
 * serialises each query into a normalised AST token sequence and computes the
 * Levenshtein edit distance between the two sequences.
 *
 * ### Why AST-token edit distance?
 *
 * Raw SQL string distance is sensitive to irrelevant formatting differences
 * (whitespace, alias names, casing).  By first parsing the query into an AST
 * and then extracting a normalised token sequence we obtain a distance measure
 * that:
 *  - is case-insensitive (tokens are lowercased),
 *  - is alias-insensitive (aliases are resolved to the real table name),
 *  - treats structurally similar queries as close even when their literal text
 *    differs (e.g. `SELECT p.name FROM products p` ≈ `SELECT products.name FROM products`).
 *
 * ### Tie-breaking
 *
 * When two candidates share the minimum distance, the one that appears earlier
 * in the `candidates` array is returned.  Callers may therefore order the
 * array by preference (e.g. most-frequently-found solution first) and
 * tie-breaking will naturally favour it.
 */
export class QueryProximityService {

    private readonly parser = new Parser();

    // =========================================================================
    // Public interface
    // =========================================================================

    /**
     * Selects the {@link ReferenceQuery} from `candidates` that is structurally
     * closest to `studentQuery` according to the given `heuristic`.
     *
     * @param studentQuery  Raw SQL string submitted by the student.
     * @param candidates    Non-empty array of reference solutions.
     * @param heuristic     Distance metric to use (default: `ASTEditDistance`).
     * @returns             The closest candidate and metadata.
     * @throws              When `candidates` is empty.
     */
    public selectClosest(
        studentQuery: string,
        candidates:   ReferenceQuery[],
        heuristic:    ProximityHeuristic = ProximityHeuristic.ASTEditDistance
    ): ProximityResult {
        if (candidates.length === 0) {
            throw new Error('candidates must contain at least one reference query');
        }

        if (candidates.length === 1) {
            return {
                referenceQuery: candidates[0],
                distance:       0,
                heuristic,
                candidateIndex: 0,
            };
        }

        const distanceFn = this.resolveDistanceFn(heuristic);

        let bestIndex    = 0;
        let bestDistance = Infinity;

        for (let i = 0; i < candidates.length; i++) {
            const d = distanceFn(studentQuery, candidates[i].query);
            if (d < bestDistance) {
                bestDistance = d;
                bestIndex    = i;
            }
            // Tie → keep earlier index (no update needed: strict `<` above)
        }

        return {
            referenceQuery: candidates[bestIndex],
            distance:       bestDistance,
            heuristic,
            candidateIndex: bestIndex,
        };
    }

    /**
     * Computes the AST-token edit distance between two SQL strings.
     *
     * Parses both queries, extracts a normalised token sequence (see
     * {@link tokeniseAST}), then returns the Levenshtein distance between the
     * two sequences.
     *
     * On parse failure for either query a fallback to
     * {@link tokenLevenshteinDistance} is applied automatically.
     */
    public astEditDistance(a: string, b: string): number {
        try {
            const astA = this.parseOne(a);
            const astB = this.parseOne(b);
            const tokA = this.tokeniseAST(astA);
            const tokB = this.tokeniseAST(astB);
            return this.levenshtein(tokA, tokB);
        } catch {
            // Graceful degradation: one of the queries is unparseable
            return this.tokenLevenshteinDistance(a, b);
        }
    }

    /**
     * Computes the token-level Levenshtein distance between two raw SQL strings.
     *
     * Splits on whitespace and common SQL punctuation so that minor formatting
     * differences (extra spaces, line-breaks) do not inflate the distance.
     */
    public tokenLevenshteinDistance(a: string, b: string): number {
        const tokA = this.tokeniseSQLString(a);
        const tokB = this.tokeniseSQLString(b);
        return this.levenshtein(tokA, tokB);
    }

    // =========================================================================
    // AST tokenisation
    // =========================================================================

    /**
     * Converts a parsed AST into a flat, normalised token array.
     *
     * The token sequence is designed to be:
     *  - **alias-independent**: aliases are resolved to the real table name via
     *    the same alias-map logic used by {@link ASTComparator}.
     *  - **clause-ordered**: tokens are emitted in a fixed clause order
     *    (SELECT → FROM/JOIN → WHERE → GROUP BY → HAVING → ORDER BY → LIMIT)
     *    so that two semantically equivalent queries with different physical
     *    orderings produce the same sequence.
     *  - **case-normalised**: all tokens are lower-cased.
     *
     * Non-SELECT ASTs fall back to a best-effort serialisation of the raw AST
     * via JSON (keys are stable, values normalised).
     */
    public tokeniseAST(ast: AST): string[] {
        if (ast.type !== 'select') {
            return this.tokeniseGenericAST(ast);
        }

        const select     = ast as Select;
        const aliasMap   = this.buildAliasMap(select.from as any[]);
        const tokens: string[] = [];

        // ── SELECT columns ──────────────────────────────────────────────────
        tokens.push('select');
        // node-sql-parser v5 always emits a `distinct` key; only treat it as
        // DISTINCT when the nested `.type` is actually the string 'DISTINCT'.
        const distinctNode = (select as any).distinct;
        if (distinctNode && typeof distinctNode === 'object' && distinctNode.type === 'DISTINCT') {
            tokens.push('distinct');
        }

        const cols = select.columns;
        if (Array.isArray(cols)) {
            // Sort columns so order differences don't inflate distance
            const colTokens = cols.map(c => this.tokeniseColumn(c, aliasMap));
            colTokens.sort();
            colTokens.forEach(ct => tokens.push(...ct));
        } else {
            tokens.push('*');
        }

        // ── FROM / JOIN ──────────────────────────────────────────────────────
        if (Array.isArray(select.from)) {
            tokens.push('from');
            for (const entry of select.from as any[]) {
                if (entry?.expr?.ast?.type === 'select') {
                    // Derived table subquery — recurse
                    tokens.push('subquery');
                    tokens.push(...this.tokeniseAST(entry.expr.ast));
                } else if (entry?.table) {
                    tokens.push(String(entry.table).toLowerCase());
                    if (entry.join) tokens.push(String(entry.join).toLowerCase());
                }
            }
        }

        // ── WHERE ────────────────────────────────────────────────────────────
        if (select.where) {
            tokens.push('where');
            tokens.push(...this.tokeniseExpr(select.where, aliasMap));
        }

        // ── GROUP BY ─────────────────────────────────────────────────────────
        // node-sql-parser v5 represents GROUP BY as either a plain array
        // (older behaviour) or { columns: [...] } (current behaviour).
        const groupbyRaw = (select as any).groupby;
        const groupbyArr: any[] | null =
            Array.isArray(groupbyRaw)
                ? groupbyRaw
                : Array.isArray(groupbyRaw?.columns)
                    ? groupbyRaw.columns
                    : null;
        if (groupbyArr && groupbyArr.length > 0) {
            tokens.push('group_by');
            const gbTokens = groupbyArr.map(
                (e: any) => this.tokeniseExpr(e, aliasMap).join('.')
            );
            gbTokens.sort();
            gbTokens.forEach(t => tokens.push(t));
        }

        // ── HAVING ───────────────────────────────────────────────────────────
        if ((select as any).having) {
            tokens.push('having');
            tokens.push(...this.tokeniseExpr((select as any).having, aliasMap));
        }

        // ── ORDER BY ─────────────────────────────────────────────────────────
        if (Array.isArray((select as any).orderby)) {
            tokens.push('order_by');
            for (const ob of (select as any).orderby as any[]) {
                tokens.push(...this.tokeniseExpr(ob.expr, aliasMap));
                if (ob.type) tokens.push(String(ob.type).toLowerCase());
            }
        }

        // ── LIMIT / OFFSET ───────────────────────────────────────────────────
        const limitNode = (select as any).limit;
        if (limitNode?.value?.length) {
            tokens.push('limit');
            tokens.push(String(limitNode.value[0]?.value ?? ''));
            if (limitNode.value.length > 1) {
                tokens.push('offset');
                tokens.push(String(limitNode.value[1]?.value ?? ''));
            }
        }

        return tokens.filter(t => t !== '');
    }

    // =========================================================================
    // Private helpers
    // =========================================================================

    private resolveDistanceFn(
        heuristic: ProximityHeuristic
    ): (a: string, b: string) => number {
        switch (heuristic) {
            case ProximityHeuristic.ASTEditDistance:
                return (a, b) => this.astEditDistance(a, b);
            case ProximityHeuristic.TokenLevenshtein:
                return (a, b) => this.tokenLevenshteinDistance(a, b);
        }
    }

    private parseOne(sql: string): AST {
        const result = this.parser.astify(sql, { database: 'postgresql' });
        return Array.isArray(result) ? result[0] : result;
    }

    // -------------------------------------------------------------------------
    // Alias map  (mirrors ASTComparator.buildAliasMap — kept local to avoid a
    //             circular dependency between services)
    // -------------------------------------------------------------------------

    private buildAliasMap(from: any[]): Record<string, string> {
        const map: Record<string, string> = {};
        if (!from) return map;

        let prevTable = '';
        let prevAlias = '';

        for (const entry of from) {
            const alias = entry?.as;
            if (alias) {
                const table      = entry.table ?? '';
                const isSelfJoin = table === prevTable && table !== '';
                if (isSelfJoin) {
                    const suffix = entry.join === 'RIGHT JOIN' ? 0 : 1;
                    map[alias]    = `${table}${suffix}`;
                    map[prevAlias] = `${table}${1 - suffix}`;
                } else {
                    map[alias] = table;
                }
                prevTable = table;
                prevAlias = alias;
            }
        }

        return map;
    }

    private normaliseTable(name: string | null | undefined, aliasMap: Record<string, string>): string {
        if (!name) return '';
        return (aliasMap[name] ?? name).toLowerCase();
    }

    // -------------------------------------------------------------------------
    // Column tokenisation
    // -------------------------------------------------------------------------

    private tokeniseColumn(col: any, aliasMap: Record<string, string>): string[] {
        const expr = col?.expr;
        if (!expr) return [];

        if (expr.type === 'aggr_func') {
            const fn    = String(expr.name ?? '').toLowerCase();
            const table = this.normaliseTable(expr.args?.expr?.table, aliasMap);
            const colName = String(
                expr.args?.expr?.column?.expr?.value ?? expr.args?.expr?.column ?? '*'
            ).toLowerCase();
            return [fn, table ? `${table}.${colName}` : colName];
        }

        if (expr.type === 'column_ref') {
            const table   = this.normaliseTable(expr.table, aliasMap);
            const colName = String(
                expr.column?.expr?.value ?? expr.column ?? ''
            ).toLowerCase();
            return [table ? `${table}.${colName}` : colName];
        }

        // star / expression
        if (expr.type === 'star') return ['*'];

        return this.tokeniseExpr(expr, aliasMap);
    }

    // -------------------------------------------------------------------------
    // Generic expression tokenisation
    // -------------------------------------------------------------------------

    private tokeniseExpr(node: any, aliasMap: Record<string, string>): string[] {
        if (!node || typeof node !== 'object') {
            return node != null ? [String(node).toLowerCase()] : [];
        }

        if (Array.isArray(node)) {
            return node.flatMap((n: any) => this.tokeniseExpr(n, aliasMap));
        }

        switch (node.type) {
            case 'column_ref': {
                const table   = this.normaliseTable(node.table, aliasMap);
                const colName = String(
                    node.column?.expr?.value ?? node.column ?? ''
                ).toLowerCase();
                return [table ? `${table}.${colName}` : colName];
            }
            case 'number':
                return [String(node.value)];
            case 'string':
            case 'single_quote_string':
                return [String(node.value).toLowerCase()];
            case 'aggr_func': {
                const fn      = String(node.name ?? '').toLowerCase();
                const argToks = this.tokeniseExpr(node.args?.expr, aliasMap);
                return [fn, ...argToks];
            }
            case 'function': {
                const fn      = String(node.name?.name?.[0]?.value ?? node.name ?? '').toLowerCase();
                const argToks = (node.args?.value ?? []).flatMap(
                    (a: any) => this.tokeniseExpr(a, aliasMap)
                );
                return [fn, ...argToks];
            }
            case 'binary_expr': {
                const left  = this.tokeniseExpr(node.left,  aliasMap);
                const right = this.tokeniseExpr(node.right, aliasMap);
                return [...left, String(node.operator ?? '').toLowerCase(), ...right];
            }
            case 'unary_expr': {
                const inner = this.tokeniseExpr(node.expr, aliasMap);
                return [String(node.operator ?? '').toLowerCase(), ...inner];
            }
            case 'select':
                return ['subquery', ...this.tokeniseAST(node)];
            default:
                // Fallback: walk all values
                return Object.values(node).flatMap(
                    v => (v && typeof v === 'object') ? this.tokeniseExpr(v, aliasMap) : []
                );
        }
    }

    // -------------------------------------------------------------------------
    // Fallback tokenisation for non-SELECT ASTs
    // -------------------------------------------------------------------------

    private tokeniseGenericAST(ast: AST): string[] {
        const json   = JSON.stringify(ast);
        const tokens = this.tokeniseSQLString(json);
        return tokens;
    }

    // -------------------------------------------------------------------------
    // Raw SQL string tokenisation
    // -------------------------------------------------------------------------

    /**
     * Splits a raw SQL string into a token array by splitting on whitespace
     * and common SQL punctuation characters, then lower-casing each token.
     */
    public tokeniseSQLString(sql: string): string[] {
        return sql
            .split(/[\s,;()\[\]{}'"]+/)
            .map(t => t.toLowerCase())
            .filter(t => t.length > 0);
    }

    // -------------------------------------------------------------------------
    // Levenshtein edit distance (generic sequence)
    // -------------------------------------------------------------------------

    /**
     * Computes the Levenshtein edit distance between two string arrays.
     *
     * Uses the standard O(n·m) DP table.  Substitution cost is 1.
     * For typical SQL queries (< 50 tokens each) this is fast.
     */
    public levenshtein(a: string[], b: string[]): number {
        const m = a.length;
        const n = b.length;

        // Allocate a (m+1) × (n+1) matrix
        const dp: number[][] = Array.from({ length: m + 1 }, (_, i) =>
            Array.from({ length: n + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0))
        );

        for (let i = 1; i <= m; i++) {
            for (let j = 1; j <= n; j++) {
                if (a[i - 1] === b[j - 1]) {
                    dp[i][j] = dp[i - 1][j - 1];
                } else {
                    dp[i][j] = 1 + Math.min(
                        dp[i - 1][j],     // deletion
                        dp[i][j - 1],     // insertion
                        dp[i - 1][j - 1]  // substitution
                    );
                }
            }
        }

        return dp[m][n];
    }
}
