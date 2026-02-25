import { Binary, ColumnRefItem, Join } from 'node-sql-parser';
import { JoinStatement } from '../shared/interfaces/execution-plan';
import {
	FeedbackEntry,
	FeedbackEntrySolution,
} from '../shared/interfaces/feedback';
import { t, SupportedLanguage } from '../shared/i18n';

/**
 * Compares join structures between student and reference queries using both
 * execution-plan join statements and AST-level join arrays.
 */
export class JoinComparator {
	compareJoinStatements(
		studentJoin: JoinStatement,
		referenceJoin: JoinStatement,
		studentAliasMap?: Record<string, string>,
		referenceAliasMap?: Record<string, string>,
	): boolean {
		let isEqual = true;

		if (studentJoin.joinType !== referenceJoin.joinType) {
			isEqual = false;
		}

		if (
			this.normalizeTableName(studentJoin.tableName, studentAliasMap) !==
			this.normalizeTableName(referenceJoin.tableName, referenceAliasMap)
		) {
			isEqual = false;
		}

		if (
			this.normalizeFilter(studentJoin.joinCondition, studentAliasMap) !==
			this.normalizeFilter(referenceJoin.joinCondition, referenceAliasMap)
		) {
			isEqual = false;
		}

		if (studentJoin.joinedTable && referenceJoin.joinedTable) {
			const isNestedJoinEqual = this.compareJoinStatements(
				studentJoin.joinedTable,
				referenceJoin.joinedTable,
				studentAliasMap,
				referenceAliasMap,
			);
			if (!isNestedJoinEqual) {
				isEqual = false;
			}
		} else if (studentJoin.joinedTable || referenceJoin.joinedTable) {
			isEqual = false;
		}

		return isEqual;
	}

	/**
	 * Compares two AST JOIN arrays and returns a structured feedback entry.
	 *
	 * Returns [isEqual, entry] where `entry` is a FeedbackEntry when there is a
	 * mismatch, or undefined when the joins are equal.  The `solution` field of
	 * the entry contains a formatted Expected/Received comparison string.
	 */
	compareJoinAST(
		referenceJoin: Join[],
		studentJoin: Join[],
		studentAliasMap?: Record<string, string>,
		referenceAliasMap?: Record<string, string>,
		lang: SupportedLanguage = 'en',
	): [boolean, FeedbackEntry | undefined] {
		const messages: string[] = [];
		let isSameJoin = true;

		if (referenceJoin.length !== studentJoin.length) {
			isSameJoin = false;
			messages.push(t('FEEDBACK_JOIN_COUNT_WRONG', lang));
			return [
				isSameJoin,
				{
					message: messages.join(' '),
					solution: this.buildJoinComparisonSolution(
						referenceJoin,
						studentJoin,
						lang,
					),
				},
			];
		}

		if (referenceJoin.length === 1 && studentJoin.length === 1) {
			if (referenceJoin[0].table !== studentJoin[0].table) {
				isSameJoin = false;
				messages.push(t('FEEDBACK_JOIN_WRONG_TABLE', lang));
			}
		}

		for (let i = 1; i < referenceJoin.length; i++) {
			const reference = referenceJoin[i];
			const student = studentJoin[i];

			const joinType1 = reference.join;
			const joinType2 = student.join;

			if (!this.areJoinTypesCompatible(joinType1, joinType2)) {
				isSameJoin = false;
				messages.push(t('FEEDBACK_JOIN_WRONG_TYPE', lang));
			}

			if (reference.table !== student.table) {
				if (
					!(
						i > 0 &&
						reference.table === studentJoin[i - 1]?.table &&
						student.table === referenceJoin[i - 1]?.table
					)
				) {
					isSameJoin = false;
					messages.push(t('FEEDBACK_JOIN_WRONG_TABLE', lang));
				}
			}

			if (
				!this.areJoinConditionsEqual(
					reference.on,
					student.on,
					studentAliasMap,
					referenceAliasMap,
				)
			) {
				isSameJoin = false;
				messages.push(t('FEEDBACK_JOIN_WRONG_CONDITION', lang));
			}
		}

		if (messages.length > 0) {
			return [
				isSameJoin,
				{
					message: messages.join(' '),
					solution: this.buildJoinComparisonSolution(
						referenceJoin,
						studentJoin,
						lang,
					),
				},
			];
		}

		return [isSameJoin, undefined];
	}

	normalizeCondition(
		condition: any,
		aliasMap?: Record<string, string>,
	): string | undefined {
		if (typeof condition === 'string')
			return this.normalizeFilter(condition, aliasMap);
		const binaryCondition = condition as Binary;
		if (binaryCondition) {
			const leftColumn =
				typeof (binaryCondition.left as ColumnRefItem).column === 'string'
					? (binaryCondition.left as ColumnRefItem).column
					: (binaryCondition.left as any).column.expr.value;
			// Bug fix: rightColumn was incorrectly reading from binaryCondition.left instead of .right
			const rightColumn =
				typeof (binaryCondition.right as ColumnRefItem).column === 'string'
					? (binaryCondition.right as ColumnRefItem).column
					: (binaryCondition.right as any).column.expr.value;
			const leftTable = this.normalizeTableName(
				(binaryCondition.left as ColumnRefItem).table || '',
				aliasMap,
			);
			const rightTable = this.normalizeTableName(
				(binaryCondition.right as ColumnRefItem).table || '',
				aliasMap,
			);
			const conditionString = `${leftTable}.${leftColumn}${binaryCondition.operator}${rightTable}.${rightColumn}`;
			return conditionString.replace(/\s/g, '').split('=').sort().join('=');
		}
	}

	normalizeFilter(
		filter?: string,
		aliasMap?: Record<string, string>,
	): string | undefined {
		if (!filter || !aliasMap) return filter;
		return filter.replace(/\b\w+\b/g, (match) => aliasMap[match] || match);
	}

	normalizeTableName(name: string, aliasMap?: Record<string, string>): string {
		if (!aliasMap) return name;
		return aliasMap[name] || name;
	}

	private areJoinConditionsEqual(
		referenceCondition?: any,
		studentCondition?: any,
		studentAliasMap?: Record<string, string>,
		referenceAliasMap?: Record<string, string>,
	): boolean {
		if (!referenceCondition || !studentCondition) {
			return referenceCondition === studentCondition;
		}

		const referenceNormalized = this.normalizeCondition(
			referenceCondition,
			referenceAliasMap,
		);
		const studentNormalized = this.normalizeCondition(
			studentCondition,
			studentAliasMap,
		);

		return referenceNormalized === studentNormalized;
	}

	private areJoinTypesCompatible(type1: string, type2: string): boolean {
		if (type1 === type2) return true;
		if (
			(type1 === 'INNER JOIN' && type2 === 'JOIN') ||
			(type1 === 'JOIN' && type2 === 'INNER JOIN')
		) {
			return true;
		}
		return false;
	}

	/**
	 * Builds a multi-line Expected/Received comparison string used as the
	 * `solution` field of a join FeedbackEntry.
	 */
	private buildJoinComparisonSolution(
		joins1: Join[],
		joins2: Join[],
		lang: SupportedLanguage = 'en',
	) {
		const lines: FeedbackEntrySolution[] = [];
		const formatJoin = (join: Join, parent?: Join) => {
			const parentTable = parent?.table;
			return `${parentTable || ''} ${join?.join || ''} ${join?.table || ''} ${this.normalizeCondition(join?.on) || ''}`;
		};

		for (let i = 0; i < Math.max(joins1.length, joins2.length); i++) {
			const join1 = joins1[i];
			const join2 = joins2[i];
			const parent1 = joins1[i - 1];
			const parent2 = joins2[i - 1];

			const expected = join1 ? formatJoin(join1, parent1) : '';
			const received = join2 ? formatJoin(join2, parent2) : '';
			lines.push({
				expected: t('FEEDBACK_JOIN_SOLUTION_EXPECTED', lang, expected),
				received: t('FEEDBACK_JOIN_SOLUTION_RECEIVED', lang, received),
			});
		}
		return lines;
	}
}
