-- ============================================================================
-- NEUROSYNC: FIX MISSING VIEWS
-- Run this if you get "Table doesn't exist" errors for views
-- ============================================================================

USE neurosync_db;

-- ============================================================================
-- CREATE ALL REQUIRED VIEWS
-- ============================================================================

-- View 1: Top Performing Students
DROP VIEW IF EXISTS top_performing_students;
CREATE VIEW top_performing_students AS
SELECT 
    s.student_id,
    s.name,
    s.class,
    COUNT(sub.submission_id) AS total_submissions,
    AVG(sub.marks_obtained) AS average_marks,
    SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) AS on_time_count,
    ROUND((SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) / COUNT(sub.submission_id)) * 100, 2) AS on_time_percentage
FROM student s
LEFT JOIN submission sub ON s.student_id = sub.student_id
WHERE sub.status IN ('submitted', 'late', 'graded')
GROUP BY s.student_id
HAVING average_marks >= 75
ORDER BY average_marks DESC, on_time_percentage DESC;

-- View 2: Assignment Completion Statistics
DROP VIEW IF EXISTS assignment_completion_stats;
CREATE VIEW assignment_completion_stats AS
SELECT 
    a.assignment_id,
    a.title,
    a.subject,
    a.class,
    a.due_date,
    t.name AS teacher_name,
    COUNT(DISTINCT st.student_id) AS total_students,
    COUNT(sub.submission_id) AS submissions_received,
    SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) AS on_time_submissions,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) AS late_submissions,
    ROUND((COUNT(sub.submission_id) / COUNT(DISTINCT st.student_id)) * 100, 2) AS completion_rate
FROM assignment a
JOIN teacher t ON a.teacher_id = t.teacher_id
LEFT JOIN student st ON a.class = st.class
LEFT JOIN submission sub ON a.assignment_id = sub.assignment_id
GROUP BY a.assignment_id;

-- View 3: Students at Risk
DROP VIEW IF EXISTS students_at_risk;
CREATE VIEW students_at_risk AS
SELECT 
    s.student_id,
    s.name,
    s.class,
    s.email,
    COUNT(sub.submission_id) AS total_submissions,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) AS late_submissions,
    ROUND((SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) / COUNT(sub.submission_id)) * 100, 2) AS late_percentage,
    sba.average_delay
FROM student s
JOIN submission sub ON s.student_id = sub.student_id
LEFT JOIN student_behavior_analytics sba ON s.student_id = sba.student_id
GROUP BY s.student_id
HAVING late_percentage > 40 OR late_submissions >= 3
ORDER BY late_percentage DESC;

-- View 4: Notification Effectiveness
DROP VIEW IF EXISTS notification_effectiveness;
CREATE VIEW notification_effectiveness AS
SELECT 
    n.mode_of_alert,
    COUNT(n.notification_id) AS total_notifications,
    SUM(CASE WHEN n.delivery_status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_count,
    SUM(CASE WHEN sub.submission_id IS NOT NULL THEN 1 ELSE 0 END) AS resulted_in_submission,
    ROUND((SUM(CASE WHEN sub.submission_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(n.notification_id)) * 100, 2) AS effectiveness_rate
FROM notification n
LEFT JOIN submission sub ON n.assignment_id = sub.assignment_id AND n.student_id = sub.student_id
GROUP BY n.mode_of_alert
ORDER BY effectiveness_rate DESC;

-- View 5: Teacher Workload (THE MISSING ONE!)
DROP VIEW IF EXISTS teacher_workload;
CREATE VIEW teacher_workload AS
SELECT 
    t.teacher_id,
    t.name,
    t.department,
    COUNT(DISTINCT a.assignment_id) AS total_assignments,
    COUNT(sub.submission_id) AS total_submissions_received,
    SUM(CASE WHEN sub.status = 'graded' THEN 1 ELSE 0 END) AS graded_submissions,
    SUM(CASE WHEN sub.status IN ('submitted', 'late') THEN 1 ELSE 0 END) AS pending_grading
FROM teacher t
LEFT JOIN assignment a ON t.teacher_id = a.teacher_id
LEFT JOIN submission sub ON a.assignment_id = sub.assignment_id
GROUP BY t.teacher_id
ORDER BY pending_grading DESC;

-- View 6: Class Performance Summary
DROP VIEW IF EXISTS class_performance_summary;
CREATE VIEW class_performance_summary AS
SELECT 
    s.class,
    COUNT(DISTINCT s.student_id) AS total_students,
    COUNT(sub.submission_id) AS total_submissions,
    AVG(sub.marks_obtained) AS avg_marks,
    SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) AS on_time_count,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) AS late_count
FROM student s
LEFT JOIN submission sub ON s.student_id = sub.student_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY s.class
ORDER BY avg_marks DESC;

-- ============================================================================
-- VERIFY ALL VIEWS ARE CREATED
-- ============================================================================

SELECT 
    TABLE_NAME as view_name,
    'Created Successfully' as status
FROM INFORMATION_SCHEMA.VIEWS 
WHERE TABLE_SCHEMA = 'neurosync_db'
ORDER BY TABLE_NAME;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

SELECT 
    '✓ All views created successfully!' as Status,
    'You can now use the application without errors' as Message;