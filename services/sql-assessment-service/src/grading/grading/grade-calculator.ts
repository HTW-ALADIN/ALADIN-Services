/**
 * Inputs to the grade calculation.
 *
 * Each boolean flag or numeric count maps to one grade-point deduction when
 * the condition indicates an error.
 */
export interface GradeInputs {
    /** Maximum achievable grade (default 7 in the current scoring model). */
    fullGrade: number;
    /** Whether the two queries return the same result set. */
    resultSetMatch: boolean;
    /** Whether the SELECT column lists match. */
    columnsMatch: boolean;
    /**
     * Number of execution-plan element mismatches (GROUP BY, HAVING, ORDER BY,
     * WHERE, JOIN).  Each mismatch costs one point.
     */
    planPenaltyPoints: number;
}

/**
 * Calculates the final numeric grade from the outputs of all comparison
 * strategies.
 *
 * Scoring model (mirrors the original SQLQueryGradingService logic):
 *  - Start at fullGrade.
 *  - −1 if result sets differ.
 *  - −1 if SELECT columns differ.
 *  - −planPenaltyPoints for each execution-plan element that differs.
 *  - Clamp at 0 (never negative).
 *
 * This is a pure function — no I/O, no state.
 */
export class GradeCalculator {

    public calculate(inputs: GradeInputs): number {
        let grade = inputs.fullGrade;

        if (!inputs.resultSetMatch)  grade--;
        if (!inputs.columnsMatch)    grade--;
        grade -= inputs.planPenaltyPoints;

        return Math.max(grade, 0);
    }
}
