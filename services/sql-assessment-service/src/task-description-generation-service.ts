import { AST } from "node-sql-parser";
import { GenerationOptions, GptOptions } from "./interfaces";
import { LLMTaskDescriptionGenerationEngine } from "./llm-task-description-generation-engine";
import { TemplateTaskDescriptionGenerationEngine } from "./template-task-description-generation-engine";

export class TaskDescriptionGenerationService {

    templateTaskDescriptionGenerationEngine: TemplateTaskDescriptionGenerationEngine
    llmTaskDescriptionGenerationEngine: LLMTaskDescriptionGenerationEngine;

    constructor(llmTaskDescriptionGenerationEngine: LLMTaskDescriptionGenerationEngine, templateTaskDescriptionGenerationEngine: TemplateTaskDescriptionGenerationEngine) {
        this.templateTaskDescriptionGenerationEngine = templateTaskDescriptionGenerationEngine;
        this.llmTaskDescriptionGenerationEngine = llmTaskDescriptionGenerationEngine;
    }

    public async generateTaskFromQuery(genearationType: GenerationOptions, query: string, queryAST: AST, schema: string, databaseKey: string, isSelfJoin?: boolean, option?: GptOptions): Promise<string> {

        switch (genearationType) {
            case "template":
                return this.templateTaskDescriptionGenerationEngine.generateTaskFromQuery(queryAST, schema);

            case "llm":
                if (!option) {
                    throw Error("Undefined GPT configuration");
                }
                return await this.llmTaskDescriptionGenerationEngine.generateTaskFromQuery(query, databaseKey, option, isSelfJoin);

            case "hybrid":
                let templateDescription = this.templateTaskDescriptionGenerationEngine.generateTaskFromQuery(queryAST, schema);
                return await this.llmTaskDescriptionGenerationEngine.generateNLGTaskFromTemplateTask(query, templateDescription, databaseKey);

            default:
                return "Unknown generationType selected.";
        }
    }
}