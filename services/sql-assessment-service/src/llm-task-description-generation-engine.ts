import dotenv from 'dotenv';
import { ChatOpenAI } from '@langchain/openai';
import { SystemMessagePromptTemplate } from '@langchain/core/prompts';
import { databaseMetadata, selfJoinDatabaseMetadata } from './internal-memory';
import { SystemMessage } from '@langchain/core/messages';
import { GptOptions, IParsedTable } from './interfaces';
import { RunnableLambda, RunnableSequence } from '@langchain/core/runnables';

export class LLMTaskDescriptionGenerationEngine {
	constructor() {
		dotenv.config();

		this.openai = new ChatOpenAI({
			openAIApiKey: process.env.API_KEY,
			modelName: 'gpt-4o-mini',
			temperature: 0,
		});
		this.creativeOpeneai = new ChatOpenAI({
			openAIApiKey: process.env.API_KEY,
			modelName: 'gpt-4o-mini',
			temperature: 0.7,
		});
	}

	private readonly openai;
	private readonly creativeOpeneai;
	private readonly joinExamples =
		'INNER_JOIN: Returns only the rows where there is a match in both tables based on the specified condition, LEFT_JOIN:  Returns all rows from the left table, and matching rows from the right table, RIGHT_JOIN: Returns all rows from the right table, and matching rows from the left table, FULL_JOIN:Combines all rows from both tables, including matching rows based on the condition, while unmatched rows from either table are filled with NULL values for the missing side., CROSS_JOIN:  Creates every possible combination of rows between two tables, where each row from the first table is paired with every row from the second table, regardless of any condition.';
	private readonly instructions = `You are a helpful assistant that creates a human-readable task for a given Postgresql SQL query, where the solution of the task should be equal to the result of the given query. Use a direct and action-oriented writing style. The task should be a continuous text that represent the semantic meaning of what the query is trying to achieve. Do not use technical wordings and naming. Include the database name. If GROUP BY is included in the query, clearly state the group by statement by actually calling it group by. Always describe the join type (postgres sql based) in a human readable way, without literally mentioning the join type and without literally mentioning the matching join condition. When the SQL query contains multiple joins, always create one sentence describing the join type for each join. When the query includes a self join (join within the same table), describe it in a human readable way without actually using the alias name. Do not leave out or summarize any of the expression values used in the Where and Having conditions, even if they are long values like paths or urls.
`;
	private readonly exampleTasks = [
		{
			query:
				'SELECT AVG(products.unit_price) FROM products INNER JOIN order_details ON products.product_id = order_details.product_id;',
			task: 'Calculate the average price of sold products. Combine data from the Products table and the Orders table to determine this.',
		},
		{
			query:
				'SELECT employees.name, employees.address, benefits.benefit_name FROM employees LEFT JOIN employee_benefits ON employees.employee_id = benefits.employee_id;',
			task: 'Retrieve the names, addresses, and benefit details of all employees. Combine information from the Employees table and the Employee Benefits table, ensuring that all employees are included, even those who do not have any associated benefits.',
		},
		{
			query:
				"SELECT COUNT(e1.gender), MAX(e2.hire_date) FROM northwind.employee_territories FULL JOIN northwind.employees AS e1 ON employee_territories.employee_id = e1.employee_id FULL JOIN northwind.employees AS e2 ON e1.reports_to = e2.employee_id WHERE e1.home_phone BETWEEN '(71) 555-4444' AND '(206) 555-1189' OR e2.home_phone IN ('(71) 555-4444', '(71) 555-7773', '(206) 555-8122', '(206) 555-9857') GROUP BY e2.address",
			task: "Count the gender of employees and find the latest hire date of supervisors. Combine all records from the employee additional information table and the employee table to connect employees with their supervisors. Ensure all records from both reportees and supervisors are included. Focus only on reportees with a home phone number in the range '(71) 555-4444' to '(206) 555-1189' or whose supervisors' home phone numbers are one of '(71) 555-4444', '(71) 555-7773', '(206) 555-8122', '(206) 555-9857'. Group the results by the supervisor's address.",
		},
	];

	async generateTaskFromQuery(
		query: string,
		databaseKey: string,
		option: GptOptions,
		isSelfJoin?: boolean,
	): Promise<string> {
		switch (option) {
			case 'creative':
				return await this.generateTaskFromQueryCreative(
					query,
					databaseKey,
					isSelfJoin,
				);

			case 'multi-step':
				return await this.generateTaskFromQueryMultiStep(
					query,
					databaseKey,
					isSelfJoin,
				);

			case 'default':
				return await this.generateTaskFromQueryNotCreative(
					query,
					databaseKey,
					isSelfJoin,
				);

			default:
				return 'Unknown option selected.';
		}
	}

	private async generateTaskFromQueryMultiStep(
		query: string,
		databaseKey: string,
		isSelfJoin?: boolean,
	): Promise<string> {
		let tables;
		if (!isSelfJoin) {
			tables = [];
			let selfTables = selfJoinDatabaseMetadata.get(databaseKey);
			let otherTables = databaseMetadata.get(databaseKey);
			selfTables
				? tables.push(...selfTables)
				: otherTables
					? tables.push(...otherTables)
					: [];
		} else
			tables = isSelfJoin
				? selfJoinDatabaseMetadata.get(databaseKey)
				: databaseMetadata.get(databaseKey);

		if (!tables) throw new Error('Error in accessing database tables.');
		let queryParts = this.splitSQLQuery(query);

		const sequence = RunnableSequence.from([
			new RunnableLambda({
				func: async (input: { tables: IParsedTable[] }) => {
					const entityPrompt = SystemMessagePromptTemplate.fromTemplate([
						new SystemMessage(`You are a database expert.`),
						new SystemMessage(`Given the following database schema: {tables}.`),
						new SystemMessage(
							`Describe entity relationships based on an entity relationship diagram.`,
						),
					]).pipe(this.openai);

					const entityResponse = await entityPrompt.invoke(input);
					return { entityDescription: entityResponse.content };
				},
			}),

			...queryParts.map(
				(part) =>
					new RunnableLambda({
						func: async (input: {
							entityDescription: string;
							queryPartResults?: string[];
						}) => {
							const queryPartPrompt = SystemMessagePromptTemplate.fromTemplate([
								new SystemMessage(`You are a database and PostgreSQL expert.`),
								new SystemMessage(
									`Given the following query part: {query_part}`,
								),
								new SystemMessage(
									`Describe the semantic meaning of that query part based on the provided entity relationships: {entity_description}.`,
								),
							]).pipe(this.openai);

							const response = await queryPartPrompt.invoke({
								query_part: part,
								entity_description: input.entityDescription,
							});

							const updatedResults = [
								...(input.queryPartResults || []),
								response.content,
							];
							return { ...input, queryPartResults: updatedResults };
						},
					}),
			),

			new RunnableLambda({
				func: async (input: { queryPartResults: string[] }) => {
					const taskPrompt = SystemMessagePromptTemplate.fromTemplate([
						new SystemMessage(`You are a SQL expert.`),
						new SystemMessage(
							`Based on the following semantic descriptions of query parts: {query_part_results}, create natural-language question that describes the requested data. The question should include all required information to formulate a query that returns the requested data. Return only the question.`,
						),
					]).pipe(this.openai);

					const response = await taskPrompt.invoke({
						query_part_results: input.queryPartResults.join('\n'),
					});

					return response.content;
				},
			}),
		]);

		try {
			const response = await sequence.invoke({ tables });

			console.log('Generated Task Description:', response);
			return response as string;
		} catch (error) {
			console.error(error);
			throw new Error('Error in generating task description using GPT.');
		}
	}

	// async generateTaskFromQuery_v1_creative(query: string): Promise<string> {
	//   const systemMessage = new SystemMessage(this.instructions);
	//   const querySystemMessage = new SystemMessage(`This is the query: ${query}`);

	//   const messages = [
	//     systemMessage, querySystemMessage
	//   ]

	//   try {
	//     const response = await this.creativeOpeneai.invoke(messages);
	//     return response.content as string;
	//   } catch (error) {
	//     console.error(error);
	//     throw Error('Error in generation task description using GPT.')
	//   }
	// }

	private async generateTaskFromQueryCreative(
		query: string,
		databaseKey: string,
		isSelfJoin?: boolean,
	): Promise<string> {
		let tables = isSelfJoin
			? selfJoinDatabaseMetadata.get(databaseKey)
			: databaseMetadata.get(databaseKey);

		const systemMessage = new SystemMessage(
			`${this.instructions} As additional information you can find the parsed tables that describe the schema of the database.`,
		);
		const querySystemMessage = new SystemMessage(`This is the query: ${query}`);
		const schemaSystemMessage = new SystemMessage(
			`This is the schema: ${tables}`,
		);
		const exampleTasks = new SystemMessage(
			`These are examples for queries and corresponding tasks: ${this.exampleTasks}`,
		);
		const messages = [systemMessage, querySystemMessage, schemaSystemMessage];

		try {
			const response = await this.creativeOpeneai.invoke(messages);
			return response.content as string;
		} catch (error) {
			console.error(error);
			throw Error('Error in generation task description using GPT.');
		}
	}

	private async generateTaskFromQueryNotCreative(
		query: string,
		databaseKey: string,
		isSelfJoin: boolean | undefined,
	): Promise<string> {
		let tables;
		if (!isSelfJoin) {
			tables = [];
			let selfTables = selfJoinDatabaseMetadata.get(databaseKey);
			let otherTables = databaseMetadata.get(databaseKey);
			selfTables
				? tables.push(...selfTables)
				: otherTables
					? tables.push(...otherTables)
					: [];
		} else
			tables = isSelfJoin
				? selfJoinDatabaseMetadata.get(databaseKey)
				: databaseMetadata.get(databaseKey);

		const systemMessage = new SystemMessage(
			`${this.instructions} As additional information you can find the parsed tables that describe the schema of the database.`,
		);
		const querySystemMessage = new SystemMessage(`This is the query: ${query}`);
		const schemaSystemMessage = new SystemMessage(
			`This is the schema: ${tables}`,
		);
		const exampleTasks = new SystemMessage(
			`These are examples for queries and corresponding tasks: ${this.exampleTasks}`,
		);
		const messages = [systemMessage, querySystemMessage, schemaSystemMessage];

		try {
			const response = await this.openai.invoke(messages);
			return response.content as string;
		} catch (error) {
			console.error(error);
			throw Error('Error in generation task description using GPT.');
		}
	}

	async generateNLGTaskFromTemplateTask(
		query: string,
		taskDescription: string,
		databaseKey: string,
		isSelfJoin?: boolean,
	): Promise<string> {
		let tables;
		if (!isSelfJoin) {
			tables = [];
			let selfTables = selfJoinDatabaseMetadata.get(databaseKey);
			let otherTables = databaseMetadata.get(databaseKey);
			selfTables
				? tables.push(...selfTables)
				: otherTables
					? tables.push(...otherTables)
					: [];
		} else
			tables = isSelfJoin
				? selfJoinDatabaseMetadata.get(databaseKey)
				: databaseMetadata.get(databaseKey);

		const systemMessage = new SystemMessage(
			"You are a helpful assistant specializing in making PostgreSQL tasks more human-readable. Your goal is to rewrite the given task description into clear, continuous text that captures the core intent and semantic meaning of the SQL query. Maintain a direct, action-oriented style while preserving all original details. Ensure the improved task remains accurate, concise, and easy to understand, avoiding overly technical jargon. If values are null or not null, describe it in a human readable way (i.e. absent, undefined, any). When table aliases are used, describe them in a human-readable way based on their relationships, rather than mentioning the alias names. Describe aggregation functions (MIN, MAX, COUNT, etc.) in natural language, e.g. instead of saying 'MIN(Country)', describe it as 'the country that comes first alphabetically'. Do not leave out or summarize any of the expression values used in the Where and Having conditions, even if they are long values like paths or urls. You will be provided with the database schema and the query that solves the task for context.",
		);

		const querySystemMessage = new SystemMessage(`This is the query: ${query}`);
		const schemaSystemMessage = new SystemMessage(
			`This is the schema: ${tables}`,
		);
		const taskMessage = new SystemMessage(
			`This is the task description that you should improve: ${taskDescription}`,
		);

		const messages = [
			systemMessage,
			querySystemMessage,
			schemaSystemMessage,
			taskMessage,
		];

		try {
			const response = await this.openai.invoke(messages);
			return response.content as string;
		} catch (error) {
			console.error(error);
			throw Error('Error in generation task description using GPT.');
		}
	}

	private splitSQLQuery(query: string): string[] {
		const regex = /(SELECT|FROM|WHERE|GROUP BY|HAVING|ORDER BY)/gi;
		const parts = query
			.replace(/\n/g, ' ')
			.replace(/\s+/g, ' ')
			.split(regex)
			.map((part) => part.trim())
			.filter((part) => part !== '');

		const result: string[] = [];
		let currentSection = '';

		for (let i = 0; i < parts.length; i++) {
			if (
				['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY'].includes(
					parts[i].toUpperCase(),
				)
			) {
				if (currentSection) result.push(currentSection.trim());
				currentSection = parts[i];
			} else {
				currentSection += ' ' + parts[i];
			}
		}

		if (currentSection) result.push(currentSection.trim());

		return result;
	}
}
