import { AST, BaseFrom, Binary, Column, ColumnRefItem, From, Join, Select } from "node-sql-parser";
import { SQL_TEMPLATES } from "./sql-templates";

export class TemplateTaskDescriptionGenerationEngine {

    private readonly columnPattern = /([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)/g;
    private readonly aggregateFunctionPattern = /(MAX|MIN|SUM|AVG|COUNT)\((.*?)\)/i;

    public generateTaskFromQuery(query: AST, schema: string): string {
        return this.traverseAST(query, schema);
    }

    private traverseAST(node: AST, schema: string): string {
        if (!node) return '';

        switch (node.type) {
            case 'select':
                return this.handleSelect(node, schema);
            default:
                return 'Unsupported query type.';
        }
    }

    private handleSelect(node: Select, schema: string): string {
        let result = '';
        const isSelectAll = node.columns.length === 1 && node.columns[0].expr?.column === '*';

        if (Array.isArray(node.from)) {
            if ((node.from as Join[]).some(fromItem => fromItem?.join)) {
                let baseTable = this.formatName((node.from[0] as BaseFrom)?.table || 'an unknown table');

                const columns = isSelectAll
                    ? '*'
                    : node.columns.map((col: any) => this.getColumnName(col.expr)).join(' and ');

                result += isSelectAll
                    ? SQL_TEMPLATES.SELECT_ALL_JOIN.replace('{database}', schema)
                    : SQL_TEMPLATES.SELECT_COLUMNS_JOIN.replace('{columns}', columns).replace('{database}', schema);

                (node.from as Join[]).forEach((join: Join) => {
                    if (join.join) {
                        const joinType = join.join.toUpperCase();
                        let joinTemplate;
                        let useAlias = false;
                        if (baseTable == this.formatName(join.table)) {
                            joinTemplate = SQL_TEMPLATES.SELF_JOIN;
                            useAlias = true;
                        }
                        else joinTemplate = this.getJoinTemplate(joinType);

                        const condition: Binary | undefined = join.on;

                        result += ' ' + joinTemplate
                            .replace('{table1}', baseTable)
                            .replace('{table}', baseTable)
                            .replace('{table2}', this.formatName(join.table) || 'another_table')
                            .replace('{condition}', this.handleJoinCondition(condition));
                        baseTable = this.formatName(join.table);
                    }
                });
            }
            else if ((node.from as BaseFrom[]).every(fromItem => fromItem?.table)) {
                const table = (node.from[0] as BaseFrom)?.table || 'an unknown table';

                const columns = isSelectAll
                    ? '*'
                    : node.columns.map((col: any) => this.getColumnName(col.expr)).join(' and ');

                result += isSelectAll
                    ? SQL_TEMPLATES.SELECT_ALL.replace('{table}', this.formatName(table)).replace('{database}', schema)
                    : SQL_TEMPLATES.SELECT_COLUMNS.replace('{columns}', columns).replace('{table}', this.formatName(table)).replace('{database}', schema);

            }
            else {
                result += 'Unsupported FROM clause structure.';
            }
        }
        else {
            result += 'Invalid FROM clause.';
        }

        if (node.where) {
            const condition = this.handleCondition(node.where);
            result += ' ' + SQL_TEMPLATES.WHERE.replace('{condition}', condition);
        }

        if (node.groupby && node.groupby.columns && node.groupby.columns.length > 0) {
            const groupByColumns = node.groupby.columns
                ? node.groupby.columns.map((col: any) => this.getColumnName(col)).join(', ')
                : '';
            result += ' ' + SQL_TEMPLATES.GROUP_BY.replace('{columns}', groupByColumns);
        }

        if (node.having) {
            const havingCondition = this.handleCondition(node.having);
            result += ' ' + SQL_TEMPLATES.HAVING.replace('{condition}', havingCondition);
        }

        if (node.orderby) {
            const orderByColumns = node.orderby.map((col: any) => {
                const columnName = this.getColumnName(col.expr);
                const orderType = col.type?.toUpperCase() === 'DESC' ? 'descending' : 'ascending';
                return `${columnName} in ${orderType} order`;
            }).join(', ');

            result += ' ' + SQL_TEMPLATES.ORDER_BY.replace('{columns}', orderByColumns);
        }

        return result;
    }

    private handleJoinCondition(on: string | any): string {
        let left, operator, right;
        if (typeof on === 'string') {
            [left, operator, right] = this.parseConditionString(on);
        } else if (on?.operator) {
            left = on.left;
            right = on.right;
            operator = on.operator;
        }
        else {
            return 'an unspecified condition';
        }
        const operatorTemplate = SQL_TEMPLATES[operator] || `{left} ${operator} {right}`;
        const formattedLeft = this.getColumnName(left);
        let formattedRight = right?.value || this.getColumnName(right);

        return operatorTemplate
            .replace('{left}', formattedLeft)
            .replace('{right}', formattedRight);
    }

    private handleCondition(condition: any): string {
        if (!condition) return 'an unspecified condition';

        if (condition.operator && (condition.operator === 'AND' || condition.operator === 'OR')) {
            const left = this.handleCondition(condition.left);
            const right = this.handleCondition(condition.right);
            const operatorTemplate = SQL_TEMPLATES[condition.operator.toUpperCase()] || `{left} ${condition.operator} {right}`;
            return operatorTemplate.replace('{left}', left).replace('{right}', right);
        }

        if (condition.type === 'binary_expr') {
            if (['IS', 'IS NOT'].includes(condition.operator)) {
                if (condition.right.type == 'null') {
                    const operatorTemplate = SQL_TEMPLATES[`${condition.operator} NULL`];
                    const left = this.getColumnName(condition.left);
                    return operatorTemplate.replace('{left}', left);
                }
            }

            const operatorTemplate = SQL_TEMPLATES[condition.operator] || `{left} ${condition.operator} {right}`;
            const left = this.getColumnName(condition.left);
            let right = condition.right?.value || this.getColumnName(condition.right);

            if (condition.operator === 'BETWEEN' && Array.isArray(condition.right.value)) {
                right = `${condition.right.value[0].value} and ${condition.right.value[1].value}`;
            }

            if (condition.operator === 'IN' && Array.isArray(condition.right.value)) {
                right = condition.right.value.map((item: any) => item.value).join(', ');
            }

            return operatorTemplate
                .replace('{left}', left)
                .replace('{right}', right);
        }



        return 'an unspecified condition';
    }

    private parseConditionString(condition: string): [ColumnRefItem, string, ColumnRefItem] {
        const operators = ['=', '!=', '<', '>', '<=', '>=', 'LIKE', 'IN', 'BETWEEN', 'NOT LIKE', 'NOT IN'];

        let operator: string | null = null;
        for (const op of operators) {
            if (condition.includes(op)) {
                operator = op;
                break;
            }
        }

        if (!operator) {
            throw new Error('No valid operator found in condition');
        }

        const [left, right] = condition.split(operator).map(part => part.trim());

        const parseColumn = (columnString: string): ColumnRefItem => {
            const match = columnString.match(/^([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)$/);
            if (match) {
                return { table: match[1], column: match[2], type: "column_ref" };
            }
            return { table: '', column: columnString, type: "column_ref" };
        };

        const leftColumn = parseColumn(left);
        const rightColumn = parseColumn(right);

        return [leftColumn, operator, rightColumn];
    }

    private getColumnName(column: any): string {
        if (!column) return 'unknown column';

        if (column.type === 'aggr_func') {
            const func = column.name?.toUpperCase();
            const arg = column.args?.expr;

            if (func && arg) {
                const aggTemplate = SQL_TEMPLATES[func.toUpperCase()] || func.toLowerCase();
                let column = typeof (arg.column) === "string" ? arg.column : arg.column.expr.value;
                return aggTemplate.replace('{column}', this.formatName(column || 'unknown column', func));
            }
        }

        if (column.column) {
            if (typeof column.column === 'string') {
                let tablePart = column.table ? `the ${this.formatName(column.table)} ` : '';
                let columnPart = this.formatName(column.column);
                return `${tablePart}${columnPart}`;
            }
            else if (column.column.expr) {
                let tablePart = column.table ? `the ${this.formatName(column.table)} ` : '';
                let columnPart = this.formatName(column.column.expr.value);
                return `${tablePart}${columnPart}`;
            }
        }

        if (column.type == 'bool') {
            return column.value;
        }

        return 'unavailable';
    }

    private pluralize(name: string): string {
        if (name.endsWith('s')) return name;
        return `${name}s`;
    }

    private formatName(column: string, aggregation?: string): string {
        let formattedColumn = column.replace(/_/g, ' ').replace(/-/g, ' ').replace(/(\w+)id$/i, '$1 id');
        if (aggregation && (aggregation === 'COUNT' || aggregation === 'SUM' || aggregation === 'AVG'))
            return this.pluralize(formattedColumn);
        return this.separateWords(formattedColumn);
    }

    private separateWords(str: string) {
        const regex = /([a-z0-9])([A-Z])|([_-])([a-zA-Z0-9])/g;
        return str.replace(regex, (match, p1, p2, p3, p4) => {
            if (p1 && p2) {
                return p1 + ' ' + p2;
            }
            if (p3 && p4) {
                return ' ' + p4;
            }
            return 'match';
        }).toLowerCase();
    }

    private getJoinTemplate(joinType: string): string {
        switch (joinType) {
            case 'INNER JOIN': return SQL_TEMPLATES.INNER_JOIN;
            case 'JOIN': return SQL_TEMPLATES.INNER_JOIN;
            case 'LEFT JOIN': return SQL_TEMPLATES.LEFT_JOIN;
            case 'RIGHT JOIN': return SQL_TEMPLATES.RIGHT_JOIN;
            case 'FULL JOIN': return SQL_TEMPLATES.FULL_JOIN;
            case 'SELF JOIN': return SQL_TEMPLATES.SELF_JOIN;
            case 'CROSS JOIN': return SQL_TEMPLATES.CROSS_JOIN;
            default: return 'Perform an unspecified join.';
        }
    }

}