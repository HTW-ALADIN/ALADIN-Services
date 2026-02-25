import { Router, Request, Response } from "express";
import { GenerationOptions, GptOptions, IRequestTaskOptions, ITaskConfiguration, TaskResponse } from "./interfaces";
import { connectToDatabase, createQueryRunner, generateDatabaseKey, isDatabaseRegistered } from "./helper-functions";
import { DataSource, QueryFailedError } from "typeorm";
import { v4 as uuidv4 } from 'uuid';
import { PostgresConnectionOptions } from "typeorm/driver/postgres/PostgresConnectionOptions";
import { SQLQueryGenerationService } from "./sql-query-generation-service";
import { TaskDescriptionGenerationService } from "./task-description-generation-service";


export class TaskGenerationController {
    public router: Router;
    selectQueryGenerationService: SQLQueryGenerationService;
    taskDescriptionGenerationService: TaskDescriptionGenerationService;


    constructor(selectQueryGenerationService: SQLQueryGenerationService, taskDescriptionGenerationService: TaskDescriptionGenerationService) {
        this.selectQueryGenerationService = selectQueryGenerationService;
        this.taskDescriptionGenerationService = taskDescriptionGenerationService;
        this.router = Router();
        this.initializeRoutes();
    }

    private initializeRoutes(): void {
        this.router.get("/generate", (req: Request, resp: Response) => { this.generateTaskForRequest(req, resp) });
    }

    public async generateTaskForRequest(req: Request, res: Response): Promise<Response> {
        let taskRequest: IRequestTaskOptions;
        let connectionInfo: PostgresConnectionOptions;

        try {
            taskRequest = req.body;
        }
        catch (err: any) {
            console.log("Error in reading request", err);
            return res.status(400).json({ message: "Invalid request information" });
        }
        try {
            connectionInfo = taskRequest.connectionInfo;

        }
        catch (err: any) {
            console.log("Error in reading connection info", err);
            return res.status(400).json({ message: "Invalid connection information" });
        }


        if (!connectionInfo.host || !connectionInfo.port || !connectionInfo.username || !connectionInfo.schema) {
            return res.status(400).json({ message: "Invalid connection information" });
        }

        let databaseKey = generateDatabaseKey(connectionInfo.host, connectionInfo.port, connectionInfo.schema);
        if (!isDatabaseRegistered(databaseKey)) {
            return res.status(400).json({ message: "Unregistered database, please trigger database analysis." });
        }

        console.log("Received connection info:", connectionInfo);

        let taskContext: ITaskConfiguration = taskRequest.taskConfiguration;

        let dataSource = new DataSource(connectionInfo);

        let isConnected = await connectToDatabase(dataSource);

        if (isConnected) {
            let configValidation = this.selectQueryGenerationService.validateConfiguration(taskContext);
            if (!configValidation[0]) {
                return res.status(400).json({ message: configValidation[1] });
            }

            let query, ast;
            try {
                [query, ast] = await this.selectQueryGenerationService.generateContextBasedQuery(
                    taskContext,
                    databaseKey,
                    dataSource,
                    connectionInfo.schema
                );
                console.log(query);
            }
            catch (error) {
                console.log(error);
                dataSource.destroy();
                return res.status(500).json({ message: `Error in query generation, please try again. ${error}` });
            }

            let taskDescription, entityDescription, creativeDescription, schemaBasedDescription, semanticNGL;

            try {
                let isSelfJoin = taskContext.joinTypes.includes("SELF JOIN");
                taskDescription = await this.taskDescriptionGenerationService.generateTaskFromQuery(GenerationOptions.Template, query, ast, connectionInfo.schema, databaseKey, isSelfJoin);
                entityDescription = await this.taskDescriptionGenerationService.generateTaskFromQuery(GenerationOptions.LLM, query, ast, connectionInfo.schema, databaseKey, isSelfJoin, GptOptions.MultiStep);
                creativeDescription = await this.taskDescriptionGenerationService.generateTaskFromQuery(GenerationOptions.LLM, query, ast, connectionInfo.schema, databaseKey, isSelfJoin, GptOptions.Creative);
                schemaBasedDescription = await this.taskDescriptionGenerationService.generateTaskFromQuery(GenerationOptions.LLM, query, ast, connectionInfo.schema, databaseKey, isSelfJoin, GptOptions.Default);
                semanticNGL = await this.taskDescriptionGenerationService.generateTaskFromQuery(GenerationOptions.Hybrid, query, ast, connectionInfo.schema, databaseKey, isSelfJoin);
            }
            catch (error) {
                console.log("Error in task description generation", error);
                return res.status(500).json({ message: "Error in task description generation, please try again." });
            }

            let taskResponse: TaskResponse = { query: query, templateBasedDescription: taskDescription, gptEntityRelationshipDescription: entityDescription, gptSchemaBasedDescription: schemaBasedDescription, hybridDescription: semanticNGL, gptCreativeDescription: creativeDescription };
            dataSource.destroy();
            return res.status(200).json(taskResponse);
        }

        return res.status(400).json({ message: "Unable to connect to database" });
    }
}