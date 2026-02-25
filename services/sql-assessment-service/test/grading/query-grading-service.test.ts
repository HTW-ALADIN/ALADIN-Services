import { describe, it, beforeAll, beforeEach, afterAll } from 'vitest';
import { IMemoryDb, IBackup } from 'pg-mem';
import { DataSource } from 'typeorm';
import { createTestDb } from '../helpers/pg-mem-factory';
import { SQLQueryGradingService } from '../../src/grading/query-grading-service';
import { ResultSetComparator } from '../../src/grading/result-set-comparator';
import { ASTComparator } from '../../src/grading/comparators/ast-comparator';
import { ExecutionPlanComparator } from '../../src/grading/comparators/execution-plan-comparator';
import { ExecutionPlanParser } from '../../src/grading/execution-plan-parser';
import { JoinComparator } from '../../src/grading/join-comparator';
import { FeedbackAssembler } from '../../src/grading/feedback/feedback-assembler';
import { GradeCalculator } from '../../src/grading/grading/grade-calculator';

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

let db: IMemoryDb;
let backup: IBackup;
let dataSource: DataSource;
let service: SQLQueryGradingService;

beforeAll(async () => {
    ({ db, backup, dataSource } = await createTestDb());
});

beforeEach(() => {
    backup.restore();
    const joinComparator = new JoinComparator();
    service = new SQLQueryGradingService(
        new ResultSetComparator(),
        new ASTComparator(joinComparator),
        new ExecutionPlanComparator(new ExecutionPlanParser(), joinComparator),
        new GradeCalculator(),
        new FeedbackAssembler()
    );
});

afterAll(async () => {
    await dataSource.destroy();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SQLQueryGradingService', () => {
    describe('gradeQuery', () => {
        it.todo('returns grade 0 for a non-executable student query');
        it.todo('returns grade 0 when the student query uses an unsupported SQL clause type');
        it.todo('returns the maximum grade when student and reference queries are identical');
        it.todo('deducts points for a wrong SELECT column list');
        it.todo('deducts points for a missing WHERE clause');
        it.todo('deducts points for incorrect JOIN structure');
        it.todo('deducts points for a missing GROUP BY');
        it.todo('deducts points for a missing HAVING clause');
        it.todo('deducts points for a missing ORDER BY');
        it.todo('returns equivalent=true when result sets match');
        it.todo('returns equivalent=false when result sets differ');
    });
});
