/**
 * Centralised error-message catalogue.
 *
 * Every user-facing error string in the API lives here, keyed by a
 * language-neutral MessageKey.  Controllers and services call t(key, lang)
 * instead of inlining raw strings so that new languages can be added in one
 * place without touching any controller code.
 *
 * Interpolation: a handful of messages contain a single {{value}} placeholder.
 * Pass the `params` argument to t() to substitute it.
 *
 * Supported languages: "en" (default), "de".
 * Unknown language codes fall back to English.
 */

export type MessageKey =
	// ── shared / connection ──────────────────────────────────────────────────
	| 'INVALID_REQUEST_BODY'
	| 'MISSING_CONNECTION_INFO'
	| 'INVALID_CONNECTION_INFO'
	| 'UNABLE_TO_CONNECT'
	| 'DATABASE_NOT_REGISTERED'
	// ── database controller ──────────────────────────────────────────────────
	| 'DATABASE_ANALYSIS_SUCCESS'
	| 'DATABASE_SCHEMA_EXTRACTION_FAILED'
	| 'INIT_SQL_READ_ERROR'
	// ── query execution ──────────────────────────────────────────────────────
	| 'MISSING_OR_EMPTY_QUERY'
	| 'QUERY_EMPTY'
	| 'QUERY_PARSE_ERROR'
	| 'QUERY_MULTIPLE_STATEMENTS'
	| 'QUERY_NON_SELECT'
	| 'QUERY_EXECUTION_FAILED'
	| 'QUERY_UNEXPECTED_ERROR'
	// ── grading ──────────────────────────────────────────────────────────────
	| 'GRADING_READ_ERROR'
	| 'GRADING_CONNECTION_READ_ERROR'
	| 'GRADING_FAILED'
	| 'GRADING_FAILED_WITH_ERROR'
	// ── grading feedback — result set ─────────────────────────────────────────
	| 'FEEDBACK_RESULT_SET_MATCH'
	| 'FEEDBACK_RESULT_SET_MISMATCH'
	// ── grading feedback — executability ─────────────────────────────────────
	| 'FEEDBACK_QUERY_NOT_EXECUTABLE'
	| 'FEEDBACK_QUERY_EXECUTION_ERROR'
	| 'FEEDBACK_QUERY_COMPARISON_ERROR'
	// ── grading feedback — AST parsing ───────────────────────────────────────
	| 'FEEDBACK_AST_ARRAY_UNSUPPORTED'
	| 'FEEDBACK_AST_PARSE_FAILED'
	| 'FEEDBACK_AST_NOT_SELECT'
	| 'FEEDBACK_SQL_CLAUSE_TYPE'
	// ── grading feedback — columns ────────────────────────────────────────────
	| 'FEEDBACK_COLUMNS_WRONG_COUNT'
	| 'FEEDBACK_COLUMNS_INCORRECT'
	| 'FEEDBACK_COLUMNS_MESSAGE'
	| 'FEEDBACK_COLUMNS_SOLUTION'
	// ── grading feedback — LIMIT / OFFSET ─────────────────────────────────────
	| 'FEEDBACK_LIMIT_INCORRECT'
	| 'FEEDBACK_LIMIT_SOLUTION'
	| 'FEEDBACK_OFFSET_INCORRECT'
	| 'FEEDBACK_OFFSET_SOLUTION'
	// ── grading feedback — JOIN ───────────────────────────────────────────────
	| 'FEEDBACK_JOIN_COUNT_WRONG'
	| 'FEEDBACK_JOIN_WRONG_TABLE'
	| 'FEEDBACK_JOIN_WRONG_TYPE'
	| 'FEEDBACK_JOIN_WRONG_CONDITION'
	| 'FEEDBACK_JOIN_SOLUTION_EXPECTED'
	| 'FEEDBACK_JOIN_SOLUTION_RECEIVED'
	| 'FEEDBACK_JOIN_EXTRA'
	| 'FEEDBACK_JOIN_MISSING'
	// ── grading feedback — execution plan ─────────────────────────────────────
	| 'FEEDBACK_PLAN_RETRIEVAL_FAILED'
	| 'FEEDBACK_PLAN_PARSE_FAILED'
	| 'FEEDBACK_GROUP_KEY'
	| 'FEEDBACK_GROUP_KEY_SOLUTION'
	| 'FEEDBACK_HAVING'
	| 'FEEDBACK_HAVING_SOLUTION'
	| 'FEEDBACK_ORDER_BY'
	| 'FEEDBACK_ORDER_BY_SOLUTION'
	| 'FEEDBACK_WHERE'
	| 'FEEDBACK_WHERE_SOLUTION'
	| 'FEEDBACK_DISTINCT_MISSING'
	| 'FEEDBACK_DISTINCT_MISSING_SOLUTION'
	| 'FEEDBACK_DISTINCT_EXTRA'
	| 'FEEDBACK_DISTINCT_EXTRA_SOLUTION'
	| 'FEEDBACK_DISTINCT_STRATEGY'
	| 'FEEDBACK_CTE_INCORRECT'
	| 'FEEDBACK_CTE_SOLUTION'
	| 'FEEDBACK_LIMIT_MISSING'
	| 'FEEDBACK_LIMIT_MISSING_SOLUTION'
	| 'FEEDBACK_LIMIT_EXTRA'
	| 'FEEDBACK_LIMIT_EXTRA_SOLUTION'
	| 'FEEDBACK_WINDOW_MISSING'
	| 'FEEDBACK_WINDOW_MISSING_SOLUTION'
	| 'FEEDBACK_WINDOW_EXTRA'
	| 'FEEDBACK_WINDOW_PARTITION'
	| 'FEEDBACK_WINDOW_PARTITION_SOLUTION'
	| 'FEEDBACK_WINDOW_ORDER_BY'
	| 'FEEDBACK_WINDOW_ORDER_BY_SOLUTION'
	| 'FEEDBACK_SUBQUERY_COUNT'
	| 'FEEDBACK_SUBQUERY_COUNT_SOLUTION_SINGULAR'
	| 'FEEDBACK_SUBQUERY_COUNT_SOLUTION_PLURAL'
	| 'FEEDBACK_SUBQUERY_TYPE'
	// ── grading feedback — task description ───────────────────────────────────
	| 'FEEDBACK_TASK_DESCRIPTION'
	// ── description generation ───────────────────────────────────────────────
	| 'DESCRIPTION_MISSING_QUERY'
	| 'DESCRIPTION_PARSE_FAILED'
	| 'DESCRIPTION_TEMPLATE_FAILED'
	| 'DESCRIPTION_LLM_DEFAULT_FAILED'
	| 'DESCRIPTION_LLM_CREATIVE_FAILED'
	| 'DESCRIPTION_LLM_MULTISTEP_FAILED'
	| 'DESCRIPTION_HYBRID_FAILED'
	// ── task generation ──────────────────────────────────────────────────────
	| 'TASK_GENERATION_INVALID_REQUEST'
	| 'TASK_GENERATION_INVALID_CONNECTION'
	| 'TASK_GENERATION_QUERY_ERROR'
	| 'TASK_GENERATION_DESCRIPTION_ERROR';

export type SupportedLanguage = 'en' | 'de';

type MessageCatalogue = Record<SupportedLanguage, Record<MessageKey, string>>;

export const MESSAGES: MessageCatalogue = {
	en: {
		// shared
		INVALID_REQUEST_BODY: 'Invalid request body.',
		MISSING_CONNECTION_INFO: 'Missing connectionInfo.',
		INVALID_CONNECTION_INFO: 'Invalid connection information.',
		UNABLE_TO_CONNECT: 'Unable to connect to database.',
		DATABASE_NOT_REGISTERED:
			'Unregistered database, please trigger database analysis.',
		// database controller
		DATABASE_ANALYSIS_SUCCESS: 'Connection successful.',
		DATABASE_SCHEMA_EXTRACTION_FAILED: 'Unable to extract database schema.',
		INIT_SQL_READ_ERROR: 'Failed to read the database initialization script.',

		// query execution
		MISSING_OR_EMPTY_QUERY: 'Missing or empty query string.',
		QUERY_EMPTY: 'Query must not be empty.',
		QUERY_PARSE_ERROR: 'The provided input could not be parsed as a SQL query.',
		QUERY_MULTIPLE_STATEMENTS:
			'Only a single SELECT statement is allowed per request.',
		QUERY_NON_SELECT:
			'Only SELECT queries are permitted. Received statement type: "{{value}}".',
		QUERY_EXECUTION_FAILED: 'Query execution failed: {{value}}',
		QUERY_UNEXPECTED_ERROR: 'Unexpected error: {{value}}',
		// grading
		GRADING_READ_ERROR: 'Error reading task configuration.',
		GRADING_CONNECTION_READ_ERROR: 'Error reading connection information.',
		GRADING_FAILED: 'Unable to grade query.',
		GRADING_FAILED_WITH_ERROR: 'Unable to grade query. Error: {{value}}',
		// grading feedback — result set
		FEEDBACK_RESULT_SET_MATCH: 'Same result set of both queries.',
		FEEDBACK_RESULT_SET_MISMATCH: 'Result sets differ.',
		// grading feedback — executability
		FEEDBACK_QUERY_NOT_EXECUTABLE: 'Query is not executable.',
		FEEDBACK_QUERY_EXECUTION_ERROR:
			'Query is not executable due to following syntax error:',
		FEEDBACK_QUERY_COMPARISON_ERROR:
			'Unable to execute query comparison: {{value}}',
		// grading feedback — AST parsing
		FEEDBACK_AST_ARRAY_UNSUPPORTED: 'AST array not supported.',
		FEEDBACK_AST_PARSE_FAILED: 'AST parsing failed.',
		FEEDBACK_AST_NOT_SELECT: 'Error: Not a select statement.',
		FEEDBACK_SQL_CLAUSE_TYPE:
			'Incorrect SQL clause, the task requires a clause of type: {{value}}',
		// grading feedback — columns
		FEEDBACK_COLUMNS_WRONG_COUNT: 'Incorrect number of columns selected.',
		FEEDBACK_COLUMNS_INCORRECT: 'Incorrect columns selected.',
		FEEDBACK_COLUMNS_MESSAGE: 'The column selection is incorrect: {{value}}',
		FEEDBACK_COLUMNS_SOLUTION:
			'The task requires the selection of the following columns: {{value}}',
		// grading feedback — LIMIT / OFFSET
		FEEDBACK_LIMIT_INCORRECT: 'Incorrect LIMIT value.',
		FEEDBACK_LIMIT_SOLUTION: 'Expected LIMIT {{expected}}, got {{received}}.',
		FEEDBACK_OFFSET_INCORRECT: 'Incorrect OFFSET value.',
		FEEDBACK_OFFSET_SOLUTION: 'Expected OFFSET {{expected}}, got {{received}}.',
		// grading feedback — JOIN
		FEEDBACK_JOIN_COUNT_WRONG:
			'Incorrect Join statement: Query does not include the correct number of Joins.',
		FEEDBACK_JOIN_WRONG_TABLE:
			'Incorrect Join statement: Query uses incorrect table in Join statement.',
		FEEDBACK_JOIN_WRONG_TYPE:
			'Incorrect Join statement: Query uses wrong Join type.',
		FEEDBACK_JOIN_WRONG_CONDITION:
			'Incorrect Join statement: Query uses incorrect Join condition.',
		FEEDBACK_JOIN_SOLUTION_EXPECTED: 'Expected: {{value}}',
		FEEDBACK_JOIN_SOLUTION_RECEIVED: 'Received: {{value}}',
		FEEDBACK_JOIN_EXTRA: 'Incorrect inclusion of Join statement.',
		FEEDBACK_JOIN_MISSING: 'Join statement missing.',
		// grading feedback — execution plan
		FEEDBACK_PLAN_RETRIEVAL_FAILED: 'Unable to retrieve execution plans.',
		FEEDBACK_PLAN_PARSE_FAILED: 'Unable to parse execution plans.',
		FEEDBACK_GROUP_KEY: 'Incorrect Group key.',
		FEEDBACK_GROUP_KEY_SOLUTION: 'Expected {{expected}}, got {{received}}.',
		FEEDBACK_HAVING: 'Incorrect Having filter.',
		FEEDBACK_HAVING_SOLUTION: 'Expected {{expected}}, got {{received}}.',
		FEEDBACK_ORDER_BY: 'Incorrect Order By sort key.',
		FEEDBACK_ORDER_BY_SOLUTION: 'Expected {{expected}}, got {{received}}.',
		FEEDBACK_WHERE: 'Incorrect Where filter.',
		FEEDBACK_WHERE_SOLUTION: 'Expected {{expected}}, got {{received}}.',
		FEEDBACK_DISTINCT_MISSING: 'DISTINCT keyword is missing from the query.',
		FEEDBACK_DISTINCT_MISSING_SOLUTION: 'The query should use SELECT DISTINCT.',
		FEEDBACK_DISTINCT_EXTRA:
			'DISTINCT keyword should not be used in this query.',
		FEEDBACK_DISTINCT_EXTRA_SOLUTION:
			'The query should use plain SELECT without DISTINCT.',
		FEEDBACK_DISTINCT_STRATEGY:
			'Note: different DISTINCT implementation strategy (student: {{student}}, reference: {{reference}}).',
		FEEDBACK_CTE_INCORRECT: 'Incorrect CTE usage.',
		FEEDBACK_CTE_SOLUTION:
			'Expected CTEs: [{{expected}}], got: [{{received}}].',
		FEEDBACK_LIMIT_MISSING: 'LIMIT clause is missing.',
		FEEDBACK_LIMIT_MISSING_SOLUTION: 'The query should include a LIMIT clause.',
		FEEDBACK_LIMIT_EXTRA: 'LIMIT clause should not be present in this query.',
		FEEDBACK_LIMIT_EXTRA_SOLUTION: 'Remove the LIMIT clause from the query.',
		FEEDBACK_WINDOW_MISSING: 'Window function (OVER) is missing.',
		FEEDBACK_WINDOW_MISSING_SOLUTION:
			'The query should use a window function with OVER.',
		FEEDBACK_WINDOW_EXTRA:
			'Window function (OVER) should not be used in this query.',
		FEEDBACK_WINDOW_PARTITION: 'Incorrect PARTITION BY in window function.',
		FEEDBACK_WINDOW_PARTITION_SOLUTION:
			'Expected PARTITION BY: [{{expected}}], got: [{{received}}].',
		FEEDBACK_WINDOW_ORDER_BY: 'Incorrect ORDER BY in window function.',
		FEEDBACK_WINDOW_ORDER_BY_SOLUTION:
			'Expected window ORDER BY: [{{expected}}], got: [{{received}}].',
		FEEDBACK_SUBQUERY_COUNT:
			'Incorrect number of subqueries: expected {{expected}}, got {{received}}.',
		FEEDBACK_SUBQUERY_COUNT_SOLUTION_SINGULAR:
			'The query should contain exactly {{count}} subquery.',
		FEEDBACK_SUBQUERY_COUNT_SOLUTION_PLURAL:
			'The query should contain exactly {{count}} subqueries.',
		FEEDBACK_SUBQUERY_TYPE:
			'In {{context}}: expected a {{expected}}, got a {{received}}.',
		// grading feedback — task description
		FEEDBACK_TASK_DESCRIPTION:
			'Your query solves the task with the following description:',
		// description
		DESCRIPTION_MISSING_QUERY: 'Missing or empty query string.',
		DESCRIPTION_PARSE_FAILED: 'Failed to parse SQL query: {{value}}',
		DESCRIPTION_TEMPLATE_FAILED:
			'Error in template description generation: {{value}}',
		DESCRIPTION_LLM_DEFAULT_FAILED:
			'Error in LLM default description generation: {{value}}',
		DESCRIPTION_LLM_CREATIVE_FAILED:
			'Error in LLM creative description generation: {{value}}',
		DESCRIPTION_LLM_MULTISTEP_FAILED:
			'Error in LLM multi-step description generation: {{value}}',
		DESCRIPTION_HYBRID_FAILED:
			'Error in hybrid description generation: {{value}}',
		// task generation
		TASK_GENERATION_INVALID_REQUEST: 'Invalid request information.',
		TASK_GENERATION_INVALID_CONNECTION: 'Invalid connection information.',
		TASK_GENERATION_QUERY_ERROR:
			'Error in query generation, please try again. {{value}}',
		TASK_GENERATION_DESCRIPTION_ERROR:
			'Error in task description generation, please try again.',
	},

	de: {
		// shared
		INVALID_REQUEST_BODY: 'Ungültiger Anfrage-Body.',
		MISSING_CONNECTION_INFO: 'Verbindungsinformationen fehlen.',
		INVALID_CONNECTION_INFO: 'Ungültige Verbindungsinformationen.',
		UNABLE_TO_CONNECT: 'Verbindung zur Datenbank nicht möglich.',
		DATABASE_NOT_REGISTERED:
			'Datenbank nicht registriert. Bitte zunächst eine Datenbankanalyse auslösen.',
		// database controller
		DATABASE_ANALYSIS_SUCCESS: 'Verbindung erfolgreich.',
		DATABASE_SCHEMA_EXTRACTION_FAILED:
			'Das Datenbankschema konnte nicht extrahiert werden.',
		INIT_SQL_READ_ERROR:
			'Das Initialisierungsskript der Datenbank konnte nicht gelesen werden.',

		// query execution
		MISSING_OR_EMPTY_QUERY: 'Abfragezeichenkette fehlt oder ist leer.',
		QUERY_EMPTY: 'Die Abfrage darf nicht leer sein.',
		QUERY_PARSE_ERROR:
			'Die Eingabe konnte nicht als SQL-Abfrage analysiert werden.',
		QUERY_MULTIPLE_STATEMENTS:
			'Pro Anfrage ist nur eine einzelne SELECT-Anweisung erlaubt.',
		QUERY_NON_SELECT:
			'Nur SELECT-Abfragen sind zulässig. Empfangener Anweisungstyp: "{{value}}".',
		QUERY_EXECUTION_FAILED: 'Abfrageausführung fehlgeschlagen: {{value}}',
		QUERY_UNEXPECTED_ERROR: 'Unerwarteter Fehler: {{value}}',
		// grading
		GRADING_READ_ERROR: 'Fehler beim Lesen der Aufgabenkonfiguration.',
		GRADING_CONNECTION_READ_ERROR:
			'Fehler beim Lesen der Verbindungsinformationen.',
		GRADING_FAILED: 'Die Abfrage konnte nicht bewertet werden.',
		GRADING_FAILED_WITH_ERROR:
			'Die Abfrage konnte nicht bewertet werden. Fehler: {{value}}',
		// grading feedback — result set
		FEEDBACK_RESULT_SET_MATCH: 'Beide Abfragen liefern dasselbe Ergebnis.',
		FEEDBACK_RESULT_SET_MISMATCH: 'Die Ergebnismengen stimmen nicht überein.',
		// grading feedback — executability
		FEEDBACK_QUERY_NOT_EXECUTABLE: 'Die Abfrage ist nicht ausführbar.',
		FEEDBACK_QUERY_EXECUTION_ERROR:
			'Die Abfrage ist aufgrund des folgenden Syntaxfehlers nicht ausführbar:',
		FEEDBACK_QUERY_COMPARISON_ERROR:
			'Abfragevergleich konnte nicht durchgeführt werden: {{value}}',
		// grading feedback — AST parsing
		FEEDBACK_AST_ARRAY_UNSUPPORTED: 'AST-Array wird nicht unterstützt.',
		FEEDBACK_AST_PARSE_FAILED: 'AST-Analyse fehlgeschlagen.',
		FEEDBACK_AST_NOT_SELECT: 'Fehler: Keine SELECT-Anweisung.',
		FEEDBACK_SQL_CLAUSE_TYPE:
			'Falsche SQL-Klausel, die Aufgabe erfordert eine Klausel vom Typ: {{value}}',
		// grading feedback — columns
		FEEDBACK_COLUMNS_WRONG_COUNT: 'Falsche Anzahl an ausgewählten Spalten.',
		FEEDBACK_COLUMNS_INCORRECT: 'Falsche Spalten ausgewählt.',
		FEEDBACK_COLUMNS_MESSAGE: 'Die Spaltenauswahl ist falsch: {{value}}',
		FEEDBACK_COLUMNS_SOLUTION:
			'Die Aufgabe erfordert die Auswahl folgender Spalten: {{value}}',
		// grading feedback — LIMIT / OFFSET
		FEEDBACK_LIMIT_INCORRECT: 'Falscher LIMIT-Wert.',
		FEEDBACK_LIMIT_SOLUTION:
			'Erwartet LIMIT {{expected}}, erhalten {{received}}.',
		FEEDBACK_OFFSET_INCORRECT: 'Falscher OFFSET-Wert.',
		FEEDBACK_OFFSET_SOLUTION:
			'Erwartet OFFSET {{expected}}, erhalten {{received}}.',
		// grading feedback — JOIN
		FEEDBACK_JOIN_COUNT_WRONG:
			'Falsche JOIN-Anweisung: Die Abfrage enthält nicht die richtige Anzahl an JOINs.',
		FEEDBACK_JOIN_WRONG_TABLE:
			'Falsche JOIN-Anweisung: Die Abfrage verwendet eine falsche Tabelle in der JOIN-Anweisung.',
		FEEDBACK_JOIN_WRONG_TYPE:
			'Falsche JOIN-Anweisung: Die Abfrage verwendet einen falschen JOIN-Typ.',
		FEEDBACK_JOIN_WRONG_CONDITION:
			'Falsche JOIN-Anweisung: Die Abfrage verwendet eine falsche JOIN-Bedingung.',
		FEEDBACK_JOIN_SOLUTION_EXPECTED: 'Erwartet: {{value}}',
		FEEDBACK_JOIN_SOLUTION_RECEIVED: 'Erhalten: {{value}}',
		FEEDBACK_JOIN_EXTRA: 'Unerwartete JOIN-Anweisung vorhanden.',
		FEEDBACK_JOIN_MISSING: 'JOIN-Anweisung fehlt.',
		// grading feedback — execution plan
		FEEDBACK_PLAN_RETRIEVAL_FAILED:
			'Ausführungspläne konnten nicht abgerufen werden.',
		FEEDBACK_PLAN_PARSE_FAILED:
			'Ausführungspläne konnten nicht analysiert werden.',
		FEEDBACK_GROUP_KEY: 'Falscher GROUP BY-Schlüssel.',
		FEEDBACK_GROUP_KEY_SOLUTION:
			'Erwartet {{expected}}, erhalten {{received}}.',
		FEEDBACK_HAVING: 'Falscher HAVING-Filter.',
		FEEDBACK_HAVING_SOLUTION: 'Erwartet {{expected}}, erhalten {{received}}.',
		FEEDBACK_ORDER_BY: 'Falscher ORDER BY-Sortierschlüssel.',
		FEEDBACK_ORDER_BY_SOLUTION: 'Erwartet {{expected}}, erhalten {{received}}.',
		FEEDBACK_WHERE: 'Falscher WHERE-Filter.',
		FEEDBACK_WHERE_SOLUTION: 'Erwartet {{expected}}, erhalten {{received}}.',
		FEEDBACK_DISTINCT_MISSING:
			'Das Schlüsselwort DISTINCT fehlt in der Abfrage.',
		FEEDBACK_DISTINCT_MISSING_SOLUTION:
			'Die Abfrage sollte SELECT DISTINCT verwenden.',
		FEEDBACK_DISTINCT_EXTRA:
			'Das Schlüsselwort DISTINCT sollte in dieser Abfrage nicht verwendet werden.',
		FEEDBACK_DISTINCT_EXTRA_SOLUTION:
			'Die Abfrage sollte ein einfaches SELECT ohne DISTINCT verwenden.',
		FEEDBACK_DISTINCT_STRATEGY:
			'Hinweis: Unterschiedliche DISTINCT-Implementierungsstrategie (Student: {{student}}, Referenz: {{reference}}).',
		FEEDBACK_CTE_INCORRECT: 'Falsche CTE-Verwendung.',
		FEEDBACK_CTE_SOLUTION:
			'Erwartete CTEs: [{{expected}}], erhalten: [{{received}}].',
		FEEDBACK_LIMIT_MISSING: 'LIMIT-Klausel fehlt.',
		FEEDBACK_LIMIT_MISSING_SOLUTION:
			'Die Abfrage sollte eine LIMIT-Klausel enthalten.',
		FEEDBACK_LIMIT_EXTRA:
			'LIMIT-Klausel sollte in dieser Abfrage nicht vorhanden sein.',
		FEEDBACK_LIMIT_EXTRA_SOLUTION:
			'Entfernen Sie die LIMIT-Klausel aus der Abfrage.',
		FEEDBACK_WINDOW_MISSING: 'Fensterfunktion (OVER) fehlt.',
		FEEDBACK_WINDOW_MISSING_SOLUTION:
			'Die Abfrage sollte eine Fensterfunktion mit OVER verwenden.',
		FEEDBACK_WINDOW_EXTRA:
			'Fensterfunktion (OVER) sollte in dieser Abfrage nicht verwendet werden.',
		FEEDBACK_WINDOW_PARTITION: 'Falsches PARTITION BY in der Fensterfunktion.',
		FEEDBACK_WINDOW_PARTITION_SOLUTION:
			'Erwartetes PARTITION BY: [{{expected}}], erhalten: [{{received}}].',
		FEEDBACK_WINDOW_ORDER_BY: 'Falsches ORDER BY in der Fensterfunktion.',
		FEEDBACK_WINDOW_ORDER_BY_SOLUTION:
			'Erwartetes Fenster-ORDER BY: [{{expected}}], erhalten: [{{received}}].',
		FEEDBACK_SUBQUERY_COUNT:
			'Falsche Anzahl an Unterabfragen: erwartet {{expected}}, erhalten {{received}}.',
		FEEDBACK_SUBQUERY_COUNT_SOLUTION_SINGULAR:
			'Die Abfrage sollte genau {{count}} Unterabfrage enthalten.',
		FEEDBACK_SUBQUERY_COUNT_SOLUTION_PLURAL:
			'Die Abfrage sollte genau {{count}} Unterabfragen enthalten.',
		FEEDBACK_SUBQUERY_TYPE:
			'In {{context}}: erwartet ein {{expected}}, erhalten ein {{received}}.',
		// grading feedback — task description
		FEEDBACK_TASK_DESCRIPTION:
			'Ihre Abfrage löst die Aufgabe mit der folgenden Beschreibung:',
		// description
		DESCRIPTION_MISSING_QUERY: 'Abfragezeichenkette fehlt oder ist leer.',
		DESCRIPTION_PARSE_FAILED:
			'SQL-Abfrage konnte nicht analysiert werden: {{value}}',
		DESCRIPTION_TEMPLATE_FAILED:
			'Fehler bei der Template-basierten Beschreibungsgenerierung: {{value}}',
		DESCRIPTION_LLM_DEFAULT_FAILED:
			'Fehler bei der Standard-LLM-Beschreibungsgenerierung: {{value}}',
		DESCRIPTION_LLM_CREATIVE_FAILED:
			'Fehler bei der kreativen LLM-Beschreibungsgenerierung: {{value}}',
		DESCRIPTION_LLM_MULTISTEP_FAILED:
			'Fehler bei der mehrstufigen LLM-Beschreibungsgenerierung: {{value}}',
		DESCRIPTION_HYBRID_FAILED:
			'Fehler bei der hybriden Beschreibungsgenerierung: {{value}}',
		// task generation
		TASK_GENERATION_INVALID_REQUEST: 'Ungültige Anfrageinformationen.',
		TASK_GENERATION_INVALID_CONNECTION: 'Ungültige Verbindungsinformationen.',
		TASK_GENERATION_QUERY_ERROR:
			'Fehler bei der Abfragegenerierung, bitte erneut versuchen. {{value}}',
		TASK_GENERATION_DESCRIPTION_ERROR:
			'Fehler bei der Aufgabenbeschreibungsgenerierung, bitte erneut versuchen.',
	},
};
