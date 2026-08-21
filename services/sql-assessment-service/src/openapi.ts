import swaggerJsdoc from 'swagger-jsdoc';
import path from 'path';

/**
 * @openapi
 * components:
 *   schemas:
 *
 *     # -----------------------------------------------------------------------
 *     # Shared / primitive schemas
 *     # -----------------------------------------------------------------------
 *
 *     ErrorResponse:
 *       type: object
 *       required:
 *         - message
 *       properties:
 *         message:
 *           type: string
 *           description: Human-readable error description (localised).
 *           example: Unable to connect to the database.
 *         code:
 *           type: string
 *           description: Optional machine-readable error code.
 *           example: NON_SELECT
 *
 *     MessageResponse:
 *       type: object
 *       required:
 *         - message
 *       properties:
 *         message:
 *           type: string
 *           example: Database successfully analyzed.
 *
 *     # -----------------------------------------------------------------------
 *     # Connection info (mirrors typeorm PostgresConnectionOptions subset)
 *     # -----------------------------------------------------------------------
 *
 *     PostgresConnectionInfo:
 *       type: object
 *       required:
 *         - type
 *         - host
 *         - port
 *         - username
 *         - password
 *         - database
 *         - schema
 *       properties:
 *         type:
 *           type: string
 *           enum: [postgres]
 *           example: postgres
 *         host:
 *           type: string
 *           example: localhost
 *         port:
 *           type: number
 *           example: 5432
 *         username:
 *           type: string
 *           example: myuser
 *         password:
 *           type: string
 *           example: mypassword
 *         database:
 *           type: string
 *           example: mydb
 *         schema:
 *           type: string
 *           example: public
 *
 *     PGliteConnectionInfo:
 *       type: object
 *       description: >
 *         Connection info for an in-process PGlite database. The instance is
 *         registered out-of-band (via /analyze-database or a configured
 *         init-SQL file) and referenced afterwards by databaseId.
 *       required:
 *         - type
 *         - databaseId
 *       properties:
 *         type:
 *           type: string
 *           enum: [pglite]
 *           example: pglite
 *         databaseId:
 *           type: string
 *           description: Stable identifier of a registered PGlite instance.
 *           example: my-database
 *         sqlContent:
 *           type: string
 *           description: >
 *             SQL used to (re-)initialise the instance. Required by
 *             /analyze-database; optional on downstream calls, which reuse the
 *             already-registered instance.
 *
 *     ConnectionInfo:
 *       description: >
 *         Backend-agnostic connection info. Discriminated on the `type` field:
 *         `postgres` selects PostgresConnectionInfo, `pglite` selects
 *         PGliteConnectionInfo.
 *       oneOf:
 *         - $ref: '#/components/schemas/PostgresConnectionInfo'
 *         - $ref: '#/components/schemas/PGliteConnectionInfo'
 *       discriminator:
 *         propertyName: type
 *         mapping:
 *           postgres: '#/components/schemas/PostgresConnectionInfo'
 *           pglite: '#/components/schemas/PGliteConnectionInfo'
 *
 *     AliasMap:
 *       type: object
 *       description: >
 *         Optional human-readable display names for tables and columns.
 *         Supplied at database analysis time; used in generated descriptions.
 *       properties:
 *         tables:
 *           type: object
 *           additionalProperties:
 *             type: string
 *           example:
 *             orders: "Customer Orders"
 *         columns:
 *           type: object
 *           additionalProperties:
 *             type: object
 *             additionalProperties:
 *               type: string
 *           example:
 *             orders:
 *               order_date: "Order Date"
 *
 *     LlmGatewayConfig:
 *       type: object
 *       description: >
 *         Per-request LLM gateway connection details. When present, LLM-based
 *         description variants are generated via the supplied gateway instead
 *         of the template engine. The service never reads gateway location or
 *         credentials from its own environment; the apiKey is sent as an
 *         Authorization: Bearer header on every outbound call and is never
 *         logged.
 *       required:
 *         - endpoint
 *         - apiKey
 *       properties:
 *         endpoint:
 *           type: string
 *           description: >
 *             Base URL of an llm-gateway-service-compatible API. The client
 *             appends /generate.
 *           example: http://llm-gateway:8080
 *         apiKey:
 *           type: string
 *           description: Bearer token sent to the gateway on every outbound call.
 *           example: sk-...
 *         provider:
 *           type: string
 *           description: >
 *             Provider id override (e.g. "openai"). Defaults to "openai" when
 *             omitted.
 *           example: openai
 *         model:
 *           type: string
 *           description: >
 *             Model id override (e.g. "gpt-4o-mini"). Defaults to
 *             "gpt-4o-mini" when omitted.
 *           example: gpt-4o-mini
 *         customProvider:
 *           type: object
 *           description: >
 *             Optional inline OpenAI-compatible endpoint. When present, the
 *             gateway routes the request directly to baseUrl with the given
 *             apiKey, bypassing its own provider registration — so callers can
 *             use any provider without pre-registering it.
 *           required:
 *             - baseUrl
 *             - apiKey
 *           properties:
 *             baseUrl:
 *               type: string
 *               description: >
 *                 Base URL of an OpenAI-compatible API. The gateway appends
 *                 /chat/completions.
 *               example: https://api.openai.com/v1
 *             apiKey:
 *               type: string
 *               description: Provider-specific token for the custom endpoint.
 *               example: sk-provider-key
 *
 *     # -----------------------------------------------------------------------
 *     # Database endpoint schemas
 *     # -----------------------------------------------------------------------
 *
 *     AnalyzeDatabaseRequest:
 *       type: object
 *       required:
 *         - connectionInfo
 *       properties:
 *         connectionInfo:
 *           $ref: '#/components/schemas/ConnectionInfo'
 *         aliasMap:
 *           $ref: '#/components/schemas/AliasMap'
 *         languageCode:
 *           type: string
 *           description: BCP 47 language code for error messages. Defaults to "en".
 *           example: en
 *
 *     # -----------------------------------------------------------------------
 *     # Generation endpoint schemas
 *     # -----------------------------------------------------------------------
 *
 *     TaskConfiguration:
 *       type: object
 *       required:
 *         - aggregation
 *         - orderby
 *         - joinDepth
 *         - joinTypes
 *         - predicateCount
 *         - groupby
 *         - having
 *         - columnCount
 *         - operationTypes
 *       properties:
 *         aggregation:
 *           type: boolean
 *           description: Whether to include aggregate functions (COUNT, SUM, …).
 *         orderby:
 *           type: boolean
 *           description: Whether to include an ORDER BY clause.
 *         joinDepth:
 *           type: integer
 *           minimum: 0
 *           description: Number of JOIN operations to include.
 *         joinTypes:
 *           type: array
 *           items:
 *             type: string
 *             enum: [INNER JOIN, LEFT JOIN, RIGHT JOIN, FULL JOIN, CROSS JOIN, SELF JOIN]
 *         predicateCount:
 *           type: integer
 *           minimum: 0
 *           description: Number of WHERE predicates to generate.
 *         groupby:
 *           type: boolean
 *           description: Whether to include a GROUP BY clause.
 *         having:
 *           type: boolean
 *           description: Whether to include a HAVING clause (requires groupby=true).
 *         columnCount:
 *           type: integer
 *           minimum: 1
 *           description: Number of columns to select.
 *         operationTypes:
 *           type: array
 *           items:
 *             type: string
 *           description: Predicate operation types to use (e.g. "=", ">", "LIKE").
 *
 *     GenerateTaskRequest:
 *       type: object
 *       required:
 *         - connectionInfo
 *         - taskConfiguration
 *       properties:
 *         connectionInfo:
 *           $ref: '#/components/schemas/ConnectionInfo'
 *         taskConfiguration:
 *           $ref: '#/components/schemas/TaskConfiguration'
 *         languageCode:
 *           type: string
 *           example: en
 *         llmGateway:
 *           $ref: '#/components/schemas/LlmGatewayConfig'
 *
 *     TaskResponse:
 *       type: object
 *       required:
 *         - query
 *         - templateBasedDescription
 *         - gptEntityRelationshipDescription
 *         - gptSchemaBasedDescription
 *         - hybridDescription
 *       properties:
 *         query:
 *           type: string
 *           description: The generated SQL SELECT query.
 *           example: SELECT name FROM customers WHERE age > 30
 *         templateBasedDescription:
 *           type: string
 *           description: AST-template-generated natural-language description.
 *         gptEntityRelationshipDescription:
 *           type: string
 *           description: LLM-generated description using entity-relationship context (multi-step).
 *         gptSchemaBasedDescription:
 *           type: string
 *           description: LLM-generated description using the raw schema (default GPT option).
 *         hybridDescription:
 *           type: string
 *           description: Hybrid (template + LLM) natural-language description.
 *         gptCreativeDescription:
 *           type: string
 *           description: LLM-generated creative description (temperature 0.7). May be absent.
 *
 *     # -----------------------------------------------------------------------
 *     # Description endpoint schemas
 *     # -----------------------------------------------------------------------
 *
 *     DescriptionRequest:
 *       type: object
 *       required:
 *         - connectionInfo
 *         - query
 *       properties:
 *         connectionInfo:
 *           $ref: '#/components/schemas/ConnectionInfo'
 *         query:
 *           type: string
 *           description: Raw SQL query string to describe.
 *           example: SELECT name FROM customers WHERE age > 30
 *         isSelfJoin:
 *           type: boolean
 *           description: Whether the query involves a self-join. Defaults to false.
 *         languageCode:
 *           type: string
 *           description: BCP 47 language code for the generated description. Defaults to "en".
 *           example: en
 *         llmGateway:
 *           $ref: '#/components/schemas/LlmGatewayConfig'
 *
 *     DescriptionResponse:
 *       type: object
 *       required:
 *         - description
 *         - languageCode
 *       properties:
 *         description:
 *           type: string
 *           description: Natural-language description of the SQL query.
 *           example: Retrieve the names of all customers older than 30.
 *         languageCode:
 *           type: string
 *           description: The language code of the returned description.
 *           example: en
 *
 *     # -----------------------------------------------------------------------
 *     # Grading endpoint schemas
 *     # -----------------------------------------------------------------------
 *
 *     ReferenceQuery:
 *       type: object
 *       required:
 *         - query
 *       properties:
 *         query:
 *           type: string
 *           description: The SQL string of the reference (model) solution.
 *           example: SELECT name FROM customers WHERE age > 30
 *         stats:
 *           type: object
 *           description: Optional prior-cohort statistics for this reference query.
 *           properties:
 *             timesFoundByStudents:
 *               type: integer
 *             averageAttemptsToFind:
 *               type: number
 *
 *     GradeRequest:
 *       type: object
 *       required:
 *         - connectionInfo
 *         - gradingRequest
 *       properties:
 *         connectionInfo:
 *           $ref: '#/components/schemas/ConnectionInfo'
 *         gradingRequest:
 *           type: object
 *           required:
 *             - studentQuery
 *           properties:
 *             referenceQuery:
 *               type: string
 *               deprecated: true
 *               description: >
 *                 Single reference query string. Deprecated — prefer referenceQueries.
 *             referenceQueries:
 *               type: array
 *               items:
 *                 $ref: '#/components/schemas/ReferenceQuery'
 *               description: >
 *                 One or more reference solutions. The closest one is selected automatically.
 *             studentQuery:
 *               type: string
 *               description: The student SQL query to grade.
 *         languageCode:
 *           type: string
 *           example: en
 *         generationStrategy:
 *           type: string
 *           enum: [template, llm, hybrid]
 *           description: >
 *             Which description generation strategy to use when the student
 *             query is not equivalent. Defaults to hybrid / llm depending on
 *             query type support.
 *         gptOption:
 *           type: string
 *           enum: [default, creative, multi-step]
 *           description: GPT option when generationStrategy is llm. Defaults to default.
 *         llmGateway:
 *           $ref: '#/components/schemas/LlmGatewayConfig'
 *
 *     GradeResponse:
 *       type: object
 *       required:
 *         - comparisonResult
 *       properties:
 *         comparisonResult:
 *           type: object
 *           properties:
 *             grade:
 *               type: number
 *               description: Numeric grade awarded (0–100).
 *               example: 75
 *             equivalent:
 *               type: boolean
 *               description: Whether the student query is semantically equivalent to the reference.
 *             supportedQueryType:
 *               type: boolean
 *               description: Whether the query type is supported for structural comparison.
 *             feedbackDetails:
 *               type: object
 *               description: Detailed per-dimension feedback assembled by the feedback assembler.
 *
 *     ComparisonRequest:
 *       type: object
 *       required:
 *         - connectionInfo
 *         - studentQuery
 *       properties:
 *         connectionInfo:
 *           $ref: '#/components/schemas/ConnectionInfo'
 *         referenceQuery:
 *           type: string
 *           deprecated: true
 *           description: Single reference query. Deprecated — prefer referenceQueries.
 *         referenceQueries:
 *           type: array
 *           items:
 *             $ref: '#/components/schemas/ReferenceQuery'
 *         studentQuery:
 *           type: string
 *         languageCode:
 *           type: string
 *           example: en
 *
 *     ResultSetComparisonResponse:
 *       type: object
 *       required:
 *         - match
 *       properties:
 *         match:
 *           type: boolean
 *           description: Whether both queries return identical result sets.
 *         feedback:
 *           type: object
 *           description: Optional verdict feedback when the result sets differ.
 *
 *     ASTComparisonResponse:
 *       type: object
 *       required:
 *         - columnsMatch
 *         - supported
 *       properties:
 *         columnsMatch:
 *           type: boolean
 *           description: Whether the SELECT column lists of both queries match.
 *         supported:
 *           type: boolean
 *           description: >
 *             Whether the query uses a supported structure. When false, only
 *             result-set equivalence is meaningful for grading.
 *         feedback:
 *           type: object
 *           description: Per-element AST feedback.
 *
 *     ExecutionPlanComparisonResponse:
 *       type: object
 *       required:
 *         - plansMatch
 *         - penaltyPoints
 *       properties:
 *         plansMatch:
 *           type: boolean
 *           description: >
 *             Whether all compared plan elements (WHERE, GROUP BY, ORDER BY, JOIN) match.
 *         feedback:
 *           type: object
 *           description: Per-element execution-plan feedback.
 *         penaltyPoints:
 *           type: number
 *           description: Grade points deducted based on plan differences.
 *
 *     # -----------------------------------------------------------------------
 *     # Query execution schemas
 *     # -----------------------------------------------------------------------
 *
 *     QueryExecuteRequest:
 *       type: object
 *       required:
 *         - connectionInfo
 *         - query
 *       properties:
 *         connectionInfo:
 *           $ref: '#/components/schemas/ConnectionInfo'
 *         query:
 *           type: string
 *           description: Raw SQL SELECT query to execute.
 *           example: SELECT * FROM customers LIMIT 10
 *         languageCode:
 *           type: string
 *           example: en
 *
 *     QueryExecutionResult:
 *       type: object
 *       required:
 *         - rows
 *         - rowCount
 *       properties:
 *         rows:
 *           type: array
 *           items:
 *             type: object
 *             additionalProperties: true
 *           description: Rows returned by the query.
 *         rowCount:
 *           type: integer
 *           description: Number of rows returned.
 *           example: 42
 */

const swaggerDefinition: swaggerJsdoc.Options['definition'] = {
  openapi: '3.0.3',
  info: {
    title: 'SQL Assessment Service API',
    version: '1.0.0',
    description:
      'REST API for SQL exercise generation, student query grading, ' +
      'and natural-language description of SQL queries in an educational context.',
    contact: {
      name: 'ALADIN Project',
    },
  },
  tags: [
    {name: 'Database', description: 'Register and analyze PostgreSQL databases'},
    {name: 'Generation', description: 'Generate SQL tasks and descriptions'},
    {name: 'Description', description: 'Generate natural-language descriptions of SQL queries'},
    {name: 'Grading', description: 'Grade and compare student SQL queries'},
    {name: 'Query', description: 'Execute raw SQL queries'},
  ],
};

const options: swaggerJsdoc.Options = {
  definition: swaggerDefinition,
  // Scan both the compiled JS (runtime) and the TS source (for generate-openapi CLI)
  apis: [
    path.join(__dirname, 'openapi.{js,ts}'),
    path.join(__dirname, '**', '*.{js,ts}'),
  ],
};

let _cachedSpec: object | null = null;

/**
 * Returns the generated OpenAPI specification object.
 * The result is memoised after the first call.
 */
export function getSwaggerSpec(): object {
  if (!_cachedSpec) {
    _cachedSpec = swaggerJsdoc(options);
  }
  return _cachedSpec;
}
