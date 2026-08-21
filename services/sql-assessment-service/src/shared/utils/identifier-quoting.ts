/**
 * Quotes a SQL identifier (schema, table, column, alias) for PostgreSQL
 * according to double-quote rules: the identifier is wrapped in double quotes
 * and any embedded double quote is doubled. Unquoted lowercase identifiers
 * behave identically in PostgreSQL, so quoting is transparent for them.
 */
export function quoteIdentifier(name: string): string {
	return `"${name.replace(/"/g, '""')}"`;
}
