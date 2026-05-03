import 'reflect-metadata';
import { DatabaseAnalyzer } from './database/database-analyzer';
import { DatabaseController } from './database/database-controller';
import { DatabaseService } from './database/database-service';
import { SQLQueryGradingService } from './grading/query-grading-service';
import { GradingController } from './grading/grading-controller';
import { ResultSetComparator } from './grading/result-set-comparator';
import { ASTComparator } from './grading/comparators/ast-comparator';
import { ExecutionPlanComparator } from './grading/comparators/execution-plan-comparator';
import { ExecutionPlanParser } from './grading/execution-plan-parser';
import { JoinComparator } from './grading/join-comparator';
import { FeedbackAssembler } from './grading/feedback/feedback-assembler';
import { GradeCalculator } from './grading/grading/grade-calculator';
import { SQLQueryGenerationService } from './generation/query/sql-query-generation-service';
import { SelectQueryGenerationDirector } from './generation/query/select-query-generation-director';
import { TemplateTaskDescriptionGenerationEngine } from './generation/description/template-task-description-generation-engine';
import { LLMTaskDescriptionGenerationEngine } from './generation/description/llm-task-description-generation-engine';
import { TaskDescriptionGenerationService } from './generation/description/task-description-generation-service';
import { TaskGenerationController } from './generation/task-generation-controller';
import { DescriptionController } from './generation/description/description-controller';
import { QueryExecutionController } from './query/query-execution-controller';
import { QueryExecutionService } from './query/query-execution-service';

export interface CreateControllersOptions {
	/** Path to a SQL file used as PGlite initialisation SQL when `sqlContent`
	 *  is not provided in the request.  Falls back to `PGLITE_INIT_SQL_FILE`
	 *  environment variable when omitted. */
	pgliteInitSqlFile?: string;
}

export function createControllers(options: CreateControllersOptions = {}) {
	const pgliteInitSqlFile =
		options.pgliteInitSqlFile ?? process.env.PGLITE_INIT_SQL_FILE;

	const databaseAnalyzer = new DatabaseAnalyzer();
	const databaseService = new DatabaseService(
		databaseAnalyzer,
		pgliteInitSqlFile,
	);
	const connectionController = new DatabaseController(
		databaseAnalyzer,
		databaseService,
	);

	const selectQueryGenerator = new SQLQueryGenerationService(
		new SelectQueryGenerationDirector(),
	);
	const templateTaskDescriptionGenerationEngine =
		new TemplateTaskDescriptionGenerationEngine();
	const llmTaskDescriptionGenerationEngine = process.env.OPENAI_API_KEY
		? new LLMTaskDescriptionGenerationEngine()
		: undefined;
	const taskDescriptionGenerationService = new TaskDescriptionGenerationService(
		llmTaskDescriptionGenerationEngine,
		templateTaskDescriptionGenerationEngine,
	);
	const taskGenerationController = new TaskGenerationController(
		selectQueryGenerator,
		taskDescriptionGenerationService,
		databaseService,
	);

	// ── Grading dependencies ──────────────────────────────────────────────────
	const joinComparator = new JoinComparator();
	const resultSetComparator = new ResultSetComparator();
	const astComparator = new ASTComparator(joinComparator);
	const executionPlanComparator = new ExecutionPlanComparator(
		new ExecutionPlanParser(),
		joinComparator,
	);
	const gradeCalculator = new GradeCalculator();
	const feedbackAssembler = new FeedbackAssembler();

	const queryGradingService = new SQLQueryGradingService(
		resultSetComparator,
		astComparator,
		executionPlanComparator,
		gradeCalculator,
		feedbackAssembler,
	);
	const gradingController = new GradingController(
		queryGradingService,
		taskDescriptionGenerationService,
		resultSetComparator,
		astComparator,
		executionPlanComparator,
		undefined,
		databaseService,
	);

	const descriptionController = new DescriptionController(
		taskDescriptionGenerationService,
		databaseService,
	);
	const queryExecutionService = new QueryExecutionService();
	const queryExecutionController = new QueryExecutionController(
		queryExecutionService,
		databaseService,
	);

	return {
		connectionController,
		taskGenerationController,
		gradingController,
		descriptionController,
		queryExecutionController,
	};
}
