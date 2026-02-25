import { describe, it, expect, beforeEach } from 'vitest';
import { GradeCalculator, GradeInputs } from '../../../src/grading/grading/grade-calculator';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function inputs(overrides: Partial<GradeInputs> = {}): GradeInputs {
    return {
        fullGrade:         7,
        resultSetMatch:    true,
        columnsMatch:      true,
        planPenaltyPoints: 0,
        ...overrides,
    };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('GradeCalculator', () => {
    let calculator: GradeCalculator;

    beforeEach(() => {
        calculator = new GradeCalculator();
    });

    describe('calculate — perfect score', () => {
        it('returns fullGrade when all comparisons pass', () => {
            expect(calculator.calculate(inputs())).toBe(7);
        });
    });

    describe('calculate — individual deductions', () => {
        it('deducts 1 point when result sets differ', () => {
            expect(calculator.calculate(inputs({ resultSetMatch: false }))).toBe(6);
        });

        it('deducts 1 point when column lists differ', () => {
            expect(calculator.calculate(inputs({ columnsMatch: false }))).toBe(6);
        });

        it('deducts planPenaltyPoints from the grade', () => {
            expect(calculator.calculate(inputs({ planPenaltyPoints: 3 }))).toBe(4);
        });
    });

    describe('calculate — combined deductions', () => {
        it('deducts 2 points when both result sets and columns differ', () => {
            expect(calculator.calculate(inputs({ resultSetMatch: false, columnsMatch: false }))).toBe(5);
        });

        it('deducts all three when result sets, columns, and plan all differ', () => {
            expect(calculator.calculate(inputs({
                resultSetMatch:    false,
                columnsMatch:      false,
                planPenaltyPoints: 2,
            }))).toBe(3);
        });
    });

    describe('calculate — grade floor', () => {
        it('clamps grade at 0 when total deductions exceed fullGrade', () => {
            expect(calculator.calculate(inputs({
                resultSetMatch:    false,
                columnsMatch:      false,
                planPenaltyPoints: 10,
            }))).toBe(0);
        });

        it('never returns a negative grade', () => {
            expect(calculator.calculate(inputs({
                fullGrade:         1,
                resultSetMatch:    false,
                columnsMatch:      false,
                planPenaltyPoints: 5,
            }))).toBeGreaterThanOrEqual(0);
        });
    });

    describe('calculate — custom fullGrade', () => {
        it('respects a custom fullGrade value', () => {
            expect(calculator.calculate(inputs({ fullGrade: 10 }))).toBe(10);
        });

        it('deducts from the custom fullGrade', () => {
            expect(calculator.calculate(inputs({
                fullGrade:      10,
                columnsMatch:   false,
                planPenaltyPoints: 1,
            }))).toBe(8);
        });
    });
});
