import { DataSource, QueryFailedError } from 'typeorm';
import { t, SupportedLanguage } from '../shared/i18n';

/**
 * Handles dynamic execution and row-level comparison of two query result sets.
 */
export class ResultSetComparator {

    async compare(
        referenceQuery: string,
        studentQuery: string,
        dataSource: DataSource,
        lang: SupportedLanguage = 'en'
    ): Promise<[boolean, string[]]> {
        let referenceResultSet: any[];
        let studentResultSet: any[];
        let comparisonResult: boolean;
        const feedback: string[] = [];

        try {
            const queryRunner = dataSource.createQueryRunner();
            referenceResultSet = await queryRunner.query(referenceQuery);
            studentResultSet = await queryRunner.query(studentQuery);
            comparisonResult = this.areResultsEqual(referenceResultSet, studentResultSet);
            queryRunner.release();
        } catch (error) {
            feedback.push(t('FEEDBACK_QUERY_COMPARISON_ERROR', lang, String(error)));
            return [false, feedback];
        }

        return [comparisonResult, feedback];
    }

    async isExecutable(
        query: string,
        dataSource: DataSource,
        lang: SupportedLanguage = 'en'
    ): Promise<[boolean, string[]]> {
        const feedback: string[] = [];
        try {
            const queryRunner = dataSource.createQueryRunner();
            await queryRunner.query(query);
            queryRunner.release();
        } catch (error) {
            feedback.push(t('FEEDBACK_QUERY_EXECUTION_ERROR', lang));
            feedback.push((error as QueryFailedError)?.driverError?.message);
            return [false, feedback];
        }
        return [true, feedback];
    }

    private areResultsEqual(referenceQuery: any[], studentQuery: any[]): boolean {
        if (referenceQuery.length !== studentQuery.length) return false;

        for (let i = 0; i < referenceQuery.length; i++) {
            if (this.normalizeColumnOrderForRow(referenceQuery[i]) !== this.normalizeColumnOrderForRow(studentQuery[i])) {
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
                    {} as Record<string, any>
                )
        );
    }
}
