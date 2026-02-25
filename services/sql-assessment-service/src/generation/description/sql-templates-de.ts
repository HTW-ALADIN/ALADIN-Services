export const SQL_TEMPLATES_DE: { [key: string]: string } = {
    // -------------------------------------------------------------------------
    // SELECT — einfach (ohne JOIN)
    // -------------------------------------------------------------------------
    "SELECT_ALL": "Rufe alle Informationen über {table} aus der {database}-Datenbank ab.",
    "SELECT_COLUMNS": "Rufe {columns} aus der {database}-Datenbank ab.",
    /** DISTINCT-Varianten — werden verwendet, wenn SELECT DISTINCT vorhanden ist */
    "SELECT_DISTINCT_COLUMNS": "Rufe eindeutige {columns} aus der {database}-Datenbank ab.",

    // -------------------------------------------------------------------------
    // SELECT — mit JOIN
    // -------------------------------------------------------------------------
    "SELECT_ALL_JOIN": "Rufe alle Informationen über die folgende Datenkombination aus der {database}-Datenbank ab.",
    "SELECT_COLUMNS_JOIN": "Rufe {columns} aus der folgenden Datenkombination in der {database}-Datenbank ab.",
    /** DISTINCT-Variante für JOIN-Abfragen */
    "SELECT_DISTINCT_COLUMNS_JOIN": "Rufe eindeutige {columns} aus der folgenden Datenkombination in der {database}-Datenbank ab.",

    // -------------------------------------------------------------------------
    // Strukturwörter, die inline von der Engine verwendet werden
    // -------------------------------------------------------------------------
    /**
     * Bestimmter Artikel vor einem Tabellen- oder Spaltennamen.
     * Im Deutschen wird der Artikel weggelassen, da das grammatikalische
     * Geschlecht nicht automatisch bestimmt werden kann.
     */
    "COLUMN_PREFIX": "",
    /** Verbindungswort zum Verbinden von zwei Elementen in einer Spaltenliste. */
    "AND_JOINER": "und",
    /** Sortierrichtungslabel für ASC. */
    "ORDER_ASC": "aufsteigend",
    /** Sortierrichtungslabel für DESC. */
    "ORDER_DESC": "absteigend",
    /** Strukturwörter für CASE-Ausdrücke. */
    "CASE_WHEN": "wenn",
    "CASE_THEN": "dann",
    "CASE_ELSE": "sonst",

    // -------------------------------------------------------------------------
    // Boolesche Operatoren (werden beim Kombinieren von WHERE- / HAVING-Teilbedingungen verwendet)
    // -------------------------------------------------------------------------
    "AND": "{left} und {right}",
    "OR": "{left} oder {right}",

    // -------------------------------------------------------------------------
    // JOIN-Typen
    // -------------------------------------------------------------------------
    "SELF_JOIN": "Verknüpfe Datensätze innerhalb der {table}-Tabelle, bei denen {condition}.",
    "INNER_JOIN": "Kombiniere die Daten aus der {table1}-Tabelle und der {table2}-Tabelle.",
    "LEFT_JOIN": "Schließe alle Daten aus der {table1}-Tabelle sowie die übereinstimmenden Daten aus der {table2}-Tabelle ein.",
    "RIGHT_JOIN": "Schließe alle Daten aus der {table2}-Tabelle sowie die übereinstimmenden Daten aus der {table1}-Tabelle ein.",
    "FULL_JOIN": "Schließe alle Datensätze aus der {table1}-Tabelle und der {table2}-Tabelle ein.",
    "CROSS_JOIN": "Kombiniere jeden Datensatz aus der {table1}-Tabelle mit jedem Datensatz aus der {table2}-Tabelle.",
    /**
     * Wird verwendet, wenn eine schwache oder assoziative Entität in einer JOIN-Kette übersprungen wird.
     * Die beiden Platzhalter repräsentieren die flankierenden starken Entitäten.
     */
    "WEAK_BRIDGE": "Rufe {table2}-Daten ab, die zu jedem {table1} gehören.",

    // -------------------------------------------------------------------------
    // Aggregatfunktionen
    // -------------------------------------------------------------------------
    "AVG": "der Durchschnitt von {column}",
    "SUM": "die Summe von {column}",
    "COUNT": "die Anzahl von {column}",
    "MAX": "das Maximum von {column}",
    "MIN": "das Minimum von {column}",

    // -------------------------------------------------------------------------
    // Vergleichs- / Prädikatoperatoren
    // -------------------------------------------------------------------------
    "=": "{left} ist gleich {right}",
    ">": "{left} ist größer als {right}",
    "<": "{left} ist kleiner als {right}",
    ">=": "{left} ist größer als oder gleich {right}",
    "<=": "{left} ist kleiner als oder gleich {right}",
    "!=": "{left} ist ungleich {right}",
    "LIKE": "{left} entspricht dem Muster {right}",
    "NOT LIKE": "{left} entspricht nicht dem Muster {right}",
    "IN": "{left} ist eines von {right}",
    "NOT IN": "{left} ist keines von {right}",
    "BETWEEN": "{left} liegt zwischen {right}",
    "IS NULL": "{left} ist nicht definiert",
    "IS NOT NULL": "{left} ist definiert",
    "IS": "{left} ist {right}",
    "IS NOT": "{left} ist nicht {right}",

    // -------------------------------------------------------------------------
    // Teilabfrage-Existenzprädikate
    // -------------------------------------------------------------------------
    "EXISTS": "es gibt einen zugehörigen Datensatz, bei dem {condition}",
    "NOT_EXISTS": "es gibt keinen zugehörigen Datensatz, bei dem {condition}",

    // -------------------------------------------------------------------------
    // CASE-Ausdruck (in der SELECT-Spaltenliste)
    // -------------------------------------------------------------------------
    "CASE": "ein bedingter Wert basierend auf {conditions}",

    // -------------------------------------------------------------------------
    // Klauseln, die auf den FROM- / JOIN-Block folgen
    // -------------------------------------------------------------------------
    "WHERE": "Filtere die Ergebnisse, bei denen {condition}.",
    "GROUP_BY": "Gruppiere die Ergebnisse nach {columns}.",
    "HAVING": "Filtere die gruppierten Ergebnisse, bei denen {condition}.",
    "ORDER_BY": "Sortiere die Ergebnisse nach {columns}.",

    // -------------------------------------------------------------------------
    // LIMIT / OFFSET
    // -------------------------------------------------------------------------
    "LIMIT": "Begrenze die Ergebnisse auf {count} Datensatz/Datensätze.",
    "OFFSET": "Überspringe die ersten {count} Datensatz/Datensätze.",
    "LIMIT_OFFSET": "Begrenze die Ergebnisse auf {count} Datensatz/Datensätze, beginnend ab Datensatz {offset}.",

    // -------------------------------------------------------------------------
    // Mengenoperationen — verkettet über node._next im AST
    // -------------------------------------------------------------------------
    "UNION": "{left} Rufe zusätzlich ab: {right}",
    "UNION_ALL": "{left} Rufe zusätzlich ab (einschließlich Duplikaten): {right}",
    "INTERSECT": "{left} Schließe nur Ergebnisse ein, die auch vorkommen in: {right}",
    "EXCEPT": "{left} Ausgenommen Ergebnisse, die vorkommen in: {right}",
};
