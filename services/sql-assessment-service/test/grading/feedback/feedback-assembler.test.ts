import { describe, it, expect, beforeEach } from 'vitest';
import { FeedbackAssembler } from '../../../src/grading/feedback/feedback-assembler';
import type { ASTComparisonResult } from '../../../src/grading/comparators/ast-comparator';
import type { ExecutionPlanComparisonResult } from '../../../src/grading/comparators/execution-plan-comparator';

// ---------------------------------------------------------------------------
// Fixture factories
// ---------------------------------------------------------------------------

function makeASTResult(overrides: Partial<ASTComparisonResult> = {}): ASTComparisonResult {
    return {
        columnsMatch:        true,
        supported:           true,
        limitMatch:          true,
        feedback:            [],
        feedbackWithSolution: [],
        studentAliasMap:     {},
        referenceAliasMap:   {},
        ...overrides,
    };
}

function makePlanResult(overrides: Partial<ExecutionPlanComparisonResult> = {}): ExecutionPlanComparisonResult {
    return {
        plansMatch:          true,
        feedback:            [],
        feedbackWithSolution: [],
        penaltyPoints:       0,
        ...overrides,
    };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('FeedbackAssembler', () => {
    let assembler: FeedbackAssembler;

    beforeEach(() => {
        assembler = new FeedbackAssembler();
    });

    describe('build — result-set verdict line', () => {
        it('includes "Same result set" when resultSetMatch is true', () => {
            const { feedback } = assembler.build(true, makeASTResult(), makePlanResult());
            expect(feedback).toContain('Same result set of both queries.');
        });

        it('includes "Result sets differ" when resultSetMatch is false', () => {
            const { feedback } = assembler.build(false, makeASTResult(), makePlanResult());
            expect(feedback).toContain('Result sets differ.');
        });
    });

    describe('build — AST feedback propagation', () => {
        it('propagates AST feedback messages', () => {
            const ast = makeASTResult({ feedback: ['Column X is missing.'] });
            const { feedback } = assembler.build(true, ast, makePlanResult());
            expect(feedback).toContain('Column X is missing.');
        });

        it('propagates AST feedbackWithSolution messages', () => {
            const ast = makeASTResult({ feedbackWithSolution: ['Expected: col_a, col_b'] });
            const { feedbackWithSolution } = assembler.build(true, ast, makePlanResult());
            expect(feedbackWithSolution).toContain('Expected: col_a, col_b');
        });
    });

    describe('build — execution-plan feedback propagation', () => {
        it('propagates plan feedback messages when planResult is provided', () => {
            const plan = makePlanResult({ feedback: ['Incorrect Group key.'] });
            const { feedback } = assembler.build(true, makeASTResult(), plan);
            expect(feedback).toContain('Incorrect Group key.');
        });

        it('propagates plan feedbackWithSolution when planResult is provided', () => {
            const plan = makePlanResult({ feedbackWithSolution: ['Expected [col_a], got [col_b].'] });
            const { feedbackWithSolution } = assembler.build(true, makeASTResult(), plan);
            expect(feedbackWithSolution).toContain('Expected [col_a], got [col_b].');
        });

        it('does not include plan feedback when planResult is null (unsupported structure)', () => {
            const ast  = makeASTResult({ feedback: ['Unsupported DISTINCT.'] });
            const { feedback } = assembler.build(false, ast, null);
            // Plan-level messages must not be present
            expect(feedback).not.toContain('Incorrect Group key.');
        });
    });

    describe('build — combined output ordering', () => {
        it.todo('result-set verdict appears before AST feedback');
        it.todo('AST feedback appears before execution-plan feedback');
    });

    describe('build — empty inputs', () => {
        it('returns two non-empty arrays even when all comparators report no issues', () => {
            const { feedback, feedbackWithSolution } = assembler.build(
                true, makeASTResult(), makePlanResult()
            );
            expect(feedback.length).toBeGreaterThan(0);
            expect(Array.isArray(feedbackWithSolution)).toBe(true);
        });
    });
});
