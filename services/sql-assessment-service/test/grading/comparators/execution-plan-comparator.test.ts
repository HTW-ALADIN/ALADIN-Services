import { describe, it, beforeAll, beforeEach, afterAll } from 'vitest';
import { IMemoryDb, IBackup } from 'pg-mem';
import { DataSource } from 'typeorm';
import { createTestDb } from '../../helpers/pg-mem-factory';
import { ExecutionPlanComparator } from '../../../src/grading/comparators/execution-plan-comparator';
import { ExecutionPlanParser } from '../../../src/grading/execution-plan-parser';
import { JoinComparator } from '../../../src/grading/join-comparator';

// ---------------------------------------------------------------------------
// pg-mem setup (execution-plan comparator needs a live DataSource for EXPLAIN)
// ---------------------------------------------------------------------------

let db: IMemoryDb;
let backup: IBackup;
let dataSource: DataSource;
let comparator: ExecutionPlanComparator;

beforeAll(async () => {
    ({ db, backup, dataSource } = await createTestDb());
});

beforeEach(() => {
    backup.restore();
    comparator = new ExecutionPlanComparator(new ExecutionPlanParser(), new JoinComparator());
});

afterAll(async () => {
    await dataSource.destroy();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ExecutionPlanComparator', () => {
    describe('compare — matching plans', () => {
        it.todo('returns plansMatch=true and penaltyPoints=0 for identical queries');
        it.todo('returns plansMatch=true when GROUP BY columns match');
        it.todo('returns plansMatch=true when ORDER BY columns match');
        it.todo('returns plansMatch=true when WHERE filters match');
    });

    describe('compare — mismatched plans', () => {
        it.todo('returns penaltyPoints=1 when GROUP BY columns differ');
        it.todo('returns penaltyPoints=1 when ORDER BY columns differ');
        it.todo('returns penaltyPoints=1 when WHERE filters differ');
        it.todo('returns penaltyPoints=1 when HAVING filters differ');
        it.todo('returns penaltyPoints=1 when JOIN structure differs');
        it.todo('accumulates multiple penalty points for multiple mismatches');
        it.todo('includes descriptive feedback for each mismatch');
        it.todo('includes feedbackWithSolution showing expected vs actual values');
    });

    describe('compare — join detection', () => {
        it.todo('flags an unexpected JOIN in the student query');
        it.todo('flags a missing JOIN in the student query');
    });

    describe('compare — error handling', () => {
        it.todo('throws when execution plans cannot be retrieved from the database');
    });
});
