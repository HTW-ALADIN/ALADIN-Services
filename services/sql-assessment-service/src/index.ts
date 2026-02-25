import 'reflect-metadata';
import { DatabaseAnalyzer } from './database-analyzer';
import { SQLQueryGradingService } from './query-grading-service';
import { DatabaseController } from './database-controller';
import { registerControllers, startRestApi } from './rest-api';
import { TaskGenerationController } from './task-generation-controller';
import { TemplateTaskDescriptionGenerationEngine } from './template-task-description-generation-engine';
import { LLMTaskDescriptionGenerationEngine } from './llm-task-description-generation-engine';
import { GradingController } from './grading-controller';
import { SQLQueryGenerationService } from './sql-query-generation-service';
import { SelectQueryGenerationDirector } from './select-query-generation-director';
import { TaskDescriptionGenerationService } from './task-description-generation-service';


let databaseAnalyzer: DatabaseAnalyzer = new DatabaseAnalyzer();
let connectionController = new DatabaseController(databaseAnalyzer);

let selectQueryGenerator = new SQLQueryGenerationService(new SelectQueryGenerationDirector());
let templateTaskDescriptionGenerationEngine = new TemplateTaskDescriptionGenerationEngine();
let llmTaskDescrionGenerationEngine = new LLMTaskDescriptionGenerationEngine();
let taskDescriptionGenerationService = new TaskDescriptionGenerationService(llmTaskDescrionGenerationEngine, templateTaskDescriptionGenerationEngine);
let taskGenerationController = new TaskGenerationController(selectQueryGenerator, taskDescriptionGenerationService);
let queryGradingService = new SQLQueryGradingService();
let gradingController = new GradingController(queryGradingService, taskDescriptionGenerationService);
registerControllers(connectionController, taskGenerationController, gradingController);
startRestApi();
