import { describe, it, expect, beforeEach } from 'vitest';
import { FeedbackAssembler } from '../../../src/grading/feedback/feedback-assembler';
import type { ASTComparisonResult } from '../../../src/grading/comparators/ast-comparator';
import type { ExecutionPlanComparisonResult } from '../../../src/grading/comparators/execution-plan-comparator';

// ---------------------------------------------------------------------------
// Fixture factories
// ---------------------------------------------------------------------------

function makeASTResult(overrides: Partial<ASTComparisonResult> = {}): ASTComparisonResult {
    return {
        columnsMatch:      true,
        supported:         true,
        limitMatch:        true,
        ast:               {},
        studentAliasMap:   {},
        referenceAliasMap: {},
        ...overrides,
    };
}

function makePlanResult(overrides: Partial<ExecutionPlanComparisonResult> = {}): ExecutionPlanComparisonResult {
    return {
        plansMatch:    true,
        executionPlan: {},
        penaltyPoints: 0,
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

    describe('build — result-set verdict', () => {
        it('includes "Same result set" message when resultSetMatch is true', () => {
            const result = assembler.build(true, makeASTResult(), makePlanResult());
            expect(result.resultSet?.verdict.message).toBe('Same result set of both queries.');
        });

        it('includes "Result sets differ" message when resultSetMatch is false', () => {
            const result = assembler.build(false, makeASTResult(), makePlanResult());
            expect(result.resultSet?.verdict.message).toBe('Result sets differ.');
        });
    });

    describe('build — AST feedback propagation', () => {
        it('propagates AST columns feedback when columns do not match', () => {
            const ast = makeASTResult({
                ast: { columns: { message: 'The column selection is incorrect: Incorrect columns selected.' } },
            });
            const result = assembler.build(true, ast, makePlanResult());
            expect(result.ast?.columns?.message).toContain('column selection is incorrect');
        });

        it('propagates AST columns solution when present', () => {
            const ast = makeASTResult({
                ast: { columns: { message: 'The column selection is incorrect.', solution: 'Expected: col_a, col_b' } },
            });
            const result = assembler.build(true, ast, makePlanResult());
            expect(result.ast?.columns?.solution).toContain('col_a');
        });
    });

    describe('build — execution-plan feedback propagation', () => {
        it('propagates plan groupKey feedback when planResult is provided', () => {
            const plan = makePlanResult({ executionPlan: { groupKey: { message: 'Incorrect Group key.' } } });
            const result = assembler.build(true, makeASTResult(), plan);
            expect(result.executionPlan?.groupKey?.message).toBe('Incorrect Group key.');
        });

        it('propagates plan groupKey solution when planResult is provided', () => {
            const plan = makePlanResult({
                executionPlan: {
                    groupKey: { message: 'Incorrect Group key.', solution: 'Expected [col_a], got [col_b].' },
                },
            });
            const result = assembler.build(true, makeASTResult(), plan);
            expect(result.executionPlan?.groupKey?.solution).toContain('col_a');
        });

        it('does not include executionPlan when planResult is null (unsupported structure)', () => {
            const result = assembler.build(false, makeASTResult(), null);
            expect(result.executionPlan).toBeUndefined();
        });
    });

    describe('build — combined output ordering', () => {
        it.todo('result-set verdict appears before AST feedback');
        it.todo('AST feedback appears before execution-plan feedback');
    });

    describe('build — empty inputs', () => {
        it('returns an object with a resultSet key even when all comparators report no issues', () => {
            const result = assembler.build(true, makeASTResult(), makePlanResult());
            expect(result.resultSet).toBeDefined();
            expect(result.resultSet?.verdict).toBeDefined();
        });

        it('does not include ast key when there are no AST issues', () => {
            const result = assembler.build(true, makeASTResult(), makePlanResult());
            expect(result.ast).toBeUndefined();
        });

        it('does not include executionPlan key when there are no plan issues', () => {
            const result = assembler.build(true, makeASTResult(), makePlanResult());
            expect(result.executionPlan).toBeUndefined();
        });
    });
});
