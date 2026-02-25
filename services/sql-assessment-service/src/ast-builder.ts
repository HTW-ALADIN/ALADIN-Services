import { AST } from 'node-sql-parser';

export interface ASTBuilder {
  getGeneratedAST(): AST;
}
