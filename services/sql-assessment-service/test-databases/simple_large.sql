
-- Simple Database with Many Rows
CREATE TABLE simple_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50),
    age INT
);

-- Insert many rows into the simple table
INSERT INTO simple_table (name, age)
SELECT 'Name_' || generate_series(1, 10000), (random() * 100)::int;
