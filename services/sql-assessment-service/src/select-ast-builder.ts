import {
  AST,
  Select,
  Join,
  Column,
  Function,
  Expr,
  ExpressionValue,
  ExprList,
  ColumnRef,
  ValueExpr,
  ColumnRefItem
} from 'node-sql-parser';
import { ASTBuilder } from './ast-builder';
import { IParsedColumn, IJoinPaths, IPath, aggregateTypes, joinType, joinTypes, randomJoinTypes } from './interfaces';
import { random, randomBoolean } from './helper-functions';

export class SelectASTBuilder implements ASTBuilder {
  private generatedAST: Select;
  private aliasedTables: string[] = [];

  constructor() {
    this.generatedAST = {
      type: 'select',
      columns: [],
      distinct: null,
      from: null,
      groupby: { columns: [], modifiers: [] },
      having: null,
      limit: null,
      options: null,
      orderby: null,
      where: null,
      with: null,
    };
  }

  buildSelect(selectColumns: IParsedColumn[], isGroupBy = false) {
    const columnArray: any[] = [];
    selectColumns.forEach(column => {
      if (column.aggregation)
        columnArray.push({
          expr: {
            type: 'aggr_func',
            name: column.aggregation,
            args: {
              expr: {
                type: 'column_ref',
                table: (isGroupBy && this.generatedAST?.groupby?.columns?.length && this.generatedAST?.groupby?.columns?.length > 0) ? (this.generatedAST?.groupby?.columns[0] as ColumnRefItem).table : this.getAlias(column.tableName),
                column: column.name,
              },
            },
          },
        });
      else
        columnArray.push({
          expr: {
            type: 'column_ref',
            table: (isGroupBy && this.generatedAST?.groupby?.columns?.length && this.generatedAST?.groupby?.columns?.length > 0) ? (this.generatedAST?.groupby?.columns[0] as ColumnRefItem).table : this.getAlias(column.tableName),
            column: column.name,
          },
        });
    });
    this.generatedAST.columns = columnArray;
  }

  buildSelectAll() {
    this.generatedAST.columns = [
      { expr: { type: 'column_ref', table: null, column: '*' } },
    ];
  }

  buildFromWithJoin(
    schema: string,
    tableName: string,
    joinPath: IPath[],
    configuredJoinTypes: joinType[],
    depth: number
  ) {
    const join = [];
    const otherJoins = configuredJoinTypes.filter((val) => val !== 'SELF JOIN');
    let isFromSelfJoin = false;
    let isPreviousSelfJoin;
    for (let i = 0; i < depth; i++) {
      const currentTable = joinPath[i].tableName;
      const previousTable = joinPath[i - 1]?.tableName;
      const nextTable = joinPath[i + 1]?.tableName;
      if (!isFromSelfJoin)
        isFromSelfJoin = currentTable == tableName;
      const isSelfJoin = currentTable === previousTable || currentTable == tableName || currentTable == nextTable;
      let currentAlias = currentTable == tableName || currentTable == previousTable ? 2 : 1;
      if (isSelfJoin) {
        if (!this.aliasedTables.includes(currentTable))
          this.aliasedTables.push(currentTable);
      }
      let joinType = otherJoins.pop() || randomJoinTypes[random(randomJoinTypes.length)];

      join.push({
        db: schema,
        table: currentTable,
        as: isSelfJoin ? `${currentTable.charAt(0)}${currentAlias}` : null,
        join: joinType,
        on: joinType == 'CROSS JOIN' ? null : isSelfJoin ? this.getRelationKeyWithAlias(joinPath[i].relationKey, currentTable) : isPreviousSelfJoin ? this.getRelationKeyWithPreviousAlias(joinPath[i].relationKey, previousTable) : joinPath[i].relationKey
      });
      isPreviousSelfJoin = isSelfJoin;
    }

    const from = [
      {
        db: schema,
        table: tableName,
        as: isFromSelfJoin ? `${tableName.charAt(0)}1` : null,
      },
      ...join,
    ];
    this.generatedAST.from = from;
  }

  private buildConjuctedWhere(expressionList: Expr[]): any {
    if (expressionList.length == 1) {
      return expressionList[0];
    }

    return {
      type: 'binary_expr',
      operator: randomBoolean() ? 'AND' : 'OR',
      left: expressionList.shift(),
      right: this.buildConjuctedWhere(expressionList),
    };
  }

  buildWhere(expressionList: Expr[]) {
    if (expressionList.length == 0) return;
    if (expressionList.length == 1) this.generatedAST.where = expressionList[0];
    else this.generatedAST.where = this.buildConjuctedWhere(expressionList);
  }

  buildWhereConstraint(
    operator: string,
    tableName: string,
    columnName: string,
    valueType: string,
    val: any
  ): Expr {
    return {
      type: 'binary_expr',
      operator: operator,
      left: { type: 'column_ref', table: this.getAlias(tableName), column: columnName },
      right: { type: valueType, value: val },
    };
  }

  buildWhereConstraintValueList(
    operator: string,
    tableName: string,
    columnName: string,
    values: any[]
  ): Expr {
    const valueList: ExpressionValue[] = [];
    values.forEach(value => {
      valueList.push({ type: value.type, value: value.value });
    });

    const exprList: ExprList = { type: 'expr_list', value: valueList };
    return {
      type: 'binary_expr',
      operator: operator,
      left: { type: 'column_ref', table: this.getAlias(tableName), column: columnName },
      right: exprList,
    };
  }

  buildFrom(schema: string, tableName: string) {
    const from = [
      {
        db: schema,
        table: tableName,
        as: null,
      },
    ];
    this.generatedAST.from = from;
  }

  buildHaving(
    operator: string,
    aggregateType: string,
    tableName: string,
    columnName: string,
    val: any,
    type: string
  ) {
    this.generatedAST.having = {
      type: 'binary_expr',
      operator: operator,
      left: {
        type: 'aggr_func',
        name: aggregateType,
        args: {
          expr: { type: 'column_ref', table: this.getAlias(tableName), column: columnName },
        },
      },
      right: { type: type, value: val }
    } as any;
  }

  buildGroupBy(tableName: string, columnName: string) {
    this.generatedAST.groupby =
    {
      columns: [{ type: 'column_ref', table: this.getAlias(tableName), column: columnName }
      ],
      modifiers: []
    };
  }

  buildOrderBy(
    orderType: 'ASC' | 'DESC',
    tableName: string,
    columnName: string
  ) {
    this.generatedAST.orderby = [
      {
        type: orderType,
        expr: { type: 'column_ref', table: this.getAlias(tableName), column: columnName },
      },
    ];
  }

  buildAggregatedOrderByClause(
    orderType: 'ASC' | 'DESC',
    tableName: string,
    columnName: string,
    aggregateType: string
  ) {
    this.generatedAST.orderby = [
      {
        type: orderType,
        expr: {
          type: 'aggr_func',
          name: aggregateType,
          args: {
            expr: { type: 'column_ref', table: this.getAlias(tableName), column: columnName },
          },
        },
      },
    ];
  }

  getGeneratedAST(): Select {
    return this.generatedAST;
  }

  private getRelationKeyWithAlias(relationKey: string, tableName: string) {

    const alias1 = `${tableName.charAt(0)}${1}`;
    const alias2 = `${tableName.charAt(0)}${2}`;

    let count = 0;
    return relationKey.replace(
      new RegExp(`\\b${tableName}\\.`, 'g'),
      () => ++count === 1 ? `${alias1}.` : `${alias2}.`
    );
  }


  private getRelationKeyWithPreviousAlias(relationKey: string, previousTableName: string) {
    const alias = `${previousTableName.charAt(0)}${2}`;

    return relationKey.replace(
      new RegExp(`\\b${previousTableName}\\.`, 'g'),
      () => `${alias}.`
    );
  }

  getAlias(tableName: string) {
    if (this.aliasedTables.includes(tableName))
      return randomBoolean() ? `${tableName.charAt(0)}${1}` : `${tableName.charAt(0)}${2}`;
    return tableName;
  }
}
