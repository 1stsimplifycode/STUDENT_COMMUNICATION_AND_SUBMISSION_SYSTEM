-- ============================================================================
-- NEUROSYNC: DATABASE SCHEMA DEFINITION
-- Student Academic Communication and Submission System
-- Team: Adishree, Bhavani & Monica
-- ============================================================================

-- Drop existing database if exists and create fresh
DROP DATABASE IF EXISTS neurosync_db;
CREATE DATABASE neurosync_db;
USE neurosync_db;

-- ============================================================================
-- TABLE 1: USER (Base authentication table)
-- ============================================================================
CREATE TABLE user (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE,
    role ENUM('admin', 'teacher', 'student') NOT NULL,
    access_level INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    INDEX idx_username (username),
    INDEX idx_role (role)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 2: TEACHER
-- ============================================================================
CREATE TABLE teacher (
    teacher_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT UNIQUE,
    name VARCHAR(100) NOT NULL,
    subject_taught VARCHAR(100) NOT NULL,
    department VARCHAR(100),
    contact_number VARCHAR(15),
    email VARCHAR(100) UNIQUE NOT NULL,
    office_location VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE,
    INDEX idx_teacher_email (email),
    INDEX idx_teacher_department (department)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 3: STUDENT
-- ============================================================================
CREATE TABLE student (
    student_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT UNIQUE,
    name VARCHAR(100) NOT NULL,
    class VARCHAR(50) NOT NULL,
    roll_number VARCHAR(20) NOT NULL,
    contact_number VARCHAR(15),
    email VARCHAR(100) UNIQUE NOT NULL,
    preferred_communication_channel VARCHAR(50) DEFAULT 'LMS',
    teacher_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id) ON DELETE SET NULL,
    UNIQUE KEY unique_class_roll (class, roll_number),
    INDEX idx_student_class (class),
    INDEX idx_student_email (email)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 4: LMS (Learning Management System)
-- ============================================================================
CREATE TABLE lms (
    lms_id INT PRIMARY KEY AUTO_INCREMENT,
    platform_name VARCHAR(100) NOT NULL,
    api_endpoint VARCHAR(255),
    access_token VARCHAR(255),
    integration_status ENUM('Active', 'Inactive') DEFAULT 'Active',
    access_level INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_platform_name (platform_name)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 5: ASSIGNMENT
-- ============================================================================
CREATE TABLE assignment (
    assignment_id INT PRIMARY KEY AUTO_INCREMENT,
    teacher_id INT NOT NULL,
    lms_id INT,
    subject VARCHAR(100) NOT NULL,
    class VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    max_marks INT DEFAULT 100,
    due_date DATE NOT NULL,
    submission_mode VARCHAR(50) DEFAULT 'Online',
    submission_deadline DATETIME NOT NULL,
    submission_instructions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id) ON DELETE CASCADE,
    FOREIGN KEY (lms_id) REFERENCES lms(lms_id) ON DELETE SET NULL,
    INDEX idx_assignment_class (class),
    INDEX idx_assignment_teacher (teacher_id),
    INDEX idx_assignment_due_date (due_date),
    FULLTEXT INDEX idx_assignment_search (title, description)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 6: SUBMISSION
-- ============================================================================
CREATE TABLE submission (
    submission_id INT PRIMARY KEY AUTO_INCREMENT,
    assignment_id INT NOT NULL,
    student_id INT NOT NULL,
    submission_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    file_attachment_path VARCHAR(500),
    status ENUM('pending', 'submitted', 'late', 'graded') DEFAULT 'pending',
    marks_obtained INT,
    grading_remarks TEXT,
    graded_by INT,
    graded_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assignment_id) REFERENCES assignment(assignment_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (graded_by) REFERENCES teacher(teacher_id) ON DELETE SET NULL,
    UNIQUE KEY unique_student_assignment (assignment_id, student_id),
    INDEX idx_submission_student (student_id),
    INDEX idx_submission_assignment (assignment_id),
    INDEX idx_submission_status (status),
    INDEX idx_submission_timestamp (submission_timestamp)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 7: INSTANT_MESSAGING_PLATFORM
-- ============================================================================
CREATE TABLE instant_messaging_platform (
    platform_id INT PRIMARY KEY AUTO_INCREMENT,
    platform_name VARCHAR(50) NOT NULL UNIQUE,
    api_endpoint VARCHAR(255),
    authentication_token VARCHAR(255),
    status ENUM('Active', 'Inactive') DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_platform_status (status)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 8: NOTIFICATION
-- ============================================================================
CREATE TABLE notification (
    notification_id INT PRIMARY KEY AUTO_INCREMENT,
    assignment_id INT,
    student_id INT,
    mode_of_alert ENUM('LMS', 'WhatsApp', 'Telegram', 'Email') NOT NULL,
    message_content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivery_status ENUM('Sent', 'Delivered', 'Failed', 'Pending') DEFAULT 'Pending',
    target_audience ENUM('Individual', 'Class', 'All') DEFAULT 'Individual',
    FOREIGN KEY (assignment_id) REFERENCES assignment(assignment_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
    INDEX idx_notification_student (student_id),
    INDEX idx_notification_assignment (assignment_id),
    INDEX idx_notification_timestamp (timestamp),
    INDEX idx_notification_status (delivery_status)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 9: STUDENT_BEHAVIOR_ANALYTICS
-- ============================================================================
CREATE TABLE student_behavior_analytics (
    behavior_id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT UNIQUE,
    total_submissions INT DEFAULT 0,
    late_submissions INT DEFAULT 0,
    on_time_submissions INT DEFAULT 0,
    average_delay DECIMAL(5,2) DEFAULT 0.00,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
    INDEX idx_behavior_student (student_id)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 10: ACTION_LOG (Audit trail)
-- ============================================================================
CREATE TABLE action_log (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    description TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE SET NULL,
    INDEX idx_log_user (user_id),
    INDEX idx_log_timestamp (timestamp),
    INDEX idx_log_action (action)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 11: EXPERT_OBSERVATION (AI/ML feature tracking)
-- ============================================================================
CREATE TABLE expert_observation (
    observation_id INT PRIMARY KEY AUTO_INCREMENT,
    teacher_id INT,
    student_id INT,
    action_type VARCHAR(50),
    observation_data JSON,
    context_data JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
    INDEX idx_observation_teacher (teacher_id),
    INDEX idx_observation_student (student_id),
    INDEX idx_observation_timestamp (timestamp)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 12: EXPERT_MEMORY (Learning patterns storage)
-- ============================================================================
CREATE TABLE expert_memory (
    memory_id INT PRIMARY KEY AUTO_INCREMENT,
    context_pattern VARCHAR(255),
    action_taken VARCHAR(255),
    outcome VARCHAR(100),
    success_score DECIMAL(3,2),
    usage_count INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_memory_pattern (context_pattern),
    INDEX idx_memory_score (success_score)
) ENGINE=InnoDB;

-- ============================================================================
-- TABLE 13: EXPERT_SUGGESTION (AI recommendations)
-- ============================================================================
CREATE TABLE expert_suggestion (
    suggestion_id INT PRIMARY KEY AUTO_INCREMENT,
    target_user_id INT,
    suggestion_type VARCHAR(50),
    suggestion_text TEXT,
    priority ENUM('Low', 'Medium', 'High') DEFAULT 'Medium',
    status ENUM('Pending', 'Viewed', 'Acted', 'Dismissed') DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (target_user_id) REFERENCES user(user_id) ON DELETE CASCADE,
    INDEX idx_suggestion_user (target_user_id),
    INDEX idx_suggestion_status (status),
    INDEX idx_suggestion_priority (priority)
) ENGINE=InnoDB;

-- ============================================================================
-- INSERT SAMPLE DATA
-- ============================================================================

-- Insert admin user (password: Sr1*ganesh - SHA256 hashed)
INSERT INTO user (username, password_hash, role, access_level, email) VALUES
('root', 'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d662f1c2ba8f9e3f5f9c5b68f', 'admin', 5, 'admin@neurosync.edu');

-- Insert LMS platforms
INSERT INTO lms (platform_name, api_endpoint, integration_status) VALUES
('Moodle', 'https://moodle.example.edu/api', 'Active'),
('Canvas', 'https://canvas.example.edu/api', 'Active'),
('Google Classroom', 'https://classroom.googleapis.com/v1', 'Active');

-- Insert Instant Messaging Platforms
INSERT INTO instant_messaging_platform (platform_name, api_endpoint, status) VALUES
('WhatsApp', 'https://api.whatsapp.com/send', 'Active'),
('Telegram', 'https://api.telegram.org/bot', 'Active'),
('Discord', 'https://discord.com/api/webhooks', 'Active');

-- Insert Teachers
-- Password: bhavani@123 / monica@123 (SHA256 hashed)
INSERT INTO user (username, password_hash, role, access_level, email) VALUES
('bhavani', '9f735e0df9a1ddc702bf0a1a7b83033f9f7153a00c29de82cedadc9957289b05', 'teacher', 2, 'bhavani@neurosync.edu'),
('monica', 'b9c950640e1b3740e98acb93e669c65766f6670dd1609ba91d36479c27619f39', 'teacher', 2, 'monica@neurosync.edu');

INSERT INTO teacher (user_id, name, subject_taught, department, contact_number, email, office_location) VALUES
(2, 'Dr. Bhavani Kumar', 'Database Management Systems', 'Computer Science', '+91-9876543210', 'bhavani@neurosync.edu', 'CS-Block, Room 301'),
(3, 'Prof. Monica Sharma', 'Data Structures & Algorithms', 'Computer Science', '+91-9876543211', 'monica@neurosync.edu', 'CS-Block, Room 302');

-- Insert Students
-- Password for all: stud123 (hashed)
INSERT INTO user (username, password_hash, role, access_level, email) VALUES
('student1', '4d05f08f95e5e18c3e96b8e9e7f4b3c4d5a8e4b6f8a9c5e7f3d4a8b9c7e6f5d4', 'student', 1, 'student1@neurosync.edu'),
('student2', '4d05f08f95e5e18c3e96b8e9e7f4b3c4d5a8e4b6f8a9c5e7f3d4a8b9c7e6f5d4', 'student', 1, 'student2@neurosync.edu'),
('student3', '4d05f08f95e5e18c3e96b8e9e7f4b3c4d5a8e4b6f8a9c5e7f3d4a8b9c7e6f5d4', 'student', 1, 'student3@neurosync.edu'),
('student4', '4d05f08f95e5e18c3e96b8e9e7f4b3c4d5a8e4b6f8a9c5e7f3d4a8b9c7e6f5d4', 'student', 1, 'student4@neurosync.edu'),
('student5', '4d05f08f95e5e18c3e96b8e9e7f4b3c4d5a8e4b6f8a9c5e7f3d4a8b9c7e6f5d4', 'student', 1, 'student5@neurosync.edu');

INSERT INTO student (user_id, name, class, roll_number, contact_number, email, preferred_communication_channel, teacher_id) VALUES
(4, 'Rajesh Kumar', 'CSE-3A', '001', '+91-9123456781', 'student1@neurosync.edu', 'WhatsApp', 1),
(5, 'Priya Sharma', 'CSE-3A', '002', '+91-9123456782', 'student2@neurosync.edu', 'Telegram', 1),
(6, 'Amit Patel', 'CSE-3A', '003', '+91-9123456783', 'student3@neurosync.edu', 'LMS', 1),
(7, 'Sneha Reddy', 'CSE-3B', '001', '+91-9123456784', 'student4@neurosync.edu', 'WhatsApp', 2),
(8, 'Karthik Rao', 'CSE-3B', '002', '+91-9123456785', 'student5@neurosync.edu', 'LMS', 2);

-- Insert Sample Assignments
INSERT INTO assignment (teacher_id, lms_id, subject, class, title, description, max_marks, due_date, submission_deadline, submission_instructions) VALUES
(1, 1, 'Database Management Systems', 'CSE-3A', 'SQL Query Assignment', 'Write complex SQL queries for the given problems', 100, DATE_ADD(CURDATE(), INTERVAL 7 DAY), DATE_ADD(NOW(), INTERVAL 7 DAY), 'Submit as .sql file'),
(1, 1, 'Database Management Systems', 'CSE-3A', 'ER Diagram Design', 'Design ER diagram for library management system', 50, DATE_ADD(CURDATE(), INTERVAL 10 DAY), DATE_ADD(NOW(), INTERVAL 10 DAY), 'Submit as PDF or image'),
(2, 2, 'Data Structures', 'CSE-3B', 'Binary Tree Implementation', 'Implement binary search tree in C++', 100, DATE_ADD(CURDATE(), INTERVAL 5 DAY), DATE_ADD(NOW(), INTERVAL 5 DAY), 'Submit source code with documentation');

-- Insert Sample Submissions
INSERT INTO submission (assignment_id, student_id, submission_timestamp, file_attachment_path, status, marks_obtained, graded_by, graded_at) VALUES
(1, 1, NOW() - INTERVAL 2 DAY, 'submissions/student1_sql_assignment.sql', 'graded', 85, 1, NOW() - INTERVAL 1 DAY),
(1, 2, NOW() - INTERVAL 1 DAY, 'submissions/student2_sql_assignment.sql', 'graded', 92, 1, NOW()),
(1, 3, NOW() - INTERVAL 3 HOUR, 'submissions/student3_sql_assignment.sql', 'submitted', NULL, NULL, NULL),
(2, 1, NOW() - INTERVAL 1 DAY, 'submissions/student1_er_diagram.pdf', 'submitted', NULL, NULL, NULL);

-- Insert Sample Notifications
INSERT INTO notification (assignment_id, student_id, mode_of_alert, message_content, delivery_status, target_audience) VALUES
(1, 1, 'WhatsApp', 'Reminder: SQL Assignment due in 2 days', 'Delivered', 'Individual'),
(1, 2, 'Telegram', 'Reminder: SQL Assignment due in 2 days', 'Delivered', 'Individual'),
(1, 3, 'LMS', 'Reminder: SQL Assignment due in 2 days', 'Delivered', 'Individual'),
(2, 1, 'WhatsApp', 'New Assignment: ER Diagram Design', 'Delivered', 'Individual'),
(3, 4, 'WhatsApp', 'New Assignment: Binary Tree Implementation', 'Delivered', 'Individual'),
(3, 5, 'LMS', 'New Assignment: Binary Tree Implementation', 'Delivered', 'Individual');

-- Insert Sample Behavior Analytics
INSERT INTO student_behavior_analytics (student_id, total_submissions, late_submissions, on_time_submissions, average_delay) VALUES
(1, 2, 0, 2, 0.00),
(2, 1, 0, 1, 0.00),
(3, 1, 0, 1, 0.00),
(4, 0, 0, 0, 0.00),
(5, 0, 0, 0, 0.00);

-- Insert Sample Action Logs
INSERT INTO action_log (user_id, action, description) VALUES
(2, 'CREATE_ASSIGNMENT', 'Created assignment: SQL Query Assignment for class CSE-3A'),
(2, 'CREATE_ASSIGNMENT', 'Created assignment: ER Diagram Design for class CSE-3A'),
(3, 'CREATE_ASSIGNMENT', 'Created assignment: Binary Tree Implementation for class CSE-3B'),
(2, 'GRADE_SUBMISSION', 'Graded submission ID: 1 with marks: 85'),
(2, 'GRADE_SUBMISSION', 'Graded submission ID: 2 with marks: 92');

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Show all tables
SHOW TABLES;

-- Show table structure
DESCRIBE user;
DESCRIBE teacher;
DESCRIBE student;
DESCRIBE assignment;
DESCRIBE submission;

-- Show sample data counts
SELECT 'Users' as Entity, COUNT(*) as Count FROM user
UNION ALL
SELECT 'Teachers', COUNT(*) FROM teacher
UNION ALL
SELECT 'Students', COUNT(*) FROM student
UNION ALL
SELECT 'Assignments', COUNT(*) FROM assignment
UNION ALL
SELECT 'Submissions', COUNT(*) FROM submission
UNION ALL
SELECT 'Notifications', COUNT(*) FROM notification;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================
SELECT '✓ Database schema created successfully!' as Status,
       'neurosync_db' as Database_Name,
       '13 tables created' as Tables,
       'Sample data inserted' as Data_Status;