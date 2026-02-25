
// import { DataSource } from 'typeorm';
// import { DatabaseAnalyzer } from '../database-analyzer';
// import { QueryGradingService } from '../query-grading-service';
// import { AST, Parser } from 'node-sql-parser';


// // jest.mock('../internal-cache', () => {
// //     const mockedMap = {
// //         get: jest.fn((key: string) => {
// //             const map = new Map<string, string>([['123', 'SELECT "employee_territories"."employee_id" FROM "northwind"."employee_territories" INNER JOIN "northwind"."territories" ON employee_territories.territory_id = territories.territory_id INNER JOIN "northwind"."region" ON territories.region_id = region.region_id WHERE "territories"."territory_description" >= \'Boston\' OR "territories"."region_id" BETWEEN 4 AND 1 AND "region"."region_description" IN (\'Northern\', \'Eastern\', \'Western\', \'Southern\') GROUP BY "employee_territories"."employee_id" HAVING COUNT("region"."region_id") < 2 ORDER BY "employee_territories"."employee_id" ASC']]);
// //             return map.get(key);
// //         })
// //     };
// //     return { queryCache: mockedMap }
// // });

// import { connectToDatabase } from '../helper-functions';

// const referenceQuery = 'SELECT "employee_territories"."employee_id" FROM "northwind"."employee_territories" INNER JOIN "northwind"."territories" ON employee_territories.territory_id = territories.territory_id INNER JOIN "northwind"."region" ON territories.region_id = region.region_id WHERE "territories"."territory_description" >= \'Boston\' OR "territories"."region_id" BETWEEN 4 AND 1 AND "region"."region_description" IN (\'Northern\', \'Eastern\', \'Western\', \'Southern\') GROUP BY "employee_territories"."employee_id" HAVING COUNT("region"."region_id") < 2 ORDER BY "employee_territories"."employee_id" ASC';

// const PostgresDataSource = new DataSource({
//     type: 'postgres',
//     host: 'localhost',
//     port: 5444,
//     username: 'testUser',
//     password: 'abc124',
//     database: 'db',
//     schema: 'northwind',
// });

// const taskId = '123';

// beforeAll(async () => {
//     await connectToDatabase(PostgresDataSource);
// });


// afterAll(() => {
//     PostgresDataSource.destroy();
// });

// test('Non executable student query leads to grade 0', async () => {
//     const queryGradingService = new QueryGradingService();
//     const queryGrade = await queryGradingService.gradeQuery(
//         referenceQuery,
//         'Select * from "northwind"."territoies"',
//         PostgresDataSource,
//         ""
//     );
//     expect(queryGrade.grade).toBe(0);
// });

// // test('Dynamic check failed', async () => {
// //     const queryGradingService = new QueryGradingService();

// //     let test = queryCache.get(taskId);

// //     const queryGrade = await queryGradingService.gradeQuery(
// //         taskId,
// //         'Select "employees"."region" from "northwind"."employees" Order By "employees"."region" ASC',
// //         PostgresDataSource
// //     );
// //     expect(queryGrade.grade).toBe(0);
// // });

// test('Not same SQL clause', async () => {
//     const queryGradingService = new QueryGradingService();

//     const queryGrade = await queryGradingService.gradeQuery(
//         referenceQuery,
//         'SET search_path TO "northwind"',
//         PostgresDataSource,
//         ""
//     );
//     expect(queryGrade.grade).toBe(0);
// });

// // test('No Order in both returns true', () => {
// //     const queryGradingService = new QueryGradingService(PostgresDataSource);
// //     const parser = new Parser();
// //     let studentQuery = parser.astify('Select * from "northwind"."territories"', { database: 'postgresql' });
// //     let referenceQuery = parser.astify('Select * from "northwind"."territories"', { database: 'postgresql' });
// //     expect(queryGradingService.isSameOrder(studentQuery as AST, referenceQuery as AST)).toBe(true);
// // });

// // test('Order in only in student returns false', () => {
// //     const queryGradingService = new QueryGradingService(PostgresDataSource);
// //     const parser = new Parser();
// //     let studentQuery = parser.astify('Select * from "northwind"."territories" Order By "northwind"."territories" ASC', { database: 'postgresql' });
// //     let referenceQuery = parser.astify('Select * from "northwind"."territories"', { database: 'postgresql' });
// //     expect(queryGradingService.isSameOrder(studentQuery as AST, referenceQuery as AST)).toBe(false);
// // });

// // test('Order in only in reference returns false', () => {
// //     const queryGradingService = new QueryGradingService(PostgresDataSource);
// //     const parser = new Parser();
// //     let studentQuery = parser.astify('Select * from "northwind"."territories"', { database: 'postgresql' });
// //     let referenceQuery = parser.astify('Select * from "northwind"."territories" Order By "northwind"."territories" ASC', { database: 'postgresql' });
// //     expect(queryGradingService.isSameOrder(studentQuery as AST, referenceQuery as AST)).toBe(false);
// // });


// // test('Different Order direction returns false', () => {
// //     const queryGradingService = new QueryGradingService(PostgresDataSource);
// //     const parser = new Parser();
// //     let studentQuery = parser.astify('Select * from "northwind"."territories" Order By "northwind"."territories" DESC', { database: 'postgresql' });
// //     let referenceQuery = parser.astify('Select * from "northwind"."territories" Order By "northwind"."territories" ASC', { database: 'postgresql' });
// //     expect(queryGradingService.isSameOrder(studentQuery as AST, referenceQuery as AST)).toBe(false);
// // });

// // test('Same Order direction returns true', () => {
// //     const queryGradingService = new QueryGradingService(PostgresDataSource);
// //     const parser = new Parser();
// //     let studentQuery = parser.astify('Select * from "northwind"."territories" Order By "northwind"."territories" ASC', { database: 'postgresql' });
// //     let referenceQuery = parser.astify('Select * from "northwind"."territories" Order By "northwind"."territories" ASC', { database: 'postgresql' });
// //     expect(queryGradingService.isSameOrder(studentQuery as AST, referenceQuery as AST)).toBe(true);
// // });

// test('Same columns returns true', () => {
//     const queryGradingService = new QueryGradingService();
//     const parser = new Parser();
//     let studentQuery = parser.astify('Select * from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     let referenceQuery = parser.astify('Select * from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     expect(queryGradingService.areSameColumnsSelected(studentQuery as AST, referenceQuery as AST)[0]).toBe(true);
// });

// test('Different columns returns false', () => {
//     const queryGradingService = new QueryGradingService();
//     const parser = new Parser();
//     let studentQuery = parser.astify('Select * from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     let referenceQuery = parser.astify('Select "territories"."territory_description" from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     expect(queryGradingService.areSameColumnsSelected(studentQuery as AST, referenceQuery as AST)[0]).toBe(false);
// });

// test('Different number of columns returns false', () => {
//     const queryGradingService = new QueryGradingService();
//     const parser = new Parser();
//     let studentQuery = parser.astify('Select * from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     let referenceQuery = parser.astify('Select "territories"."territory_description", "territories"."territory_id" from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     expect(queryGradingService.areSameColumnsSelected(studentQuery as AST, referenceQuery as AST)[0]).toBe(false);
// });

// test('Same columns but different order returns true', () => {
//     const queryGradingService = new QueryGradingService();
//     const parser = new Parser();
//     let studentQuery = parser.astify('Select "territories"."territory_id", "territories"."territory_description" from "northwind"."territories", "territories"."territory_id" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     let referenceQuery = parser.astify('Select "territories"."territory_description", "territories"."territory_id" from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     expect(queryGradingService.areSameColumnsSelected(studentQuery as AST, referenceQuery as AST)[0]).toBe(true);
// });

// test('Same columns but one with aggregation returns false', () => {
//     const queryGradingService = new QueryGradingService();
//     const parser = new Parser();
//     let studentQuery = parser.astify('Select SUM("territories"."territory_id") from "northwind"."territories", "territories"."territory_id" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     let referenceQuery = parser.astify('Select "territories"."territory_id" from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     expect(queryGradingService.areSameColumnsSelected(studentQuery as AST, referenceQuery as AST)[0]).toBe(false);
// });

// test('Same columns with same aggregation  returns true', () => {
//     const queryGradingService = new QueryGradingService();
//     const parser = new Parser();
//     let studentQuery = parser.astify('Select SUM("territories"."territory_id") from "northwind"."territories", "territories"."territory_id" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     let referenceQuery = parser.astify('Select SUM("territories"."territory_id") from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     expect(queryGradingService.areSameColumnsSelected(studentQuery as AST, referenceQuery as AST)[0]).toBe(true);
// });

// test('Same columns with same aggregation but different order returns true', () => {
//     const queryGradingService = new QueryGradingService();
//     const parser = new Parser();
//     let studentQuery = parser.astify('Select SUM("territories"."territory_id"), MAX("territories"."territory_description") from "northwind"."territories", "territories"."territory_id" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     let referenceQuery = parser.astify('Select MAX("territories"."territory_description"), SUM("territories"."territory_id") from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     expect(queryGradingService.areSameColumnsSelected(studentQuery as AST, referenceQuery as AST)[0]).toBe(true);
// });

// test('Same columns with different aggregation  returns false', () => {
//     const queryGradingService = new QueryGradingService();
//     const parser = new Parser();
//     let studentQuery = parser.astify('Select SUM("territories"."territory_id") from "northwind"."territories", "territories"."territory_id" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     let referenceQuery = parser.astify('Select MAX("territories"."territory_id") from "northwind"."territories" Order By "territories"."territory_description" ASC', { database: 'postgresql' });
//     expect(queryGradingService.areSameColumnsSelected(studentQuery as AST, referenceQuery as AST)[0]).toBe(false);
// });


// test('Test generate execution plans', async () => {
//     const queryGradingService = new QueryGradingService();
//     console.log(test);
//     const queryGrade = await queryGradingService.gradeQuery(
//         referenceQuery,
//         'SELECT "employee_territories"."employee_id" FROM "northwind"."employee_territories" INNER JOIN "northwind"."territories" ON employee_territories.territory_id = territories.territory_id INNER JOIN "northwind"."region" ON territories.region_id = region.region_id WHERE "territories"."territory_description" >= \'Boston\' OR "territories"."region_id" BETWEEN 4 AND 1 AND "region"."region_description" IN (\'Northern\', \'Eastern\', \'Western\', \'Southern\') GROUP BY "employee_territories"."employee_id" HAVING COUNT("region"."region_id") < 2 ORDER BY "employee_territories"."employee_id" ASC',
//         PostgresDataSource,
//         ""
//     );
//     expect(queryGrade.grade).toBe(6);
// });


// test('Test same query without dounle qoute string', async () => {
//     const queryGradingService = new QueryGradingService();
//     const queryGrade = await queryGradingService.gradeQuery(
//         referenceQuery,
//         'SELECT employee_territories.employee_id FROM northwind.employee_territories INNER JOIN northwind.territories ON employee_territories.territory_id = territories.territory_id INNER JOIN northwind.region ON territories.region_id = region.region_id WHERE territories.territory_description >= \'Boston\' OR territories.region_id BETWEEN 4 AND 1 AND region.region_description IN (\'Northern\', \'Eastern\', \'Western\', \'Southern\') GROUP BY employee_territories.employee_id HAVING COUNT(region.region_id) < 2 ORDER BY employee_territories.employee_id ASC',
//         PostgresDataSource, ""
//     );
//     expect(queryGrade.grade).toBe(6);
// });

// test('Nothing in common', async () => {
//     const queryGradingService = new QueryGradingService();
//     const queryGrade = await queryGradingService.gradeQuery(
//         referenceQuery,
//         'Select "employees"."region" from "northwind"."employees" Group By "employees"."region" Having "employees"."postal_code" > 0 Order By "employees"."region" ASC',
//         PostgresDataSource, ""
//     );
//     expect(queryGrade.grade).toBe(0);
// });

// test('Wrong select', async () => {
//     const queryGradingService = new QueryGradingService();

//     const queryGrade = await queryGradingService.gradeQuery(
//         referenceQuery,
//         'SELECT COUNT("employee_territories"."territory_id") FROM "northwind"."employee_territories" INNER JOIN "northwind"."territories" ON employee_territories.territory_id = territories.territory_id INNER JOIN "northwind"."region" ON territories.region_id = region.region_id WHERE "territories"."territory_description" >= \'Boston\' OR "territories"."region_id" BETWEEN 4 AND 1 AND "region"."region_description" IN (\'Northern\', \'Eastern\', \'Western\', \'Southern\') GROUP BY "employee_territories"."employee_id" HAVING COUNT("region"."region_id") < 2 ORDER BY "employee_territories"."employee_id" ASC',
//         PostgresDataSource, ""
//     );
//     expect(queryGrade.grade).toBe(5);
// });

