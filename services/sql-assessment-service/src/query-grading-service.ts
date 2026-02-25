import { DataSource, QueryFailedError, QueryRunner } from "typeorm";
import { databaseMetadata, selfJoinDatabaseMetadata } from "./internal-memory";
import { AST, Binary, Column, ColumnRefItem, Join, Parser, Select } from "node-sql-parser";
import {
	ComparisonResult,
	IParsedExecutionPlan,
	IParsedTable,
	JoinStatement,
	QueryPlan,
	QueryPlanKeys,
	QueryPlanNode,
} from "./interfaces";

export class SQLQueryGradingService {
	private readonly fullGrade = 7;
	constructor() {}

	public async gradeQuery(
		referenceQuery: string,
		studentQuery: string,
		dataSource: DataSource,
		databaseKey: string
	): Promise<ComparisonResult> {
		let grade = this.fullGrade;
		let feedback: string[] = [];
		let feedbackWithSolution: string[] = [];
		studentQuery = this.removeSemicolon(studentQuery);
		referenceQuery = this.removeSemicolon(referenceQuery);
		const parser = new Parser();

		let isQueryExecutable = await this.isQueryExecutable(studentQuery, dataSource);
		feedback.push(...isQueryExecutable[1]);
		if (!isQueryExecutable[0])
			return {
				grade: 0,
				feedback: feedback,
				feedbackWithSolution: feedbackWithSolution,
				equivelant: false,
				supportedQueryType: false,
			};

		const sameResultSet = await this.dynamicComparisionOfResultSets(referenceQuery, studentQuery, dataSource);
		feedback.push(...sameResultSet[1]);
		sameResultSet[0] ? feedback.push("Same result set of both queries") : feedback.push("Result sets differ");

		let studentAST = parser.astify(studentQuery, { database: "postgresql" });
		let referenceAST = parser.astify(referenceQuery, {
			database: "postgresql",
		});

		if (Array.isArray(studentAST) || Array.isArray(referenceAST)) {
			feedback.push("AST array not supported");
			grade = sameResultSet[0] ? this.fullGrade : 0;
			return {
				grade: grade,
				feedback: feedback,
				feedbackWithSolution: feedbackWithSolution,
				equivelant: grade == this.fullGrade,
				supportedQueryType: false,
			};
		}

		if (!(studentAST && referenceAST)) {
			feedback.push("AST parsing failed");
			grade = sameResultSet[0] ? this.fullGrade : 0;
			return {
				grade: grade,
				feedback: feedback,
				feedbackWithSolution: feedbackWithSolution,
				equivelant: grade == this.fullGrade,
				supportedQueryType: false,
			};
		}

		studentAST = studentAST as AST;
		referenceAST = referenceAST as AST;

		if (studentAST.type != referenceAST.type) {
			feedback.push(`Incorrect SQL clause, the task requires a clause of type: ${referenceAST.type}`);
			grade = sameResultSet[0] ? this.fullGrade : 0;
			return {
				grade: grade,
				feedback: feedback,
				feedbackWithSolution: feedbackWithSolution,
				equivelant: grade == this.fullGrade,
				supportedQueryType: false,
			};
		}

		if (this.hasUnsupportedQueryStructure(studentAST, true)) {
			grade = sameResultSet[0] ? this.fullGrade : 0;
			return {
				grade: grade,
				feedback: feedback,
				feedbackWithSolution: feedbackWithSolution,
				equivelant: grade == this.fullGrade,
				supportedQueryType: false,
			};
		}

		let queryRunner = dataSource.createQueryRunner();

		let studentExecutionPlan = await queryRunner.query(`EXPLAIN (FORMAT JSON) ${studentQuery}`);
		let referenceExecutionPlan = await queryRunner.query(`EXPLAIN (FORMAT JSON) ${referenceQuery}`);

		queryRunner.release();
		if (!(studentExecutionPlan && referenceExecutionPlan)) {
			feedback.push("Unable to retreive execution plans");
			grade = sameResultSet[0] ? this.fullGrade : 0;
			return {
				grade: grade,
				feedback: feedback,
				feedbackWithSolution: feedbackWithSolution,
				equivelant: grade == this.fullGrade,
				supportedQueryType: false,
			};
		}

		if (!sameResultSet[0]) grade--;

		let areSameColumns = this.areSameColumnsSelected(studentAST, referenceAST);
		if (!areSameColumns[0]) grade--;
		feedback.push(...areSameColumns[1]);
		feedbackWithSolution.push(...areSameColumns[2]);
		let studentAliasMap = areSameColumns[3];
		let referenceAliasMap = areSameColumns[4];
		let parsedStudentExecutionPlan = this.parseExecutionPlan(studentExecutionPlan[0], studentAliasMap);
		let parsedReferenceExecutionPlan = this.parseExecutionPlan(referenceExecutionPlan[0], referenceAliasMap);

		if (!(parsedStudentExecutionPlan && parsedReferenceExecutionPlan)) {
			throw new Error("Unable to parse execution plans");
		}
		let comparisonResult = this.compareExecutionPlans(
			parsedStudentExecutionPlan,
			parsedReferenceExecutionPlan,
			studentAST,
			referenceAST,
			studentAliasMap,
			referenceAliasMap
		);

		grade = grade - comparisonResult[2];
		feedback.push(...comparisonResult[0]);
		feedbackWithSolution.push(...comparisonResult[1]);
		if (grade < 0) grade = 0;
		return {
			grade: grade,
			feedback: feedback,
			feedbackWithSolution: feedbackWithSolution,
			equivelant: grade == this.fullGrade,
			supportedQueryType: true,
		};
	}

	private removeSemicolon(str: string): string {
		return str.endsWith(";") ? str.slice(0, -1) : str;
	}

	private hasUnsupportedQueryStructure(studentAST: AST, isInitial: boolean) {
		return this.hasDistinct(studentAST) || this.hasSubquery(studentAST, true);
	}

	private hasSubquery(node: any, isInitial: boolean): boolean {
		if (!node || typeof node !== "object") return false;

		if (node.type === "select" && !isInitial) {
			return true;
		}

		const subqueryLocations = ["from", "where", "having", "orderby", "columns", "groupby", "limit", "with"];

		for (const location of subqueryLocations) {
			if (node[location]) {
				if (Array.isArray(node[location])) {
					for (const child of node[location]) {
						if (this.hasSubquery(child, false)) {
							return true;
						}
					}
				} else if (typeof node[location] === "object") {
					if (this.hasSubquery(node[location], false)) {
						return true;
					}
				}
			}
		}

		for (const key in node) {
			if (node.hasOwnProperty(key)) {
				const value = node[key];
				if (Array.isArray(value)) {
					for (const child of value) {
						if (this.hasSubquery(child, false)) return true;
					}
				} else if (typeof value === "object" && value !== null) {
					if (this.hasSubquery(value, false)) return true;
				}
			}
		}

		return false;
	}

	private hasDistinct(ast: any): boolean {
		if (ast.type === "select" && ast.distinct === true) {
			return true;
		}
		return false;
	}

	private buildASTAliasMap(from: any[]): Record<string, string> {
		let aliasMap: Record<string, string> = {};
		let previousJoinedTable = "";
		let previousJoinedAlias = "";
		if (from) {
			from.forEach((fromEntry: any) => {
				let alias = fromEntry.as;

				if (alias) {
					let table = fromEntry.table;
					let isSelfJoin = table == previousJoinedTable ? true : false;
					if (isSelfJoin) {
						let selfJoinTable = fromEntry.join == "RIGHT JOIN" ? `${table}0` : `${table}1`;
						aliasMap[alias] = selfJoinTable;
						aliasMap[previousJoinedAlias] =
							fromEntry.join == "RIGHT JOIN" ? `${previousJoinedTable}1` : `${previousJoinedTable}0`;
					} else aliasMap[alias] = table;
					previousJoinedAlias = alias;
					previousJoinedTable = table;
				}
			});
		}

		return aliasMap;
	}

	private areSameColumnsSelected(
		studentAST: AST,
		referenceAST: AST
	): [boolean, string[], string[], Record<string, string>, Record<string, string>] {
		let feedback: string[] = [];
		let feedbackWithSolution: string[] = [];
		let studentAliasMap = {},
			referenceAliasMap = {};

		switch (studentAST.type) {
			case "select": {
				let select = studentAST as Select;
				let referenceSelect = referenceAST as Select;
				let selectColumns;
				let referenceSelectColumns;

				if (!referenceSelect.columns || !select.columns) {
					feedback.push("Error: Not a select statement");
					return [false, feedback, feedbackWithSolution, studentAliasMap, referenceAliasMap];
				}

				selectColumns = select.columns;
				referenceSelectColumns = referenceSelect.columns;
				studentAliasMap = this.buildASTAliasMap(select.from as any[]);
				referenceAliasMap = this.buildASTAliasMap(referenceSelect.from as any[]);
				let [sameColumns, feedbackCol] = this.areColumnsEqual(
					selectColumns,
					referenceSelectColumns,
					studentAliasMap,
					referenceAliasMap
				);
				if (!sameColumns) {
					feedback.push(`The column selection is incorrect: ${feedbackCol}`);
					feedbackWithSolution.push("The task requires the selection of the following columns:");
					referenceSelectColumns.forEach((column) => {
						if (column?.expr?.type == "column_ref")
							feedbackWithSolution.push(`${column?.expr?.table}.${column?.expr?.column?.expr?.value}`);
						if (column?.expr?.type == "aggr_func")
							feedbackWithSolution.push(
								`${column?.expr?.name}(${column?.expr?.args?.expr?.table}.${column?.expr?.args?.expr?.column?.expr?.value})`
							);
					});
				}
				return [sameColumns, feedback, feedbackWithSolution, studentAliasMap, referenceAliasMap];
			}
			default: {
				return [false, feedback, feedbackWithSolution, studentAliasMap, referenceAliasMap];
			}
		}
	}

	private getAlias(tableName: string, aliasMap: Record<string, string>): string {
		let alias = Object.entries(aliasMap)
			.filter(([_, table]) => table === tableName)
			.map(([alias]) => alias);
		return alias.length > 0 ? alias[0] : tableName;
	}

	private areColumnsEqual(
		student: any[],
		reference: any[],
		studentAliasMap?: Record<string, string>,
		referenceAliasMap?: Record<string, string>
	): [boolean, string[]] {
		let feedback: string[] = [];
		if (student.length !== reference.length) {
			feedback.push("Incorrect number of columns selected.");
			return [false, feedback];
		}

		let areAllColumnsTheSame = true;
		reference.forEach((referenceColumn) => {
			let isIncluded = student.find((studentColumn: any) => {
				if (referenceColumn?.expr?.type == "aggr_func") {
					let referenceTable = this.normalizeTableName(referenceColumn?.expr?.args?.expr?.table, referenceAliasMap);
					let studentTable = this.normalizeTableName(studentColumn?.expr?.args?.expr?.table, studentAliasMap);
					return (
						referenceTable == studentTable &&
						studentColumn.expr?.name == referenceColumn.expr?.name &&
						studentColumn?.expr?.args?.expr?.column?.expr?.value ==
							referenceColumn?.expr?.args?.expr?.column?.expr?.value
					);
				} else if (referenceColumn?.expr?.type == "column_ref") {
					let referenceTable = this.normalizeTableName(referenceColumn?.expr?.table, referenceAliasMap);
					let studentTable = this.normalizeTableName(studentColumn?.expr?.table, studentAliasMap);
					return (
						referenceTable == studentTable &&
						referenceColumn?.expr?.column?.expr?.value == studentColumn?.expr?.column?.expr?.value
					);
				} else return false;
			});
			if (!isIncluded) {
				areAllColumnsTheSame = false;
				feedback.push("Incorrect columns selected.");
			}
		});
		return [areAllColumnsTheSame, feedback];
	}

	private isSameOrder(studentAST: AST, referenceAST: AST) {
		switch (studentAST.type) {
			case "select": {
				let select = studentAST as Select;
				let referenceSelect = referenceAST as Select;
				let referenceOrderType;
				let studentOrderType;

				if (!referenceSelect.orderby && select.orderby) {
					console.log("Incorrect use of Order By: Task does not require ordering");
					return false;
				}

				if (referenceSelect.orderby && !select.orderby) {
					console.log("Missing Order By: Task requires ordering");
					return false;
				}

				if (!referenceSelect.orderby && !select.orderby) {
					return true;
				}

				if (referenceSelect.orderby && referenceSelect.orderby.length > 0) {
					referenceOrderType = referenceSelect.orderby[0].type;
				}

				if (select.orderby && select.orderby.length > 0) {
					studentOrderType = select.orderby[0].type;
				}

				return studentOrderType == referenceOrderType ? true : false;
			}
		}
		return false;
	}

	private async isQueryExecutable(query: string, dataSource: DataSource): Promise<[boolean, string[]]> {
		let feedback: string[] = [];
		try {
			let queryRunner = dataSource.createQueryRunner();
			await queryRunner.query(query);
			queryRunner.release();
		} catch (error) {
			feedback.push("Query is not executable due to following syntax error:");
			feedback.push((error as QueryFailedError)?.driverError?.message);
			return [false, feedback];
		}
		return [true, feedback];
	}

	private async dynamicComparisionOfResultSets(
		referenceQuery: string,
		studentQuery: string,
		dataSource: DataSource
	): Promise<[boolean, string[]]> {
		let referenceResultSet, studentResultSet: any[];
		let comparisionResult: boolean;
		let feedback: string[] = [];
		try {
			let queryRunner = dataSource.createQueryRunner();
			referenceResultSet = await queryRunner.query(referenceQuery);
			studentResultSet = await queryRunner.query(studentQuery);
			comparisionResult = this.areResultsEqual(referenceResultSet, studentResultSet);
			queryRunner.release();
		} catch (error) {
			feedback.push("Unable to execute query comparision" + error);
			return [false, feedback];
		}

		return [comparisionResult, feedback];
	}

	private normalizeColumnOrderForRow(row: any): string {
		return JSON.stringify(
			Object.keys(row)
				.sort()
				.reduce(
					(acc, key) => {
						acc[key] = row[key];
						return acc;
					},
					{} as Record<string, any>
				)
		);
	}

	private areResultsEqual(referenceQuery: any[], studentQuery: any[]): boolean {
		if (referenceQuery.length !== studentQuery.length) return false; // Different row count

		for (let i = 0; i < referenceQuery.length; i++) {
			if (this.normalizeColumnOrderForRow(referenceQuery[i]) !== this.normalizeColumnOrderForRow(studentQuery[i])) {
				return false;
			}
		}

		return true;
	}

	private parseExecutionPlan(executionPlan: QueryPlan, aliasMap: Record<string, string>) {
		let parsedExecutionPlan: IParsedExecutionPlan = {};
		let queryPlan = executionPlan["QUERY PLAN"][0]["Plan"];
		parsedExecutionPlan.groupKey = this.extractKeyForNodeType(queryPlan, "Aggregate", "Group Key");
		parsedExecutionPlan.havingFilter = this.extractKeyForNodeType(queryPlan, "Aggregate", "Filter");
		parsedExecutionPlan.sortKey = this.extractKeyForNodeType(queryPlan, "Sort", "Sort Key");
		parsedExecutionPlan.whereFilter = this.extractAllKeysForNodeType(
			queryPlan,
			["Seq Scan", "Hash Join", "Bitmap Heap Scan", "Index Scan"],
			["Filter", "Join Filter", "Recheck Cond"]
		);
		parsedExecutionPlan.joinStatement = this.parseQueryPlanToJoinOrFromStatement(queryPlan, aliasMap);
		return parsedExecutionPlan;
	}

	private parseQueryPlanToJoinOrFromStatement(
		planNode: QueryPlanNode,
		aliasMap: Record<string, string>
	): JoinStatement | undefined {
		const nodeType = planNode["Node Type"];

		if (nodeType === "Seq Scan" || nodeType === "Bitmap Heap Scan") {
			const tableName =
				aliasMap[planNode["Alias"] || planNode["Relation Name"] || ""] || planNode["Relation Name"] || "";
			return { tableName };
		}

		if (nodeType === "Index Scan" || nodeType === "Index Only Scan") {
			const tableName =
				aliasMap[planNode["Alias"] || planNode["Relation Name"] || ""] || planNode["Relation Name"] || "";
			const condition = planNode["Index Cond"] || "";
			return { tableName: tableName, joinCondition: condition };
		}

		if (planNode["Join Type"]) {
			const joinType = planNode["Join Type"];
			const joinCondition = planNode["Hash Cond"] || planNode["Index Cond"] || "";

			const [outerPlan, innerPlan] = planNode["Plans"] || [];

			const outerJoinStatement = outerPlan
				? this.parseQueryPlanToJoinOrFromStatement(outerPlan, aliasMap)
				: { tableName: "" };
			const innerJoinStatement = innerPlan
				? this.parseQueryPlanToJoinOrFromStatement(innerPlan, aliasMap)
				: { tableName: "" };

			return outerPlan["Plans"]
				? {
						joinType,
						tableName: innerJoinStatement?.tableName || "",
						joinedTable: {
							tableName: outerJoinStatement?.tableName || "",
							joinType: outerJoinStatement?.joinType,
							joinedTable: outerJoinStatement?.joinedTable,
							joinCondition: outerJoinStatement?.joinCondition,
						},
						joinCondition: joinCondition ? joinCondition : innerJoinStatement?.joinCondition,
					}
				: {
						joinType,
						tableName: outerJoinStatement?.tableName || "",
						joinedTable: {
							tableName: innerJoinStatement?.tableName || "",
							joinType: innerJoinStatement?.joinType,
							joinedTable: innerJoinStatement?.joinedTable,
							joinCondition: innerJoinStatement?.joinCondition,
						},
						joinCondition: joinCondition ? joinCondition : outerJoinStatement?.joinCondition,
					};
		}

		let nestedPlans = planNode["Plans"];
		if (nestedPlans && nestedPlans.length > 0) {
			return this.parseQueryPlanToJoinOrFromStatement(nestedPlans[0], aliasMap);
		}

		return undefined;
	}

	private extractKeyForNodeType(plan: QueryPlanNode, nodeType: string, keyToExtract: QueryPlanKeys): any {
		if (plan["Node Type"] === nodeType) {
			return plan[keyToExtract];
		}

		if (plan.Plans) {
			for (const subPlan of plan.Plans) {
				const result = this.extractKeyForNodeType(subPlan, nodeType, keyToExtract);
				if (result !== undefined) {
					return result;
				}
			}
		}

		return undefined;
	}

	private extractAllKeysForNodeType(
		plan: QueryPlanNode,
		nodeType: string[],
		keysToExtract: QueryPlanKeys[],
		results: any[] = []
	): any[] {
		keysToExtract.forEach((keyToExtract) => {
			if (plan["Node Type"] && nodeType.includes(plan["Node Type"])) {
				if (plan[keyToExtract] !== undefined) {
					results.push(plan[keyToExtract]);
				}
			}

			if (plan.Plans) {
				for (const subPlan of plan.Plans) {
					this.extractAllKeysForNodeType(subPlan, nodeType, [keyToExtract], results);
				}
			}
		});

		return results;
	}

	private normalizeFilter(filter?: string, aliasMap?: Record<string, string>): string | undefined {
		if (!filter || !aliasMap) return filter;

		return filter.replace(/\b\w+\b/g, (match) => aliasMap[match] || match);
	}

	private parseSortKey(sortString: string): { sortKey?: string; sortDirection?: string } {
		const parts = sortString.trim().split(" ");
		if (parts.length > 1) {
			const sortKey = parts[0];
			const sortDirection = parts[1];
			return {
				sortKey,
				sortDirection,
			};
		}
		return {
			sortKey: undefined,
			sortDirection: undefined,
		};
	}

	private compareArrays(
		studentArray: string[] = [],
		referenceArray: string[] = [],
		studentAliasMap?: Record<string, string>,
		referenceAliasMap?: Record<string, string>
	): boolean {
		if (studentArray.length !== referenceArray.length) return false;

		let normalizedStudentArray = studentArray?.map((g) => this.normalizeFilter(g, studentAliasMap));
		let normalizedReferenceArray = referenceArray?.map((g) => this.normalizeFilter(g, referenceAliasMap));
		const sortedArr1 = [...normalizedStudentArray].sort();
		const sortedArr2 = [...normalizedReferenceArray].sort();
		return sortedArr1.every((val, index) => val === sortedArr2[index]);
	}

	private normalizeTableName = (name: string, aliasMap?: Record<string, string>) => {
		if (!aliasMap) return name;
		return aliasMap[name] || name;
	};

	private compareJoinStatements(
		studentJoin: JoinStatement,
		referenceJoin: JoinStatement,
		studentAliasMap?: Record<string, string>,
		referenceAliasMap?: Record<string, string>
	): boolean {
		let isEqual = true;

		if (studentJoin.joinType === referenceJoin.joinType) {
		} else {
			isEqual = false;
		}

		if (
			this.normalizeTableName(studentJoin.tableName, studentAliasMap) ===
			this.normalizeTableName(referenceJoin.tableName, referenceAliasMap)
		) {
		} else {
			isEqual = false;
		}

		if (
			this.normalizeFilter(studentJoin.joinCondition, studentAliasMap) ===
			this.normalizeFilter(referenceJoin.joinCondition, referenceAliasMap)
		) {
		} else {
			isEqual = false;
		}

		if (studentJoin.joinedTable && referenceJoin.joinedTable) {
			let isNestedJoinEqual: boolean = true;
			isNestedJoinEqual = this.compareJoinStatements(
				studentJoin.joinedTable,
				referenceJoin.joinedTable,
				studentAliasMap,
				referenceAliasMap
			);
			if (!isNestedJoinEqual) {
				isEqual = false;
			}
		} else if (studentJoin.joinedTable || referenceJoin.joinedTable) {
			isEqual = false;
		}

		return isEqual;
	}

	private compareExecutionPlans(
		studenPlan: IParsedExecutionPlan,
		referencePlan: IParsedExecutionPlan,
		studentAST: any,
		referenceAST: any,
		studentAliasMap: Record<string, string>,
		referenceAliasMap: Record<string, string>
	): [string[], string[], number] {
		let feedback: string[] = [];
		let feedbackWithSolution: string[] = [];
		let grade = 0;

		if (!this.compareArrays(studenPlan.groupKey, referencePlan.groupKey, studentAliasMap, referenceAliasMap)) {
			feedback.push(`Incorrect Group key.`);
			feedbackWithSolution.push(`Expected ${referencePlan.groupKey}, got ${studenPlan.groupKey}.`);
			grade++;
		}

		if (
			this.normalizeFilter(studenPlan.havingFilter, studentAliasMap) !==
			this.normalizeFilter(referencePlan.havingFilter, referenceAliasMap)
		) {
			grade++;
			feedback.push(`Incorrect Having filter.`);
			feedbackWithSolution.push(`Expected ${referencePlan.havingFilter}, got ${studenPlan.havingFilter}.`);
		}

		if (!this.compareArrays(studenPlan.sortKey, referencePlan.sortKey, studentAliasMap, referenceAliasMap)) {
			grade++;
			feedback.push(`Incorrect Order By sort key.`);
			feedbackWithSolution.push(`Expected ${referencePlan.sortKey}, got ${studenPlan.sortKey}.`);
		}

		if (!this.compareArrays(studenPlan.whereFilter, referencePlan.whereFilter, studentAliasMap, referenceAliasMap)) {
			grade++;
			feedback.push(`Incorrect Where filter.`);
			feedbackWithSolution.push(`Expected ${referencePlan.whereFilter}, got ${studenPlan.whereFilter}.`);
		}

		if (studenPlan.joinStatement && referencePlan.joinStatement) {
			let isJoinEqual: boolean = true;
			let feedbackJoin,
				solution: string[] = [];
			isJoinEqual = this.compareJoinStatements(
				studenPlan.joinStatement,
				referencePlan.joinStatement,
				studentAliasMap,
				referenceAliasMap
			);
			if (!isJoinEqual) {
				[isJoinEqual, feedbackJoin, solution] = this.compareJoinAST(
					referenceAST.from as Join[],
					studentAST.from as Join[],
					studentAliasMap,
					referenceAliasMap
				);
				feedback.push(...feedbackJoin);
				feedbackWithSolution.push(...solution);
				if (!isJoinEqual) grade++;
			}
		} else if (studenPlan.joinStatement && !referencePlan.joinStatement) {
			feedback.push("Incorrect inclusion of Join statement");
		} else if (referencePlan.joinStatement && !studenPlan.joinStatement) {
			feedback.push("Join statement missing.");
		}

		return [feedback, feedbackWithSolution, grade];
	}

	private compareJoinAST(
		referenceJoin: Join[],
		studentJoin: Join[],
		studentAliasMap?: Record<string, string>,
		referenceAliasMap?: Record<string, string>
	): [boolean, string[], string[]] {
		let feedback: string[] = [];
		let feedbackWithSolution: string[] = [];
		let isSameJoin = true;
		if (referenceJoin.length !== studentJoin.length) {
			isSameJoin = false;
			feedback.push("Incorrect Join statement: Query does not include the correct number of Joins.");
			feedbackWithSolution.push(...this.printJoinComparison(referenceJoin, studentJoin));
			return [isSameJoin, feedback, feedbackWithSolution];
		}

		if (referenceJoin.length == 1 && studentJoin.length == 1) {
			if (referenceJoin[0].table !== studentJoin[0].table) {
				isSameJoin = false;
				feedback.push("Incorrect Join statement: Query uses incorrect table in Join statement");
			}
		}

		for (let i = 1; i < referenceJoin.length; i++) {
			const reference = referenceJoin[i];
			const student = studentJoin[i];

			const joinType1 = reference.join;
			const joinType2 = student.join;

			if (!this.areJoinTypesCompatible(joinType1, joinType2, i, referenceJoin, studentJoin)) {
				isSameJoin = false;
				feedback.push("Incorrect Join statement: Query uses wrong Join type.");
			}

			if (reference.table !== student.table) {
				if (
					!(i > 0 && reference.table === studentJoin[i - 1]?.table && student.table === referenceJoin[i - 1]?.table)
				) {
					isSameJoin = false;
					feedback.push("Incorrect Join statement: Query uses incorrect table in Join statement.");
				}
			}

			if (!this.areJoinConditionsEqual(reference.on, student.on, studentAliasMap, referenceAliasMap)) {
				isSameJoin = false;
				feedback.push("Incorrect Join statement: Query uses incorrect Join condition.");
			}
		}

		if (feedback.length > 0) {
			feedbackWithSolution.push(...this.printJoinComparison(referenceJoin, studentJoin));
		}
		return [isSameJoin, feedback, feedbackWithSolution];
	}

	private printJoinComparison(joins1: Join[], joins2: Join[]): string[] {
		let feedback: string[] = [];
		const formatJoin = (join: Join, parent?: Join) => {
			const parentTable = parent?.table;
			return `${parentTable || ""} ${join?.join || ""} ${join?.table || ""} ${this.normalizeCondition(join?.on) || ""}`;
		};

		for (let i = 0; i < Math.max(joins1.length, joins2.length); i++) {
			const join1 = joins1[i];
			const join2 = joins2[i];
			const parent1 = joins1[i - 1];
			const parent2 = joins2[i - 1];

			const expected = join1 ? formatJoin(join1, parent1) : "";
			const received = join2 ? formatJoin(join2, parent2) : "";
			feedback.push(`Expected: ${expected}`);
			feedback.push(`Received: ${received}`);
		}
		return feedback;
	}

	private areJoinConditionsEqual(
		referenceCondition?: any,
		studentCondition?: any,
		studentAliasMap?: Record<string, string>,
		referenceAliasMap?: Record<string, string>
	): boolean {
		if (!referenceCondition || !studentCondition) {
			return referenceCondition === studentCondition;
		}

		const referenceNormalized = this.normalizeCondition(referenceCondition, referenceAliasMap);
		const studentNormalized = this.normalizeCondition(studentCondition, studentAliasMap);

		return referenceNormalized === studentNormalized;
	}

	private normalizeCondition(condition: any, aliasMap?: Record<string, string>) {
		if (typeof condition === "string") return this.normalizeFilter(condition, aliasMap);
		let binaryCondition = condition as Binary;
		if (binaryCondition) {
			let leftColumn =
				typeof (binaryCondition.left as ColumnRefItem).column === "string"
					? (binaryCondition.left as ColumnRefItem).column
					: (binaryCondition.left as any).column.expr.value;
			let rightColumn =
				typeof (binaryCondition.right as ColumnRefItem).column === "string"
					? (binaryCondition.left as ColumnRefItem).column
					: (binaryCondition.right as any).column.expr.value;
			let leftTable = this.normalizeTableName((binaryCondition.left as ColumnRefItem).table || "", aliasMap);
			let rightTable = this.normalizeTableName((binaryCondition.right as ColumnRefItem).table || "", aliasMap);
			let conditionString = `${leftTable}.${leftColumn}${binaryCondition.operator}${rightTable}.${rightColumn}`;
			return conditionString.replace(/\s/g, "").split("=").sort().join("=");
		}
	}

	private areJoinTypesCompatible(type1: string, type2: string, index: number, joins1: Join[], joins2: Join[]): boolean {
		if (type1 === type2) return true;

		if ((type1 === "INNER JOIN" && type2 === "JOIN") || (type1 === "JOIN" && type2 === "INNER JOIN")) {
			return true;
		}

		return false;
	}
}
