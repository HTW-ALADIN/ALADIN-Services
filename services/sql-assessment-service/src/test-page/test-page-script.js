"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
const successRateTasks = {
    "t0": {
        id: "t0", isIntroduction: true, text: "The following test will present several questions on retrieving data using PostgreSQL. You have one attempt to submit a SQL query in the PostgreSQL dialect and will not receive feedback. The questions are based on a specific database schema, which is visualized for reference. Before continuing, familiarize yourself with this schema and the two example queries displayed alongside it. The schema and example queries will remain visible below the questions throughout the test.", image: "schema_northwind_erd.png"
    },
    "t1": { id: "t1", referenceQuery: "SELECT \"e2\".\"home_phone\" FROM \"northwind\".\"order_details\" LEFT JOIN \"northwind\".\"orders\" ON order_details.order_id = orders.order_id FULL JOIN \"northwind\".\"employees\" AS \"e1\" ON orders.employee_id = e1.employee_id LEFT JOIN \"northwind\".\"employees\" AS \"e2\" ON e1.reports_to = e2.employee_id WHERE \"order_details\".\"unit_price\" != 27.8 GROUP BY \"e2\".\"home_phone\" HAVING MAX(\"orders\".\"ship_region\") <= 'WY' ORDER BY MAX(\"orders\".\"ship_address\") DESC", text: "In the Northwind database, find the home phone numbers of employees who supervise other employees, ensuring that the orders they are associated with do not have a unit price of 27.8. To do this, first, gather details from the order items and link them to their respective orders. Then, connect these orders to the employees who processed them. After that, for each of these employees, identify their supervisors and collect the home phone numbers of those supervisors. Make sure to only include supervisors whose associated orders have a shipping region that is Wyoming (WY) or less, based on the maximum shipping address. Finally, group the results by the home phone numbers of the supervisors and sort them in descending order based on the maximum shipping address.", image: "schema_northwind_erd.png" },
    "t2": { id: "t2", referenceQuery: "SELECT \"products\".\"category_id\" FROM \"northwind\".\"products\" WHERE \"products\".\"product_name\" LIKE '%koinen%' AND \"products\".\"product_id\" != 1 AND \"products\".\"quantity_per_unit\" IS NOT NULL OR \"products\".\"units_in_stock\" <= 25 GROUP BY \"products\".\"category_id\" HAVING MIN(\"products\".\"product_name\") >= 'Alice Mutton' ORDER BY COUNT(\"products\".\"units_on_order\") ASC", text: "Retrieve the products category id in the northwind database. Filter the results where the products product name matches the pattern %koinen% and the products product id does not equal 1 and the products quantity per unit is defined or the products units in stock is less than or equal to 25. Group the results based on the the products category id. Filter the grouped results where the minimum product name is greater than or equal to Alice Mutton. Sort the results by the the number of units on orders in ascending order.", image: "schema_northwind_erd.png" },
    "t3": {
        id: "t3", referenceQuery: "SELECT \"products\".\"product_id\" FROM \"northwind\".\"products\" WHERE \"products\".\"product_name\" LIKE 'Kon%' AND \"products\".\"supplier_id\" != 26 AND \"products\".\"units_in_stock\" IS NOT NULL OR \"products\".\"discontinued\" <= 1 GROUP BY \"products\".\"product_id\" HAVING SUM(\"products\".\"units_in_stock\") <= 3119 ORDER BY MIN(\"products\".\"category_id\") DESC", text: "What are the unique product IDs of products whose names start with \"Kon\", are not supplied by supplier 26, have a defined stock level, or are not discontinued, and how many units are in stock for each of these products, sorted by the minimum category ID in descending order, while ensuring that the total units in stock for each product do not exceed 3119?", image: "schema_northwind_erd.png"
    },
    "t4": {
        id: "t4", referenceQuery: "SELECT COUNT(\"orders\".\"required_date\"), MAX(\"order_details\".\"unit_price\") FROM \"northwind\".\"order_details\" CROSS JOIN \"northwind\".\"orders\" INNER JOIN \"northwind\".\"employees\" ON orders.employee_id = employees.employee_id WHERE \"orders\".\"order_id\" BETWEEN 10249 AND 10758 GROUP BY \"employees\".\"postal_code\" HAVING MAX(\"employees\".\"first_name\") = 'Steven'", text: "Count the number of required dates and find the highest unit price from the Northwind database. Start by combining every record from the order details table with every record from the orders table. Then, join this data with the employees table based on the employee ID. Next, filter the results to include only those orders with an order ID between 10249 and 10758. Group the results by the postal code of the employees. Finally, narrow down the grouped results to those where the highest first name among the employees is 'Steven'.", image: "schema_northwind_erd.png"
    },
    "t5": {
        id: "t5", referenceQuery: "SELECT \"orders\".\"required_date\" FROM \"northwind\".\"orders\" WHERE \"orders\".\"customer_id\" LIKE 'S%' AND \"orders\".\"ship_via\" != 3 AND \"orders\".\"order_date\" IS NOT NULL OR \"orders\".\"shipped_date\" < '1997-05-11' GROUP BY \"orders\".\"required_date\" HAVING MIN(\"orders\".\"ship_postal_code\") = '01-012' ORDER BY MIN(\"orders\".\"ship_region\") DESC", text: "Retrieve the required dates for orders from the Northwind database. Only include orders where the customer ID starts with 'S', the shipping method is not equal to 3, and either the order date is defined or the shipped date is earlier than May 11, 1997. Group the results by the required date of the orders. From these groups, filter to keep only those where the lowest shipping postal code is '01-012'. Finally, sort the results in descending order based on the lowest shipping region.", image: "schema_northwind_erd.png"
    },
    "t6": {
        id: "t6", referenceQuery: "SELECT COUNT(\"region\".\"region_description\"), MAX(\"territories\".\"territory_description\") FROM \"northwind\".\"employee_territories\" CROSS JOIN \"northwind\".\"territories\" INNER JOIN \"northwind\".\"region\" ON territories.region_id = region.region_id WHERE \"territories\".\"territory_id\" BETWEEN '27403' AND '94025' GROUP BY \"territories\".\"territory_id\" HAVING MAX(\"territories\".\"territory_description\") < 'Wilton'", text: "Retrieve the number of region descriptions and the maximum territory description from the following data combination in the northwind database. Combine each record from the employee territories table with each record from the territories table. Combine the data from the territories table and the region table. Filter the results where the territories territory id is between 27403 and 94025. Group the results based on the the territories territory id. Filter the grouped results where the maximum territory description is less than Wilton.", image: "schema_northwind_erd.png"
    },
    "t7": {
        id: "t7", referenceQuery: "SELECT \"customers\".\"address\", \"orders\".\"ship_name\" FROM \"northwind\".\"orders\" RIGHT JOIN \"northwind\".\"customers\" ON orders.customer_id = customers.customer_id WHERE \"customers\".\"region\" > 'Québec' OR \"orders\".\"ship_via\" IS NULL AND \"customers\".\"city\" IN ('Barcelona', 'Berlin', 'Boise', 'Bräcke') ORDER BY \"customers\".\"fax\" ASC", text: "What are the addresses of customers located in regions lexicographically greater than 'Québec' or who have orders with unspecified shipping methods, along with the shipping names for their orders, sorted by the customers' fax numbers in ascending order, specifically for customers located in Barcelona, Berlin, Boise, or Bräcke?", image: "schema_northwind_erd.png"
    },
    "t8": {
        id: "t8", referenceQuery: "SELECT COUNT(\"region\".\"region_description\"), MAX(\"territories\".\"territory_description\") FROM \"northwind\".\"employee_territories\" CROSS JOIN \"northwind\".\"territories\" INNER JOIN \"northwind\".\"region\" ON territories.region_id = region.region_id WHERE \"territories\".\"region_id\" BETWEEN 1 AND 2 GROUP BY \"employee_territories\".\"employee_id\" HAVING MAX(\"territories\".\"territory_description\") = 'Wilton'", text: "Count how many regions have a description and find the maximum territory description for employees who are associated with territories in the regions with IDs between 1 and 2. To do this, first, gather all employee territories and their corresponding territories. Then, connect these territories to their respective regions. After that, filter the results to include only those territories that belong to regions with IDs between 1 and 2. Group the results by each employee's ID. Finally, only include groups where the maximum territory description is 'Wilton'. The data is sourced from the Northwind database.", image: "schema_northwind_erd.png"
    },
    "t9": {
        id: "t9", referenceQuery: "SELECT MAX(\"region\".\"region_description\"), COUNT(\"territories\".\"territory_description\") FROM \"northwind\".\"employee_territories\" CROSS JOIN \"northwind\".\"territories\" INNER JOIN \"northwind\".\"region\" ON territories.region_id = region.region_id WHERE \"employee_territories\".\"employee_id\" BETWEEN 3 AND 6 GROUP BY \"employee_territories\".\"employee_id\" HAVING COUNT(\"region\".\"region_description\") != '4'", text: "What are the employee IDs and the count of distinct regions associated with their territories for employees whose IDs are between 3 and 6, excluding those who are associated with exactly 4 distinct regions?", image: "schema_northwind_erd.png"
    },
    "t10": {
        id: "t10", referenceQuery: "SELECT \"e2\".\"photo\" FROM \"northwind\".\"order_details\" LEFT JOIN \"northwind\".\"orders\" ON order_details.order_id = orders.order_id FULL JOIN \"northwind\".\"employees\" AS \"e1\" ON orders.employee_id = e1.employee_id LEFT JOIN \"northwind\".\"employees\" AS \"e2\" ON e1.reports_to = e2.employee_id WHERE \"e1\".\"photo_path\" != 'http://accweb/emmployees/davolio.bmp' GROUP BY \"e2\".\"photo\" HAVING COUNT(\"e2\".\"birth_date\") < '9' ORDER BY COUNT(\"e2\".\"city\") ASC", text: "Retrieve the e2 photo from the following data combination in the northwind database. Include all data from the order details table and the matching data from the orders table. Include all records from both the orders table and the employees table. Match records within the employees table where the e1 reports to equals the e2 employee id. Filter the results where the e1 photo path does not equal http://accweb/emmployees/davolio.bmp. Group the results based on the the e2 photo. Filter the grouped results where the number of birth dates is less than 9. Sort the results by the the number of citys in ascending order.", image: "schema_northwind_erd.png"
    },
    "t11": {
        id: "t11", referenceQuery: "SELECT \"orders\".\"order_id\", \"employees\".\"hire_date\" FROM \"northwind\".\"orders\" RIGHT JOIN \"northwind\".\"employees\" ON orders.employee_id = employees.employee_id WHERE \"employees\".\"title_of_courtesy\" < 'Ms.' AND \"orders\".\"ship_via\" IS NULL OR \"orders\".\"ship_address\" IN ('187 Suffolk Ln.', '12 Orchestra Terrace', 'Magazinweg 7', 'Maubelstr. 90') ORDER BY \"employees\".\"reports_to\" ASC", text: "Retrieve the order IDs and hire dates of employees from the Northwind database. Focus on employees who have a title of courtesy that is less than 'Ms.' and either have no associated shipping method for their orders or have a shipping address that matches one of the following: '187 Suffolk Ln.', '12 Orchestra Terrace', 'Magazinweg 7', or 'Maubelstr. 90'. Ensure to include all employees, even if they do not have any orders, and sort the results by the employee's supervisor in ascending order.", image: "schema_northwind_erd.png"
    },
    "t12": {
        id: "t12", referenceQuery: "SELECT \"orders\".\"customer_id\", \"orders\".\"order_date\" FROM \"northwind\".\"orders\" RIGHT JOIN \"northwind\".\"customers\" ON orders.customer_id = customers.customer_id WHERE \"orders\".\"ship_region\" > 'Nueva Esparta' AND \"customers\".\"contact_title\" IS NULL OR \"customers\".\"contact_name\" IN ('Maurizio Moroni', 'Horst Kloss', 'Diego Roel', 'Rita Müller') ORDER BY \"customers\".\"fax\" DESC", text: "Retrieve the customer ID and order date from the orders in the Northwind database, ensuring to include all customers and their corresponding orders. The results should be filtered to show only those orders where the shipping region is greater than 'Nueva Esparta' and the customer's contact title is undefined, or where the customer's contact name is one of the following: Maurizio Moroni, Horst Kloss, Diego Roel, or Rita Müller. Finally, sort the results by the customer's fax number in descending order.", image: "schema_northwind_erd.png"
    },
    "t13": {
        id: "t13", referenceQuery: "SELECT \"e2\".\"last_name\" FROM \"northwind\".\"order_details\" LEFT JOIN \"northwind\".\"orders\" ON order_details.order_id = orders.order_id FULL JOIN \"northwind\".\"employees\" AS \"e1\" ON orders.employee_id = e1.employee_id LEFT JOIN \"northwind\".\"employees\" AS \"e2\" ON e1.reports_to = e2.employee_id WHERE \"orders\".\"ship_name\" != 'Chop-suey Chinese' GROUP BY \"e2\".\"last_name\" HAVING MIN(\"e1\".\"title_of_courtesy\") >= 'Dr.' ORDER BY COUNT(\"e2\".\"address\") DESC", text: "What are the last names of employees who have a title of courtesy of at least 'Dr.', excluding any orders shipped under the name 'Chop-suey Chinese', and how many addresses are associated with each last name, sorted in descending order by the count of addresses?", image: "schema_northwind_erd.png"
    },
    "t14": {
        id: "t14", referenceQuery: "SELECT \"e2\".\"last_name\" FROM \"northwind\".\"order_details\" LEFT JOIN \"northwind\".\"orders\" ON order_details.order_id = orders.order_id FULL JOIN \"northwind\".\"employees\" AS \"e1\" ON orders.employee_id = e1.employee_id LEFT JOIN \"northwind\".\"employees\" AS \"e2\" ON e1.reports_to = e2.employee_id WHERE \"e1\".\"extension\" != '2344' GROUP BY \"e2\".\"last_name\" HAVING COUNT(\"orders\".\"ship_region\") != '323' ORDER BY COUNT(\"e2\".\"first_name\") ASC", text: "Retrieve the last names of employees who are supervisors (e2) from the Northwind database. Start by including all records from the order details table and the corresponding records from the orders table. Then, include all records from the orders table and the employees table, ensuring that you match records where the supervisor (e1) reports to the employee (e2). Filter the results to exclude any supervisors whose extension is '2344'. Group the results by the last names of the supervisors. From these grouped results, further filter to include only those where the count of distinct shipping regions is not equal to '323'. Finally, sort the results in ascending order based on the count of first names associated with each supervisor", image: "schema_northwind_erd.png"
    },
    "t15": {
        id: "t15", referenceQuery: "SELECT \"products\".\"supplier_id\" FROM \"northwind\".\"products\" WHERE \"products\".\"product_name\" LIKE 'Raclette %' AND \"products\".\"reorder_level\" != 20 OR \"products\".\"quantity_per_unit\" IS NOT NULL AND \"products\".\"category_id\" >= 3 GROUP BY \"products\".\"supplier_id\" HAVING COUNT(\"products\".\"quantity_per_unit\") != '77' ORDER BY MIN(\"products\".\"product_name\") DESC", text: "In the Northwind database, identify the unique suppliers of products that either have names starting with \"Raclette\" and do not have a reorder level of 20, or have a non-null quantity per unit and belong to a category with an ID of 3 or higher. Group the results by supplier ID and ensure that the count of products with a non-null quantity per unit is not equal to 77. Finally, sort the results in descending order based on the minimum product name.", image: "schema_northwind_erd.png"
    },
    "t16": {
        id: "t16", referenceQuery: "SELECT \"suppliers\".\"address\", \"suppliers\".\"country\" FROM \"northwind\".\"products\" RIGHT JOIN \"northwind\".\"suppliers\" ON products.supplier_id = suppliers.supplier_id WHERE \"products\".\"unit_price\" >= 34.8 AND \"suppliers\".\"city\" IS NULL OR \"suppliers\".\"contact_title\" IN ('Sales Representative', 'Marketing Manager', 'Sales Representative', 'Accounting Manager') ORDER BY \"suppliers\".\"homepage\" DESC", text: "Retrieve the suppliers address and the suppliers country from the following data combination in the northwind database. Include all data from the suppliers table and the matching data from the products table. Filter the results where the products unit price is greater than or equal to 34.8 and the suppliers city is not defined or the suppliers contact title is one of Sales Representative, Marketing Manager, Sales Representative, Accounting Manager. Sort the results by the the suppliers homepage in descending order.", image: "schema_northwind_erd.png"
    }
};
const feedbackTasks = {
    "t0": {
        id: "t0", isIntroduction: true, text: "The following test will present several questions on retrieving data using PostgreSQL. You have unlimited attempts to submit an SQL query in the PostgreSQL dialect and will receive feedback on whether your submission is correct. The level of detail in the feedback varies between question. The questions are based on a specific database schema, which is visualized for reference. Before continuing, familiarize yourself with this schema and the two example queries displayed alongside it. The schema and example queries will remain visible below the questions throughout the test.", image: "schema_public_erd_query.png"
    },
    "t1": { id: "t1", referenceQuery: "SELECT * FROM \"public\".\"professors\" INNER JOIN \"public\".\"faculties\" ON professors.faculty_id = faculties.faculty_id WHERE \"professors\".\"name\" LIKE '%rofessor%' OR \"faculties\".\"is_active\" IS TRUE", text: "Retrieve all information about the following data combination in the public database. Combine the data from the professors table and the faculties table. Filter the results where the professors name matches the pattern %rofessor% or the faculties is active is true.", image: "schema_public_erd_query.png" },
    "t2": { id: "t2", detailedFeedback: true, referenceQuery: "SELECT \"p1\".\"senior_professor_id\" FROM \"public\".\"professor_benefits\" RIGHT JOIN \"public\".\"professors\" AS \"p1\" ON professor_benefits.professor_id = p1.professor_id FULL JOIN \"public\".\"professors\" AS \"p2\" ON p1.senior_professor_id = p2.professor_id RIGHT JOIN \"public\".\"faculties\" ON p2.faculty_id = faculties.faculty_id WHERE \"professor_benefits\".\"benefit_id\" BETWEEN 2 AND 3 GROUP BY \"p1\".\"senior_professor_id\" HAVING COUNT(\"p2\".\"name\") <= '40' ORDER BY \"p1\".\"senior_professor_id\" DESC", text: "Retrieve the p1 senior professor id from the following data combination in the public database. Include all data from the professors table and the matching data from the professor benefits table. Match records within the professors table where the p1 senior professor id equals the p2 professor id. Include all data from the faculties table and the matching data from the professors table. Filter the results where the professor benefits benefit id is between 2 and 3. Group the results based on the the p1 senior professor id. Filter the grouped results where the number of names is less than or equal to 40. Sort the results by the the p1 senior professor id in descending order.", image: "schema_public_erd_query.png" },
    "t3": { id: "t3", detailedFeedback: true, referenceQuery: "SELECT * FROM \"public\".\"scholarships\" INNER JOIN \"public\".\"students\" ON scholarships.student_id = students.student_id WHERE \"students\".\"name\" LIKE '%dent1%' AND \"scholarships\".\"is_active\" IS TRUE", text: "Retrieve all information about the following data combination in the public database. Combine the data from the scholarships table and the students table. Filter the results where the students name matches the pattern %dent1% and the scholarships is active is true.", image: "schema_public_erd_query.png" },
    "t4": { id: "t4", referenceQuery: "SELECT \"p1\".\"professor_id\" FROM \"public\".\"professor_benefits\" RIGHT JOIN \"public\".\"professors\" AS \"p1\" ON professor_benefits.professor_id = p1.professor_id FULL JOIN \"public\".\"professors\" AS \"p2\" ON p1.senior_professor_id = p2.professor_id RIGHT JOIN \"public\".\"faculties\" ON p2.faculty_id = faculties.faculty_id WHERE \"professor_benefits\".\"benefit_id\" BETWEEN 2 AND 3 GROUP BY \"p1\".\"professor_id\" HAVING MAX(\"professor_benefits\".\"start_date\") >= '2022-12-31' ORDER BY \"p1\".\"professor_id\" ASC", text: "Retrieve the p1 professor id from the following data combination in the public database. Include all data from the professors table and the matching data from the professor benefits table. Match records within the professors table where the p1 senior professor id equals the p2 professor id. Include all data from the faculties table and the matching data from the professors table. Filter the results where the professor benefits benefit id is between 2 and 3. Group the results based on the the p1 professor id. Filter the grouped results where the maximum start date is greater than or equal to 2022-12-31. Sort the results by the the p1 professor id in ascending order.", image: "schema_public_erd_query.png" },
    "t5": { id: "t5", referenceQuery: "SELECT MAX(\"professor_benefits\".\"start_date\"), COUNT(\"professors\".\"name\"), MAX(\"professor_benefits\".\"end_date\") FROM \"public\".\"professor_benefits\" LEFT JOIN \"public\".\"professors\" ON professor_benefits.professor_id = professors.professor_id INNER JOIN \"public\".\"faculties\" ON professors.faculty_id = faculties.faculty_id WHERE \"faculties\".\"faculty_name\" = 'Architecture' AND \"professor_benefits\".\"professor_id\" IN (6, 17, 16, 7) OR \"professor_benefits\".\"end_date\" IS NOT NULL GROUP BY \"faculties\".\"faculty_name\" HAVING MIN(\"professors\".\"name\") != 'Professor1' ORDER BY SUM(\"professor_benefits\".\"professor_id\") DESC", text: "Retrieve the maximum start date and the number of names and the maximum end date from the following data combination in the public database. Include all data from the professor benefits table and the matching data from the professors table. Combine the data from the professors table and the faculties table. Filter the results where the faculties faculty name equals Architecture and the professor benefits professor id is one of 6, 17, 16, 7 or the professor benefits end date is defined. Group the results based on the the faculties faculty name. Filter the grouped results where the minimum name does not equal Professor1. Sort the results by the the sum of professor ids in descending order.", image: "schema_public_erd_query.png" },
    "t6": { id: "t6", detailedFeedback: true, referenceQuery: "SELECT COUNT(\"faculties\".\"faculty_name\"), COUNT(\"assignments\".\"assignment_name\"), MAX(\"courses\".\"course_name\") FROM \"public\".\"assignments\" LEFT JOIN \"public\".\"courses\" ON assignments.course_id = courses.course_id INNER JOIN \"public\".\"faculties\" ON courses.faculty_id = faculties.faculty_id WHERE \"assignments\".\"assignment_name\" = 'Assignment 56' OR \"faculties\".\"faculty_id\" IN (2, 3, 7, 8) AND \"courses\".\"is_active\" IS NOT NULL GROUP BY \"assignments\".\"course_id\" HAVING MIN(\"courses\".\"course_name\") = 'Course 1' ORDER BY MAX(\"faculties\".\"faculty_id\") DESC", text: "Retrieve the number of faculty names and the number of assignment names and the maximum course name from the following data combination in the public database. Include all data from the assignments table and the matching data from the courses table. Combine the data from the courses table and the faculties table. Filter the results where the assignments assignment name equals Assignment 56 or the faculties faculty id is one of 2, 3, 7, 8 and the courses is active is defined. Group the results based on the the assignments course id. Filter the grouped results where the minimum course name equals Course 1. Sort the results by the the maximum faculty id in descending order.", image: "schema_public_erd_query.png" },
    "t7": { id: "t7", referenceQuery: "SELECT MIN(\"faculties\".\"faculty_name\"), MAX(\"student_clubs\".\"club_name\") FROM \"public\".\"student_clubs\" RIGHT JOIN \"public\".\"faculties\" ON student_clubs.faculty_id = faculties.faculty_id WHERE \"student_clubs\".\"faculty_id\" IS NULL OR \"student_clubs\".\"club_id\" < 15 GROUP BY \"student_clubs\".\"club_name\" HAVING MIN(\"faculties\".\"faculty_name\") = 'Architecture' ORDER BY AVG(\"student_clubs\".\"club_id\") ASC", text: "Retrieve the minimum faculty name and the maximum club name from the following data combination in the public database. Include all data from the faculties table and the matching data from the student clubs table. Filter the results where the student clubs faculty id is not defined or the student clubs club id is less than 15. Group the results based on the the student clubs club name. Filter the grouped results where the minimum faculty name equals Architecture. Sort the results by the the average of club ids in ascending order.", image: "schema_public_erd_query.png" },
    "t8": { id: "t8", detailedFeedback: true, referenceQuery: "SELECT MIN(\"internships\".\"start_date\"), MIN(\"internships\".\"position\") FROM \"public\".\"internships\" RIGHT JOIN \"public\".\"students\" ON internships.student_id = students.student_id WHERE \"internships\".\"end_date\" IS NULL AND \"students\".\"student_id\" > 114 GROUP BY \"students\".\"student_id\" HAVING COUNT(\"internships\".\"company_name\") < '48' ORDER BY COUNT(\"students\".\"mentor_id\") DESC", text: "Retrieve the minimum start date and the minimum position from the following data combination in the public database. Include all data from the students table and the matching data from the internships table. Filter the results where the internships end date is not defined and the students student id is greater than 114. Group the results based on the the students student id. Filter the grouped results where the number of company names is less than 48. Sort the results by the the number of mentor ids in descending order.", image: "schema_public_erd_query.png" }
};
const plausibilityTasks = {
    "t0": {
        id: "t0", isIntroduction: true, text: "In the following test, you will rate several SQL queries for their plausibility using the scale: Very implausible, Somewhat implausible, Neither plausible nor implausible, Somewhat plausible, Very plausible. The queries are applied to a specific database schema, which is visualized for reference. Before continuing, familiarize yourself with this schema, which will remain visible below the questions throughout the test.", image: "schema_public_erd.png"
    },
    "t1": { id: "t1", text: "How plausible is the following SQL query based on the given database schema? \n SELECT \"students\".\"student_id\" FROM \"public\".\"students\" WHERE \"students\".\"name\" != 'Student53' OR \"students\".\"is_active\" IS TRUE OR \"students\".\"mentor_id\" > 1 OR \"students\".\"student_id\" IN (10, 55, 99, 139) GROUP BY \"students\".\"student_id\" ORDER BY \"students\".\"student_id\" DESC", image: "schema_public_erd.png" },
    "t2": { id: "t2", text: "How plausible is the following SQL query based on the given database schema? \n SELECT \"courses\".\"faculty_id\", \"courses\".\"course_id\" FROM \"public\".\"courses\" WHERE \"courses\".\"course_id\" >= 18 OR \"courses\".\"is_active\" IS NOT NULL AND \"courses\".\"faculty_id\" IS NULL", image: "schema_public_erd.png" },
    "t3": { id: "t3", text: "How plausible is the following SQL query based on the given database schema? \n SELECT * FROM \"public\".\"professors\" WHERE \"professors\".\"senior_professor_id\" >= 1", image: "schema_public_erd.png" },
    "t4": { id: "t4", text: "How plausible is the following SQL query based on the given database schema? \n SELECT \"p1\".\"is_active\" FROM \"public\".\"professors\" AS \"p1\" LEFT JOIN \"public\".\"professors\" AS \"p2\" ON p1.senior_professor_id = p2.professor_id WHERE \"p1\".\"name\" != 'Professor13' GROUP BY \"p1\".\"is_active\" HAVING COUNT(\"p1\".\"name\") <= '40' ORDER BY \"p1\".\"is_active\" DESC", image: "schema_public_erd.png" },
    "t5": { id: "t5", text: "How plausible is the following SQL query based on the given database schema? \n SELECT * FROM \"public\".\"courses\" LEFT JOIN \"public\".\"faculties\" ON courses.faculty_id = faculties.faculty_id WHERE \"faculties\".\"faculty_name\" >= 'Engineering' OR \"courses\".\"course_name\" > 'Course 10' ORDER BY \"faculties\".\"is_active\" DESC", image: "schema_public_erd.png" },
    "t6": { id: "t6", text: "How plausible is the following SQL query based on the given database schema? \n SELECT \"s1\".\"is_active\", \"s2\".\"mentor_id\" FROM \"public\".\"student_club_memberships\" CROSS JOIN \"public\".\"students\" AS \"s1\" LEFT JOIN \"public\".\"students\" AS \"s2\" ON s1.mentor_id = s2.student_id WHERE \"student_club_memberships\".\"join_date\" IS NOT NULL AND \"s2\".\"mentor_id\" IS NULL ORDER BY \"s1\".\"is_active\" ASC", image: "schema_public_erd.png" },
    "t7": { id: "t7", text: "How plausible is the following SQL query based on the given database schema? \n SELECT \"internships\".\"internship_id\", \"internships\".\"start_date\" FROM \"public\".\"internships\" RIGHT JOIN \"public\".\"students\" ON internships.student_id = students.student_id WHERE \"students\".\"mentor_id\" IS NOT NULL", image: "schema_public_erd.png" },
    "t8": { id: "t8", text: "How plausible is the following SQL query based on the given database schema? \n SELECT MIN(\"students\".\"name\") FROM \"public\".\"scholarships\" RIGHT JOIN \"public\".\"students\" ON scholarships.student_id = students.student_id ORDER BY MIN(\"students\".\"name\") DESC", image: "schema_public_erd.png" },
    "t9": { id: "t9", text: "How plausible is the following SQL query based on the given database schema? \n SELECT COUNT(\"student_clubs\".\"club_name\"), COUNT(\"faculties\".\"faculty_name\") FROM \"public\".\"student_clubs\" INNER JOIN \"public\".\"faculties\" ON student_clubs.faculty_id = faculties.faculty_id WHERE \"faculties\".\"faculty_id\" > 8 AND \"student_clubs\".\"is_active\" IS NOT NULL GROUP BY \"faculties\".\"faculty_id\" HAVING COUNT(\"student_clubs\".\"club_name\") < '15' ORDER BY COUNT(\"faculties\".\"faculty_name\") DESC", image: "schema_public_erd.png" },
    "t10": { id: "t10", text: "How plausible is the following SQL query based on the given database schema? \n SELECT \"student_clubs\".\"club_name\" FROM \"public\".\"student_club_memberships\" LEFT JOIN \"public\".\"student_clubs\" ON student_club_memberships.club_id = student_clubs.club_id RIGHT JOIN \"public\".\"faculties\" ON student_clubs.faculty_id = faculties.faculty_id WHERE \"faculties\".\"faculty_name\" LIKE '%duc%' OR \"student_clubs\".\"club_id\" BETWEEN 5 AND 11 OR \"faculties\".\"is_active\" IS TRUE GROUP BY \"student_clubs\".\"club_name\" HAVING MIN(\"student_club_memberships\".\"join_date\") > '2024-01-31' ORDER BY \"student_clubs\".\"club_name\" DESC", image: "schema_public_erd.png" },
    "t11": { id: "t11", text: "How plausible is the following SQL query based on the given database schema? \n SELECT COUNT(\"scholarships\".\"amount\") FROM \"public\".\"scholarships\" FULL JOIN \"public\".\"students\" ON scholarships.student_id = students.student_id WHERE \"students\".\"student_id\" <= 35 ORDER BY MAX(\"students\".\"mentor_id\") ASC", image: "schema_public_erd.png" },
    "t12": { id: "t12", text: "How plausible is the following SQL query based on the given database schema? \n SELECT MIN(\"professor_benefits\".\"start_date\"), MIN(\"professor_benefits\".\"end_date\") FROM \"public\".\"professor_benefits\" RIGHT JOIN \"public\".\"professors\" ON professor_benefits.professor_id = professors.professor_id LEFT JOIN \"public\".\"faculties\" ON professors.faculty_id = faculties.faculty_id WHERE \"professors\".\"name\" LIKE '%ssor%' ORDER BY COUNT(\"professors\".\"senior_professor_id\") DESC", image: "schema_public_erd.png" },
    "t13": { id: "t13", text: "How plausible is the following SQL query based on the given database schema? \n SELECT MIN(\"professor_benefits\".\"start_date\"), MAX(\"professor_benefits\".\"end_date\") FROM \"public\".\"professor_benefits\" WHERE \"professor_benefits\".\"professor_id\" BETWEEN 38 AND 15 OR \"professor_benefits\".\"end_date\" != '2025-12-30' GROUP BY \"professor_benefits\".\"benefit_id\" ORDER BY MAX(\"professor_benefits\".\"professor_id\") DESC", image: "schema_public_erd.png" },
    "t14": { id: "t14", text: "How plausible is the following SQL query based on the given database schema? \n SELECT MAX(\"benefits\".\"benefit_name\"), COUNT(\"benefits\".\"description\") FROM \"public\".\"benefits\" WHERE \"benefits\".\"benefit_name\" <= 'Travel Allowance' GROUP BY \"benefits\".\"benefit_name\" HAVING MIN(\"benefits\".\"description\") = 'Access to additional lab funding'", image: "schema_public_erd.png" },
    "t15": { id: "t15", text: "How plausible is the following SQL query based on the given database schema? \n SELECT \"students\".\"faculty_id\" FROM \"public\".\"peer_reviews\" FULL JOIN \"public\".\"students\" ON peer_reviews.reviewer_id = students.student_id WHERE \"students\".\"student_id\" IN (103, 75, 146, 31) GROUP BY \"students\".\"faculty_id\" HAVING COUNT(\"students\".\"name\") != '160' ORDER BY SUM(\"peer_reviews\".\"reviewer_id\") ASC", image: "schema_public_erd.png" }
};
const testSetups = {
    "Test1": {
        id: "Test1",
        type: "text",
        feedback: false,
        tasks: successRateTasks,
        connectionInfo: {
            "type": "postgres",
            "host": "localhost",
            "port": 5437,
            "username": "testUser",
            "password": "abc124",
            "database": "db",
            "schema": "northwind"
        }
    },
    "Test2": {
        id: "Test2",
        type: "text",
        feedback: true,
        tasks: feedbackTasks,
        connectionInfo: {
            "type": "postgres",
            "host": "localhost",
            "port": 5434,
            "username": "testUser",
            "password": "abc124",
            "database": "db_complex",
            "schema": "public"
        }
    },
    "Test3": {
        id: "Test 3",
        type: "radio",
        connectionInfo: {
            "type": "postgres",
            "host": "localhost",
            "port": 5434,
            "username": "testUser",
            "password": "abc124",
            "database": "db_complex",
            "schema": "public"
        },
        options: [
            "Very implausible",
            "Somewhat implausible",
            "Neither plausible nor implausible",
            "Somewhat plausible",
            "Very plausible"
        ],
        feedback: false,
        tasks: plausibilityTasks
    }
};
let testSetupId = null;
let testSetup = null;
let currentQuestionIndex = 0;
let report = {};
let startTime = 0;
let inputStartTime = 0;
let submitTime = 0;
const testSelection = document.getElementById("test-selection");
const testContainer = document.getElementById("test-container");
const questionText = document.getElementById("question-text");
const questionImage = document.getElementById("question-image");
const inputContainer = document.getElementById("input-container");
const submitBtn = document.getElementById("submit-btn");
const nextBtn = document.getElementById("next-btn");
const startBtn = document.getElementById("start-btn");
const testDropdown = document.getElementById("test-dropdown");
function initializeTestSelection() {
    testDropdown.innerHTML = "";
    for (const key in testSetups) {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = key;
        testDropdown.appendChild(option);
    }
    testSelection.style.display = "block";
    testContainer.style.display = "none";
}
function startTest() {
    testSetupId = testDropdown.value;
    testSetup = testSetups[testSetupId];
    currentQuestionIndex = 0;
    report = {};
    testSelection.style.display = "none";
    testContainer.style.display = "block";
    loadQuestion();
}
function loadQuestion() {
    var _a;
    startTime = Date.now();
    nextBtn.disabled = true;
    submitBtn.disabled = false;
    if (!testSetup)
        return;
    const question = testSetup.tasks[Object.keys(testSetup.tasks)[currentQuestionIndex]];
    questionText.textContent = question.text;
    questionImage.src = question.image;
    inputContainer.innerHTML = "";
    if (question.isIntroduction) {
        nextBtn.disabled = false;
        submitBtn.disabled = true;
    }
    else if (testSetup.type === "text") {
        const input = document.createElement("textarea");
        input.id = "user-input";
        input.addEventListener("input", () => {
            inputStartTime = Date.now();
        });
        inputContainer.appendChild(input);
    }
    else {
        (_a = testSetup.options) === null || _a === void 0 ? void 0 : _a.forEach(option => {
            const label = document.createElement("label");
            const radio = document.createElement("input");
            radio.type = "radio";
            radio.name = "user-input";
            radio.value = option;
            label.appendChild(radio);
            label.append(option);
            inputContainer.appendChild(label);
            inputContainer.appendChild(document.createElement("br"));
            radio.addEventListener("change", () => {
                inputStartTime = Date.now();
            });
        });
    }
}
function submitAnswer(showFeedback) {
    return __awaiter(this, void 0, void 0, function* () {
        if (!testSetup)
            return;
        const question = testSetup.tasks[Object.keys(testSetup.tasks)[currentQuestionIndex]];
        ;
        let userAnswer = "";
        if (testSetup.type === "text") {
            userAnswer = document.getElementById("user-input").value;
        }
        else {
            const selected = document.querySelector("input[name='user-input']:checked");
            userAnswer = selected ? selected.value : "";
        }
        if (!userAnswer)
            return;
        submitTime = Date.now();
        const inputTime = (inputStartTime - startTime) / 1000;
        const submissionTime = (submitTime - startTime) / 1000;
        if (!report[question.id]) {
            report[question.id] = {
                grade: 0,
                answer: [],
                startTime: inputTime,
                submitTime: submissionTime,
                submitAttempts: 0,
                feedback: ""
            };
        }
        report[question.id].submitAttempts += 1;
        report[question.id].answer.push(userAnswer);
        report[question.id].startTime = inputTime;
        report[question.id].submitTime = submissionTime;
        if (testSetup.type === "text") {
            const response = yield fetch("/api/grading/grade", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ connectionInfo: testSetup.connectionInfo, gradingRequest: { referenceQuery: question.referenceQuery, studentQuery: userAnswer } })
            });
            const result = yield response.json();
            report[question.id].grade = result.comparisonResult.grade;
            report[question.id].feedback = result.comparisonResult.feedback;
            if (testSetup.feedback) {
                if (question.detailedFeedback) {
                    showFeedbackMessage(`Feedback: ${result.comparisonResult.equivelant ? 'Submitted query is equivelant to reference query.' : 'Submitted query is not equivelant to reference query.'} \n ${result.comparisonResult.feedback}`);
                }
                else {
                    showFeedbackMessage(`Feedback: ${result.comparisonResult.equivelant ? 'Submitted query is equivelant to reference query.' : 'Submitted query is not equivelant to reference query.'}`);
                }
            }
            else {
                showFeedbackMessage("Answer submitted.");
            }
        }
        else {
            if (!testSetup.feedback) {
                showFeedbackMessage("Answer submitted.");
            }
        }
        nextBtn.disabled = false;
    });
}
function showFeedbackMessage(message) {
    const feedbackBox = document.getElementById("feedback-box");
    feedbackBox.textContent = message;
    feedbackBox.style.display = "block";
}
function nextQuestion() {
    if (!testSetup)
        return;
    const feedbackBox = document.getElementById("feedback-box");
    feedbackBox.textContent = "";
    if (currentQuestionIndex < Object.keys(testSetup.tasks).length - 1) {
        currentQuestionIndex++;
        loadQuestion();
    }
    else {
        downloadReport();
    }
}
function downloadReport() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const blob = new Blob([JSON.stringify({ testSetupId, report }, null, 2)], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `report_${testSetupId}_${timestamp}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    initializeTestSelection();
}
startBtn.addEventListener("click", startTest);
submitBtn.addEventListener("click", () => submitAnswer(true));
nextBtn.addEventListener("click", () => nextQuestion());
initializeTestSelection();
//# sourceMappingURL=test-page-script.js.map