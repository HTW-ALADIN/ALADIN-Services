
export const SQL_TEMPLATES: { [key: string]: string } = {
    "SELECT_ALL": "Retrieve all information about the {table} in the {database} database.",
    "SELECT_COLUMNS": "Retrieve {columns} in the {database} database.",
    "SELECT_ALL_JOIN": "Retrieve all information about the following data combination in the {database} database.",
    "SELECT_COLUMNS_JOIN": "Retrieve {columns} from the following data combination in the {database} database.",

    "AND": "{left} and {right}",
    "OR": "{left} or {right}",

    "SELF_JOIN": "Match records within the {table} table where {condition}.",
    "INNER_JOIN": "Combine the data from the {table1} table and the {table2} table.",
    "LEFT_JOIN": "Include all data from the {table1} table and the matching data from the {table2} table.",
    "RIGHT_JOIN": "Include all data from the {table2} table and the matching data from the {table1} table.",
    "FULL_JOIN": "Include all records from both the {table1} table and the {table2} table.",
    "CROSS_JOIN": "Combine each record from the {table1} table with each record from the {table2} table.",

    "AVG": "the average of {column}",
    "SUM": "the sum of {column}",
    "COUNT": "the number of {column}",
    "MAX": "the maximum {column}",
    "MIN": "the minimum {column}",

    "=": "{left} equals {right}",
    ">": "{left} is greater than {right}",
    "<": "{left} is less than {right}",
    ">=": "{left} is greater than or equal to {right}",
    "<=": "{left} is less than or equal to {right}",
    "!=": "{left} does not equal {right}",
    "LIKE": "{left} matches the pattern {right}",
    "NOT LIKE": "{left} does not match the pattern {right}",
    "IN": "{left} is one of {right}",
    "NOT IN": "{left} is not one of {right}",
    "BETWEEN": "{left} is between {right}",
    "IS NULL": "{left} is not defined",
    "IS NOT NULL": "{left} is defined",
    "IS": "{left} is {right}",
    "IS NOT": "{left} is not {right}",

    "WHERE": "Filter the results where {condition}.",
    "GROUP_BY": "Group the results based on the {columns}.",
    "HAVING": "Filter the grouped results where {condition}.",
    "ORDER_BY": "Sort the results by the {columns}.",
};