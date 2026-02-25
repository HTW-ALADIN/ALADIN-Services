import { SupportedLanguage } from '../../shared/i18n';

/**
 * Handles language-aware surface realization of SQL identifiers:
 * converting raw database names (table names, column names) into
 * human-readable display strings, respecting language-specific rules
 * such as capitalisation and pluralisation.
 */
export class SurfaceRealizationService {
	/**
	 * Converts a raw database identifier into a human-readable display name.
	 *
	 * Steps applied:
	 *  1. Replace underscores and hyphens with spaces.
	 *  2. Separate CamelCase boundaries with spaces.
	 *  3. Append a space before trailing "id" suffixes (e.g. "employeeId" → "employee id").
	 *  4. When `aggregation` is COUNT, SUM, or AVG, apply pluralisation.
	 *  5. Apply language-specific case transformation.
	 *
	 * @param name        - Raw identifier string (column or table name).
	 * @param lang        - Target language; controls case and pluralisation behaviour.
	 * @param aggregation - Optional SQL aggregate function name (MAX, MIN, COUNT, SUM, AVG).
	 */
	public formatName(
		name: string,
		lang: SupportedLanguage = 'en',
		aggregation?: string,
	): string {
		if (!name) return '';
		let safeName = name;
		if (typeof name == 'object' && (name as any).expr?.value)
			safeName = (name as any).expr.value;

		const formatted = safeName
			.replace(/_/g, ' ')
			.replace(/-/g, ' ')
			.replace(/(\w+)id$/i, '$1 id');

		if (
			aggregation &&
			(aggregation === 'COUNT' ||
				aggregation === 'SUM' ||
				aggregation === 'AVG')
		) {
			return this.pluralize(formatted, lang);
		}

		return this.separateWords(formatted, lang);
	}

	/**
	 * Inserts spaces at CamelCase word boundaries and at underscore/hyphen
	 * separators, then applies language-specific case transformation.
	 *
	 * For English the result is fully lowercased (consistent with the existing
	 * behaviour before this refactor). For German the original casing is
	 * preserved because German nouns must remain capitalised.
	 *
	 * @param str  - Pre-processed identifier string (underscores already removed).
	 * @param lang - Target language.
	 */
	public separateWords(str: string, lang: SupportedLanguage = 'en'): string {
		const regex = /([a-z0-9])([A-Z])|([_-])([a-zA-Z0-9])/g;
		const separated = str.replace(regex, (_, p1, p2, p3, p4) => {
			if (p1 && p2) return p1 + ' ' + p2;
			if (p3 && p4) return ' ' + p4;
			return 'match';
		});
		return lang === 'de' ? separated : separated.toLowerCase();
	}

	/**
	 * Returns a pluralised form of `name`.
	 *
	 * English: appends "s" unless the name already ends in "s".
	 * German:  returns the name unchanged — German pluralisation rules are
	 *          too irregular to automate generically without a dictionary.
	 *
	 * @param name - Display name to pluralise.
	 * @param lang - Target language.
	 */
	public pluralize(name: string, lang: SupportedLanguage = 'en'): string {
		if (lang === 'de') return name;
		if (name.endsWith('s')) return name;
		return `${name}s`;
	}
}
