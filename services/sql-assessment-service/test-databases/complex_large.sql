CREATE TABLE students (
    student_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    mentor_id INT,
    faculty_id INT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (mentor_id) REFERENCES students(student_id) ON DELETE SET NULL
);

CREATE TABLE faculties (
    faculty_id SERIAL PRIMARY KEY,
    faculty_name VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE campuses (
    campus_id SERIAL PRIMARY KEY,
    campus_name VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE faculty_campuses (
    faculty_id INT,
    campus_id INT,
    PRIMARY KEY (faculty_id, campus_id),
    FOREIGN KEY (faculty_id) REFERENCES faculties(faculty_id),
    FOREIGN KEY (campus_id) REFERENCES campuses(campus_id)
);

CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    course_name VARCHAR(50) NOT NULL,
    faculty_id INT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (faculty_id) REFERENCES faculties(faculty_id)
);

CREATE TABLE assignments (
    assignment_id SERIAL PRIMARY KEY,
    assignment_name VARCHAR(50) NOT NULL,
    course_id INT,
    assigned_student_id INT,
    is_completed BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    FOREIGN KEY (assigned_student_id) REFERENCES students(student_id)
);

CREATE TABLE peer_reviews (
    review_id SERIAL PRIMARY KEY,
    reviewer_id INT,
    reviewee_id INT,
    comments VARCHAR(255),
    is_public BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (reviewer_id) REFERENCES students(student_id),
    FOREIGN KEY (reviewee_id) REFERENCES students(student_id)
);

CREATE TABLE scholarships (
    scholarship_id SERIAL PRIMARY KEY,
    student_id INT,
    amount DECIMAL(10,2),
    effective_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE TABLE benefits (
    benefit_id SERIAL PRIMARY KEY,
    benefit_name VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE student_benefits (
    student_id INT,
    benefit_id INT,
    start_date DATE,
    end_date DATE,
    PRIMARY KEY (student_id, benefit_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (benefit_id) REFERENCES benefits(benefit_id)
);

CREATE TABLE trainings (
    training_id SERIAL PRIMARY KEY,
    training_name VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE student_trainings (
    student_id INT,
    training_id INT,
    completion_date DATE,
    PRIMARY KEY (student_id, training_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (training_id) REFERENCES trainings(training_id)
);

CREATE TABLE professors (
    professor_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    senior_professor_id INT,
    faculty_id INT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (senior_professor_id) REFERENCES professors(professor_id) ON DELETE SET NULL,
    FOREIGN KEY (faculty_id) REFERENCES faculties(faculty_id)
);

CREATE TABLE professor_benefits (
    professor_id INT,
    benefit_id INT,
    start_date DATE,
    end_date DATE,
    PRIMARY KEY (professor_id, benefit_id),
    FOREIGN KEY (professor_id) REFERENCES professors(professor_id),
    FOREIGN KEY (benefit_id) REFERENCES benefits(benefit_id)
);

-- New Tables: Student Clubs and Internships

CREATE TABLE student_clubs (
    club_id SERIAL PRIMARY KEY,
    club_name VARCHAR(50) NOT NULL,
    faculty_id INT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (faculty_id) REFERENCES faculties(faculty_id)
);

CREATE TABLE student_club_memberships (
    student_id INT,
    club_id INT,
    join_date DATE,
    PRIMARY KEY (student_id, club_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (club_id) REFERENCES student_clubs(club_id)
);

CREATE TABLE internships (
    internship_id SERIAL PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    position VARCHAR(50) NOT NULL,
    student_id INT,
    start_date DATE,
    end_date DATE,
    is_paid BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

-- Insert Data

INSERT INTO campuses (campus_name) VALUES 
('North Campus'), ('South Campus'), ('East Campus'), ('West Campus'), ('Central Campus');

INSERT INTO faculties (faculty_name) VALUES 
('Engineering'), ('Science'), ('Humanities'), ('Business'), ('Law'),
('Medicine'), ('Education'), ('Computer Science'), ('Architecture'), ('Psychology');

INSERT INTO faculty_campuses (faculty_id, campus_id) VALUES 
(1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4), (8, 4), (9, 5), (10, 5);

INSERT INTO students (name, mentor_id, faculty_id) VALUES 
('Alice', NULL, 1), ('Bob', 1, 2), ('Charlie', 1, 3), ('Diana', 2, 4), ('Eve', 2, 5),
('Frank', 3, 6), ('Grace', 4, 7), ('Hank', 1, 8), ('Ivy', 5, 9), ('Jack', 6, 10);

INSERT INTO student_clubs (club_name, faculty_id) VALUES 
('Robotics Club', 1), 
('Math Club', 2), 
('Literature Society', 3), 
('Entrepreneurship Club', 4), 
('Law Debate Team', 5),
('Photography Club', 6),
('Music Ensemble', 7),
('Drama Society', 8),
('Art Club', 9),
('Coding Club', 10),
('Environmental Club', 1),
('Chess Club', 2),
('Film Club', 3),
('Dance Troupe', 6),
('Astronomy Club', 7);

INSERT INTO student_club_memberships (student_id, club_id, join_date) 
SELECT student_id, (SELECT club_id FROM student_clubs ORDER BY RANDOM() LIMIT 1), '2024-02-01' 
FROM students LIMIT 30;

INSERT INTO internships (company_name, position, student_id, start_date, end_date, is_paid) 
SELECT 'TechCorp', 'Software Intern', student_id, '2024-06-01', '2024-08-31', TRUE 
FROM students LIMIT 20;

INSERT INTO internships (company_name, position, student_id, start_date, end_date, is_paid) 
SELECT 'FinServe', 'Financial Analyst Intern', student_id, '2024-06-01', '2024-08-31', TRUE 
FROM students LIMIT 15;

INSERT INTO internships (company_name, position, student_id, start_date, end_date, is_paid) 
SELECT 'GreenTech Solutions', 'Sustainability Intern', student_id, '2024-06-01', '2024-08-31', TRUE 
FROM students LIMIT 10;

INSERT INTO internships (company_name, position, student_id, start_date, end_date, is_paid) 
SELECT 'MedHealth', 'Research Intern', student_id, '2024-06-01', '2024-08-31', TRUE 
FROM students LIMIT 12;

INSERT INTO internships (company_name, position, student_id, start_date, end_date, is_paid) 
SELECT 'DesignWorks', 'Graphic Design Intern', student_id, '2024-06-01', '2024-08-31', TRUE 
FROM students LIMIT 8;

DO $$ 
DECLARE i INT; 
BEGIN 
    FOR i IN 1..150 LOOP 
        INSERT INTO students (name, mentor_id, faculty_id) 
        VALUES ('Student' || i, (SELECT student_id FROM students ORDER BY RANDOM() LIMIT 1), 
                (SELECT faculty_id FROM faculties ORDER BY RANDOM() LIMIT 1)); 
    END LOOP; 
END $$;

DO $$ 
DECLARE i INT; 
BEGIN 
    FOR i IN 1..100 LOOP 
        INSERT INTO courses (course_name, faculty_id) 
        VALUES ('Course ' || i, (SELECT faculty_id FROM faculties ORDER BY RANDOM() LIMIT 1)); 
    END LOOP; 
END $$;

DO $$ 
DECLARE i INT; 
BEGIN 
    FOR i IN 1..300 LOOP 
        INSERT INTO assignments (assignment_name, course_id, assigned_student_id) 
        VALUES ('Assignment ' || i, (SELECT course_id FROM courses ORDER BY RANDOM() LIMIT 1), 
                (SELECT student_id FROM students ORDER BY RANDOM() LIMIT 1)); 
    END LOOP; 
END $$;

INSERT INTO scholarships (student_id, amount, effective_date) 
SELECT student_id, ROUND(RANDOM() * 5000 + 1000), '2024-01-01' 
FROM students LIMIT 50;

INSERT INTO benefits (benefit_name, description) VALUES 
('Travel Allowance', 'Funding for academic travel'), 
('Lab Grants', 'Access to additional lab funding'), 
('Tuition Reimbursement', 'Reimbursement for continuing education');

DO $$ 
DECLARE i INT; 
BEGIN 
    FOR i IN 1..40 LOOP 
        INSERT INTO professors (name, senior_professor_id, faculty_id) 
        VALUES ('Professor' || i, (SELECT professor_id FROM professors ORDER BY RANDOM() LIMIT 1), 
                (SELECT faculty_id FROM faculties ORDER BY RANDOM() LIMIT 1)); 
    END LOOP; 
END $$;

DO $$ 
DECLARE i INT; 
BEGIN 
    FOR i IN 1..30 LOOP 
        INSERT INTO professor_benefits (professor_id, benefit_id, start_date, end_date) 
        SELECT p.professor_id, b.benefit_id, '2023-01-01', '2025-12-31'
        FROM (SELECT professor_id FROM professors ORDER BY RANDOM() LIMIT 1) p,
             (SELECT benefit_id FROM benefits ORDER BY RANDOM() LIMIT 1) b
        ON CONFLICT (professor_id, benefit_id) DO NOTHING; 
    END LOOP; 
END $$;