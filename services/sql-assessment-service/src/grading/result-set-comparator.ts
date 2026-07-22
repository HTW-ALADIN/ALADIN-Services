import { QueryFailedError } from 'typeorm';
import { RowQueryFn } from '../shared/utils/database-utils';
import { t, SupportedLanguage } from '../shared/i18n';

/**
 * Extracts a human-readable message from a database error.
 *
 * TypeORM wraps driver errors in {@link QueryFailedError} (with a
 * `driverError.message`), whereas PGlite throws a plain {@link Error}.  This
 * helper normalises both so grading feedback is populated regardless of the
 * execution backend.
 */
function extractDbErrorMessage(error: unknown): string {
	const driverMessage = (error as QueryFailedError)?.driverError?.message;
	if (typeof driverMessage === 'string' && driverMessage.length > 0) {
		return driverMessage;
	}
	if (error instanceof Error && error.message) {
		return error.message;
	}
	return String(error);
}

/**
 * Handles dynamic execution and row-level comparison of two query result sets.
 *
 * Execution is delegated to a {@link RowQueryFn} so the comparator is agnostic
 * to the underlying backend (TypeORM Postgres or in-process PGlite).
 */
export class ResultSetComparator {
	/**
	 * Executes the reference and student queries and compares their result sets.
	 *
	 * NOTE ON SESSION SCOPE: the reference and student queries are executed via
	 * two independent {@link RowQueryFn} invocations.  For the Postgres backend
	 * each invocation acquires and releases its own QueryRunner (a separate
	 * connection/session); the PGlite backend shares one in-process instance.
	 * Neither query may therefore rely on session-local state established by the
	 * other — e.g. temporary tables, `SET` / `SET LOCAL` parameters (search_path,
	 * timeouts), session variables, prepared statements, or transaction scope.
	 * This is safe for the read-only SELECTs used in grading; revisit the
	 * executor design before introducing any cross-query session dependency.
	 */
	async compare(
		referenceQuery: string,
		studentQuery: string,
		runQuery: RowQueryFn,
		lang: SupportedLanguage = 'en',
	): Promise<[boolean, string[]]> {
		let referenceResultSet: unknown[];
		let studentResultSet: unknown[];
		let comparisonResult: boolean;
		const feedback: string[] = [];

		try {
			referenceResultSet = await runQuery(referenceQuery);
			studentResultSet = await runQuery(studentQuery);
			comparisonResult = this.areResultsEqual(
				referenceResultSet,
				studentResultSet,
			);
		} catch (error) {
			feedback.push(t('FEEDBACK_QUERY_COMPARISON_ERROR', lang, String(error)));
			return [false, feedback];
		}

		return [comparisonResult, feedback];
	}

	async isExecutable(
		query: string,
		runQuery: RowQueryFn,
		lang: SupportedLanguage = 'en',
	): Promise<[boolean, string[]]> {
		const feedback: string[] = [];
		try {
			await runQuery(query);
		} catch (error) {
			feedback.push(t('FEEDBACK_QUERY_EXECUTION_ERROR', lang));
			feedback.push(extractDbErrorMessage(error));
			return [false, feedback];
		}
		return [true, feedback];
	}

	private areResultsEqual(
		referenceQuery: unknown[],
		studentQuery: unknown[],
	): boolean {
		if (referenceQuery.length !== studentQuery.length) return false;

		for (let i = 0; i < referenceQuery.length; i++) {
			if (
				this.normalizeColumnOrderForRow(referenceQuery[i]) !==
				this.normalizeColumnOrderForRow(studentQuery[i])
			) {
				return false;
			}
		}

		return true;
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
					{} as Record<string, unknown>,
				),
		);
	}
}
