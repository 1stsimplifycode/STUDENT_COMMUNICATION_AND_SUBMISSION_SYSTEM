-- ============================================================================
-- NEUROSYNC: COMPLEX SQL QUERIES FOR ANALYSIS AND REPORTING
-- ============================================================================

USE neurosync_db;

-- ============================================================================
-- 1. NESTED QUERIES
-- ============================================================================

-- Find students who have never submitted late
SELECT s.student_id, s.name, s.class, s.email
FROM student s
WHERE s.student_id NOT IN (
    SELECT DISTINCT student_id 
    FROM submission 
    WHERE status = 'late'
)
AND s.student_id IN (
    SELECT DISTINCT student_id 
    FROM submission
);

-- Find assignments with below-average submission rate
SELECT a.assignment_id, a.title, a.class, 
       (SELECT COUNT(*) FROM submission sub WHERE sub.assignment_id = a.assignment_id) as submission_count,
       (SELECT COUNT(*) FROM student st WHERE st.class = a.class) as total_students,
       ROUND((SELECT COUNT(*) FROM submission sub WHERE sub.assignment_id = a.assignment_id) / 
             (SELECT COUNT(*) FROM student st WHERE st.class = a.class) * 100, 2) as submission_rate
FROM assignment a
WHERE (SELECT COUNT(*) FROM submission sub WHERE sub.assignment_id = a.assignment_id) / 
      (SELECT COUNT(*) FROM student st WHERE st.class = a.class) < 
      (SELECT AVG(sub_rate) FROM (
          SELECT COUNT(DISTINCT sub.submission_id) / COUNT(DISTINCT st.student_id) as sub_rate
          FROM assignment a2
          JOIN student st ON st.class = a2.class
          LEFT JOIN submission sub ON sub.assignment_id = a2.assignment_id
          GROUP BY a2.assignment_id
      ) as avg_rates);

-- Find teachers whose students perform above average
SELECT t.teacher_id, t.name, t.department,
       AVG(sub.marks_obtained) as avg_marks
FROM teacher t
JOIN student s ON t.teacher_id = s.teacher_id
JOIN submission sub ON s.student_id = sub.student_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY t.teacher_id
HAVING AVG(sub.marks_obtained) > (
    SELECT AVG(marks_obtained) FROM submission WHERE marks_obtained IS NOT NULL
);

-- Students who submitted all assignments on time
SELECT s.student_id, s.name, s.class
FROM student s
WHERE NOT EXISTS (
    SELECT 1 FROM submission sub
    WHERE sub.student_id = s.student_id AND sub.status = 'late'
)
AND EXISTS (
    SELECT 1 FROM submission sub WHERE sub.student_id = s.student_id
);

-- ============================================================================
-- 2. JOIN QUERIES (ALL TYPES)
-- ============================================================================

-- INNER JOIN: Get all submissions with student and assignment details
SELECT 
    s.submission_id,
    st.name as student_name,
    st.class,
    a.title as assignment_title,
    a.subject,
    t.name as teacher_name,
    s.submission_timestamp,
    s.status,
    s.marks_obtained
FROM submission s
INNER JOIN student st ON s.student_id = st.student_id
INNER JOIN assignment a ON s.assignment_id = a.assignment_id
INNER JOIN teacher t ON a.teacher_id = t.teacher_id
ORDER BY s.submission_timestamp DESC;

-- LEFT JOIN: All assignments with submission count (including 0 submissions)
SELECT 
    a.assignment_id,
    a.title,
    a.class,
    a.due_date,
    t.name as teacher_name,
    COUNT(s.submission_id) as submission_count,
    (SELECT COUNT(*) FROM student WHERE class = a.class) as total_students
FROM assignment a
LEFT JOIN submission s ON a.assignment_id = s.assignment_id
LEFT JOIN teacher t ON a.teacher_id = t.teacher_id
GROUP BY a.assignment_id
ORDER BY a.due_date DESC;

-- RIGHT JOIN: All students with their submission counts (including students with no submissions)
SELECT 
    st.student_id,
    st.name,
    st.class,
    COUNT(s.submission_id) as total_submissions,
    SUM(CASE WHEN s.status = 'late' THEN 1 ELSE 0 END) as late_submissions
FROM submission s
RIGHT JOIN student st ON s.student_id = st.student_id
GROUP BY st.student_id;

-- SELF JOIN: Find students in the same class with similar performance
SELECT 
    s1.student_id as student1_id,
    s1.name as student1_name,
    s2.student_id as student2_id,
    s2.name as student2_name,
    s1.class,
    AVG(sub1.marks_obtained) as avg_marks1,
    AVG(sub2.marks_obtained) as avg_marks2
FROM student s1
JOIN student s2 ON s1.class = s2.class AND s1.student_id < s2.student_id
LEFT JOIN submission sub1 ON s1.student_id = sub1.student_id
LEFT JOIN submission sub2 ON s2.student_id = sub2.student_id
GROUP BY s1.student_id, s2.student_id
HAVING ABS(AVG(sub1.marks_obtained) - AVG(sub2.marks_obtained)) < 5;

-- CROSS JOIN: Generate notification matrix (all students × all notification modes)
SELECT 
    s.student_id,
    s.name,
    imp.platform_name,
    s.preferred_communication_channel,
    CASE 
        WHEN s.preferred_communication_channel = imp.platform_name THEN 'Preferred'
        ELSE 'Alternative'
    END as channel_type
FROM student s
CROSS JOIN instant_messaging_platform imp;

-- ============================================================================
-- 3. AGGREGATE QUERIES
-- ============================================================================

-- Overall system statistics
SELECT 
    COUNT(DISTINCT u.user_id) as total_users,
    COUNT(DISTINCT t.teacher_id) as total_teachers,
    COUNT(DISTINCT s.student_id) as total_students,
    COUNT(DISTINCT a.assignment_id) as total_assignments,
    COUNT(DISTINCT sub.submission_id) as total_submissions,
    AVG(sub.marks_obtained) as overall_avg_marks,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) as total_late_submissions,
    ROUND(SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) / 
          COUNT(sub.submission_id) * 100, 2) as on_time_percentage
FROM user u
LEFT JOIN teacher t ON u.user_id = t.user_id
LEFT JOIN student s ON u.user_id = s.user_id
LEFT JOIN assignment a ON t.teacher_id = a.teacher_id
LEFT JOIN submission sub ON a.assignment_id = sub.assignment_id;

-- Class-wise performance analysis
SELECT 
    s.class,
    COUNT(DISTINCT s.student_id) as total_students,
    COUNT(sub.submission_id) as total_submissions,
    AVG(sub.marks_obtained) as avg_marks,
    MAX(sub.marks_obtained) as highest_marks,
    MIN(sub.marks_obtained) as lowest_marks,
    STDDEV(sub.marks_obtained) as marks_std_dev,
    SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) as on_time_count,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) as late_count
FROM student s
LEFT JOIN submission sub ON s.student_id = sub.student_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY s.class
ORDER BY avg_marks DESC;

-- Subject-wise analysis
SELECT 
    a.subject,
    COUNT(DISTINCT a.assignment_id) as assignments_created,
    COUNT(sub.submission_id) as submissions_received,
    AVG(sub.marks_obtained) as avg_marks,
    SUM(CASE WHEN sub.status = 'graded' THEN 1 ELSE 0 END) as graded_count,
    SUM(CASE WHEN sub.status IN ('submitted', 'late') THEN 1 ELSE 0 END) as pending_grading
FROM assignment a
LEFT JOIN submission sub ON a.assignment_id = sub.assignment_id
GROUP BY a.subject
ORDER BY assignments_created DESC;

-- Monthly submission trends
SELECT 
    DATE_FORMAT(sub.submission_timestamp, '%Y-%m') as month,
    COUNT(sub.submission_id) as total_submissions,
    SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) as on_time,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) as late,
    AVG(sub.marks_obtained) as avg_marks
FROM submission sub
GROUP BY DATE_FORMAT(sub.submission_timestamp, '%Y-%m')
ORDER BY month DESC;

-- Teacher workload distribution
SELECT 
    t.teacher_id,
    t.name,
    t.department,
    COUNT(DISTINCT a.assignment_id) as assignments_created,
    COUNT(DISTINCT s.student_id) as students_managed,
    COUNT(sub.submission_id) as submissions_to_grade,
    SUM(CASE WHEN sub.status = 'graded' THEN 1 ELSE 0 END) as already_graded,
    ROUND(SUM(CASE WHEN sub.status = 'graded' THEN 1 ELSE 0 END) / 
          COUNT(sub.submission_id) * 100, 2) as grading_completion_rate
FROM teacher t
LEFT JOIN assignment a ON t.teacher_id = a.teacher_id
LEFT JOIN student s ON t.teacher_id = s.teacher_id
LEFT JOIN submission sub ON a.assignment_id = sub.assignment_id
GROUP BY t.teacher_id
ORDER BY grading_completion_rate ASC;

-- ============================================================================
-- 4. WINDOW FUNCTIONS
-- ============================================================================

-- Rank students by average marks within each class
SELECT 
    s.student_id,
    s.name,
    s.class,
    AVG(sub.marks_obtained) as avg_marks,
    RANK() OVER (PARTITION BY s.class ORDER BY AVG(sub.marks_obtained) DESC) as class_rank,
    DENSE_RANK() OVER (ORDER BY AVG(sub.marks_obtained) DESC) as overall_rank
FROM student s
JOIN submission sub ON s.student_id = sub.student_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY s.student_id
ORDER BY s.class, class_rank;

-- Running total of submissions over time
SELECT 
    DATE(submission_timestamp) as submission_date,
    COUNT(*) as daily_submissions,
    SUM(COUNT(*)) OVER (ORDER BY DATE(submission_timestamp)) as cumulative_submissions
FROM submission
GROUP BY DATE(submission_timestamp)
ORDER BY submission_date;

-- Moving average of marks for each student
SELECT 
    s.student_id,
    s.name,
    a.title,
    sub.marks_obtained,
    sub.submission_timestamp,
    AVG(sub.marks_obtained) OVER (
        PARTITION BY s.student_id 
        ORDER BY sub.submission_timestamp 
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) as moving_avg_3_submissions
FROM student s
JOIN submission sub ON s.student_id = sub.student_id
JOIN assignment a ON sub.assignment_id = a.assignment_id
WHERE sub.marks_obtained IS NOT NULL
ORDER BY s.student_id, sub.submission_timestamp;

-- Percentile distribution of marks
SELECT 
    s.student_id,
    s.name,
    AVG(sub.marks_obtained) as avg_marks,
    PERCENT_RANK() OVER (ORDER BY AVG(sub.marks_obtained)) as percentile_rank,
    NTILE(4) OVER (ORDER BY AVG(sub.marks_obtained)) as quartile
FROM student s
JOIN submission sub ON s.student_id = sub.student_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY s.student_id;

-- ============================================================================
-- 5. ADVANCED ANALYTICAL QUERIES
-- ============================================================================

-- Find correlation between submission timing and marks
SELECT 
    CASE 
        WHEN TIMESTAMPDIFF(DAY, a.submission_deadline, sub.submission_timestamp) < 0 
        THEN 'Early'
        WHEN TIMESTAMPDIFF(DAY, a.submission_deadline, sub.submission_timestamp) = 0 
        THEN 'On Time'
        ELSE 'Late'
    END as submission_timing,
    COUNT(*) as submission_count,
    AVG(sub.marks_obtained) as avg_marks,
    MIN(sub.marks_obtained) as min_marks,
    MAX(sub.marks_obtained) as max_marks
FROM submission sub
JOIN assignment a ON sub.assignment_id = a.assignment_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY submission_timing;

-- Identify high-performing vs struggling students
SELECT 
    s.student_id,
    s.name,
    s.class,
    COUNT(sub.submission_id) as total_submissions,
    AVG(sub.marks_obtained) as avg_marks,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) as late_count,
    CASE 
        WHEN AVG(sub.marks_obtained) >= 80 AND SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) = 0 
        THEN 'Excellent'
        WHEN AVG(sub.marks_obtained) >= 60 AND SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) <= 1 
        THEN 'Good'
        WHEN AVG(sub.marks_obtained) >= 40 
        THEN 'Average'
        ELSE 'Needs Support'
    END as performance_category
FROM student s
JOIN submission sub ON s.student_id = sub.student_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY s.student_id
ORDER BY performance_category, avg_marks DESC;

-- Notification effectiveness by platform
SELECT 
    n.mode_of_alert,
    COUNT(DISTINCT n.notification_id) as notifications_sent,
    COUNT(DISTINCT CASE WHEN n.delivery_status = 'Delivered' THEN n.notification_id END) as delivered,
    COUNT(DISTINCT sub.submission_id) as resulted_in_submission,
    ROUND(COUNT(DISTINCT sub.submission_id) / COUNT(DISTINCT n.notification_id) * 100, 2) as conversion_rate,
    AVG(TIMESTAMPDIFF(HOUR, n.timestamp, sub.submission_timestamp)) as avg_response_hours
FROM notification n
LEFT JOIN submission sub ON n.assignment_id = sub.assignment_id 
                        AND n.student_id = sub.student_id
                        AND sub.submission_timestamp > n.timestamp
GROUP BY n.mode_of_alert
ORDER BY conversion_rate DESC;

-- Assignment difficulty analysis (based on average marks and submission rate)
SELECT 
    a.assignment_id,
    a.title,
    a.subject,
    a.max_marks,
    COUNT(sub.submission_id) as submissions_received,
    (SELECT COUNT(*) FROM student WHERE class = a.class) as total_students,
    ROUND(COUNT(sub.submission_id) / (SELECT COUNT(*) FROM student WHERE class = a.class) * 100, 2) as submission_rate,
    AVG(sub.marks_obtained) as avg_marks,
    ROUND(AVG(sub.marks_obtained) / a.max_marks * 100, 2) as avg_percentage,
    CASE 
        WHEN AVG(sub.marks_obtained) / a.max_marks >= 0.8 THEN 'Easy'
        WHEN AVG(sub.marks_obtained) / a.max_marks >= 0.6 THEN 'Moderate'
        WHEN AVG(sub.marks_obtained) / a.max_marks >= 0.4 THEN 'Challenging'
        ELSE 'Difficult'
    END as difficulty_level
FROM assignment a
LEFT JOIN submission sub ON a.assignment_id = sub.assignment_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY a.assignment_id
HAVING COUNT(sub.submission_id) >= 3
ORDER BY avg_percentage;

-- Time-based submission patterns
SELECT 
    HOUR(sub.submission_timestamp) as hour_of_day,
    COUNT(*) as submission_count,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) as late_submissions,
    ROUND(SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) as late_percentage
FROM submission sub
GROUP BY HOUR(sub.submission_timestamp)
ORDER BY hour_of_day;

-- Day of week submission patterns
SELECT 
    DAYNAME(sub.submission_timestamp) as day_of_week,
    DAYOFWEEK(sub.submission_timestamp) as day_number,
    COUNT(*) as submission_count,
    AVG(sub.marks_obtained) as avg_marks,
    SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) as on_time_count
FROM submission sub
WHERE sub.marks_obtained IS NOT NULL
GROUP BY DAYNAME(sub.submission_timestamp), DAYOFWEEK(sub.submission_timestamp)
ORDER BY day_number;

-- ============================================================================
-- 6. COHORT ANALYSIS
-- ============================================================================

-- Student cohort performance by class
WITH class_performance AS (
    SELECT 
        s.class,
        s.student_id,
        AVG(sub.marks_obtained) as student_avg,
        COUNT(sub.submission_id) as submission_count
    FROM student s
    JOIN submission sub ON s.student_id = sub.student_id
    WHERE sub.marks_obtained IS NOT NULL
    GROUP BY s.class, s.student_id
)
SELECT 
    class,
    COUNT(student_id) as students_in_class,
    AVG(student_avg) as class_average,
    MAX(student_avg) as highest_student_avg,
    MIN(student_avg) as lowest_student_avg,
    STDDEV(student_avg) as performance_variance
FROM class_performance
GROUP BY class
ORDER BY class_average DESC;

-- Retention analysis: Students who submit consistently
WITH submission_streak AS (
    SELECT 
        s.student_id,
        s.name,
        COUNT(DISTINCT sub.assignment_id) as assignments_submitted,
        (SELECT COUNT(*) FROM assignment a WHERE a.class = s.class) as total_assignments,
        ROUND(COUNT(DISTINCT sub.assignment_id) / 
              (SELECT COUNT(*) FROM assignment a WHERE a.class = s.class) * 100, 2) as completion_rate
    FROM student s
    LEFT JOIN submission sub ON s.student_id = sub.student_id
    GROUP BY s.student_id
)
SELECT 
    student_id,
    name,
    assignments_submitted,
    total_assignments,
    completion_rate,
    CASE 
        WHEN completion_rate >= 90 THEN 'Highly Engaged'
        WHEN completion_rate >= 70 THEN 'Engaged'
        WHEN completion_rate >= 50 THEN 'Moderately Engaged'
        WHEN completion_rate > 0 THEN 'Low Engagement'
        ELSE 'Not Engaged'
    END as engagement_level
FROM submission_streak
ORDER BY completion_rate DESC;

-- ============================================================================
-- 7. PREDICTIVE QUERIES (Risk Assessment)
-- ============================================================================

-- Students at risk of poor performance
SELECT 
    s.student_id,
    s.name,
    s.class,
    s.email,
    COUNT(sub.submission_id) as total_submissions,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) as late_submissions,
    AVG(sub.marks_obtained) as current_avg_marks,
    sba.average_delay,
    CASE 
        WHEN SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) >= 3 THEN 'High Risk'
        WHEN AVG(sub.marks_obtained) < 50 THEN 'High Risk'
        WHEN SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) >= 2 
             OR AVG(sub.marks_obtained) < 60 THEN 'Medium Risk'
        ELSE 'Low Risk'
    END as risk_level,
    CONCAT(
        CASE WHEN SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) >= 2 
             THEN 'Frequent late submissions; ' ELSE '' END,
        CASE WHEN AVG(sub.marks_obtained) < 60 
             THEN 'Low marks; ' ELSE '' END,
        CASE WHEN sba.average_delay > 2 
             THEN 'High average delay' ELSE '' END
    ) as risk_factors
FROM student s
LEFT JOIN submission sub ON s.student_id = sub.student_id
LEFT JOIN student_behavior_analytics sba ON s.student_id = sba.student_id
WHERE sub.submission_id IS NOT NULL
GROUP BY s.student_id
HAVING risk_level IN ('High Risk', 'Medium Risk')
ORDER BY 
    CASE risk_level 
        WHEN 'High Risk' THEN 1 
        WHEN 'Medium Risk' THEN 2 
    END,
    late_submissions DESC;

-- ============================================================================
-- 8. COMPARATIVE ANALYSIS
-- ============================================================================

-- Compare current semester performance to overall average
SELECT 
    s.student_id,
    s.name,
    AVG(CASE WHEN sub.submission_timestamp >= DATE_SUB(NOW(), INTERVAL 3 MONTH) 
             THEN sub.marks_obtained END) as recent_avg,
    AVG(sub.marks_obtained) as overall_avg,
    AVG(CASE WHEN sub.submission_timestamp >= DATE_SUB(NOW(), INTERVAL 3 MONTH) 
             THEN sub.marks_obtained END) - AVG(sub.marks_obtained) as performance_change,
    CASE 
        WHEN AVG(CASE WHEN sub.submission_timestamp >= DATE_SUB(NOW(), INTERVAL 3 MONTH) 
                      THEN sub.marks_obtained END) > AVG(sub.marks_obtained) 
        THEN 'Improving'
        WHEN AVG(CASE WHEN sub.submission_timestamp >= DATE_SUB(NOW(), INTERVAL 3 MONTH) 
                      THEN sub.marks_obtained END) < AVG(sub.marks_obtained) 
        THEN 'Declining'
        ELSE 'Stable'
    END as trend
FROM student s
JOIN submission sub ON s.student_id = sub.student_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY s.student_id
HAVING COUNT(sub.submission_id) >= 5
ORDER BY performance_change DESC;

-- Teacher comparison by student outcomes
SELECT 
    t.teacher_id,
    t.name,
    t.department,
    COUNT(DISTINCT s.student_id) as students_taught,
    COUNT(DISTINCT a.assignment_id) as assignments_created,
    AVG(sub.marks_obtained) as avg_student_marks,
    SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) / 
        COUNT(sub.submission_id) * 100 as on_time_rate,
    RANK() OVER (ORDER BY AVG(sub.marks_obtained) DESC) as performance_rank
FROM teacher t
JOIN student s ON t.teacher_id = s.teacher_id
JOIN assignment a ON t.teacher_id = a.teacher_id
LEFT JOIN submission sub ON s.student_id = sub.student_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY t.teacher_id
ORDER BY avg_student_marks DESC;

-- ============================================================================
-- 9. DATA QUALITY & INTEGRITY CHECKS
-- ============================================================================

-- Check for orphaned records
SELECT 'Submissions without valid assignments' as check_type, COUNT(*) as count
FROM submission sub
LEFT JOIN assignment a ON sub.assignment_id = a.assignment_id
WHERE a.assignment_id IS NULL

UNION ALL

SELECT 'Submissions without valid students', COUNT(*)
FROM submission sub
LEFT JOIN student s ON sub.student_id = s.student_id
WHERE s.student_id IS NULL

UNION ALL

SELECT 'Notifications without valid assignments', COUNT(*)
FROM notification n
LEFT JOIN assignment a ON n.assignment_id = a.assignment_id
WHERE a.assignment_id IS NULL

UNION ALL

SELECT 'Students without valid teachers', COUNT(*)
FROM student s
LEFT JOIN teacher t ON s.teacher_id = t.teacher_id
WHERE t.teacher_id IS NULL;

-- Check for data anomalies
SELECT 
    'Marks exceeding maximum' as anomaly_type,
    COUNT(*) as anomaly_count
FROM submission sub
JOIN assignment a ON sub.assignment_id = a.assignment_id
WHERE sub.marks_obtained > a.max_marks

UNION ALL

SELECT 
    'Submissions before assignment creation',
    COUNT(*)
FROM submission sub
JOIN assignment a ON sub.assignment_id = a.assignment_id
WHERE sub.submission_timestamp < a.created_at

UNION ALL

SELECT 
    'Duplicate submissions',
    COUNT(*) - COUNT(DISTINCT CONCAT(student_id, '-', assignment_id))
FROM submission;

-- ============================================================================
-- 10. BUSINESS INTELLIGENCE QUERIES
-- ============================================================================

-- Executive dashboard summary
SELECT 
    'Total Active Users' as metric,
    COUNT(*) as value,
    NULL as percentage
FROM user
WHERE last_login >= DATE_SUB(NOW(), INTERVAL 30 DAY)

UNION ALL

SELECT 
    'Assignment Completion Rate',
    NULL,
    ROUND(COUNT(DISTINCT sub.submission_id) / 
          (SELECT COUNT(*) FROM assignment a 
           JOIN student s ON a.class = s.class) * 100, 2)
FROM submission sub

UNION ALL

SELECT 
    'Average System Performance (Marks)',
    ROUND(AVG(marks_obtained), 2),
    NULL
FROM submission
WHERE marks_obtained IS NOT NULL

UNION ALL

SELECT 
    'On-Time Submission Rate',
    NULL,
    ROUND(SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) / 
          COUNT(*) * 100, 2)
FROM submission

UNION ALL

SELECT 
    'Grading Completion Rate',
    NULL,
    ROUND(SUM(CASE WHEN status = 'graded' THEN 1 ELSE 0 END) / 
          COUNT(*) * 100, 2)
FROM submission;

-- Resource utilization analysis
SELECT 
    l.platform_name,
    COUNT(DISTINCT a.assignment_id) as assignments_using_platform,
    COUNT(DISTINCT n.notification_id) as notifications_sent,
    l.integration_status
FROM lms l
LEFT JOIN assignment a ON l.lms_id = a.lms_id
LEFT JOIN notification n ON n.mode_of_alert = 'LMS'
GROUP BY l.lms_id
ORDER BY assignments_using_platform DESC;

-- Peak usage times
SELECT 
    DATE(submission_timestamp) as date,
    HOUR(submission_timestamp) as hour,
    COUNT(*) as submission_count,
    RANK() OVER (ORDER BY COUNT(*) DESC) as usage_rank
FROM submission
WHERE submission_timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(submission_timestamp), HOUR(submission_timestamp)
ORDER BY submission_count DESC
LIMIT 20;

-- ============================================================================
-- 11. EXPORT QUERIES FOR REPORTS
-- ============================================================================

-- Comprehensive student report card
SELECT 
    s.student_id,
    s.name,
    s.class,
    s.roll_number,
    s.email,
    COUNT(DISTINCT sub.submission_id) as total_submissions,
    SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) as on_time_submissions,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) as late_submissions,
    AVG(sub.marks_obtained) as average_marks,
    MAX(sub.marks_obtained) as highest_marks,
    MIN(sub.marks_obtained) as lowest_marks,
    sba.average_delay as avg_delay_days,
    RANK() OVER (PARTITION BY s.class ORDER BY AVG(sub.marks_obtained) DESC) as class_rank
FROM student s
LEFT JOIN submission sub ON s.student_id = sub.student_id
LEFT JOIN student_behavior_analytics sba ON s.student_id = sba.student_id
WHERE sub.marks_obtained IS NOT NULL
GROUP BY s.student_id
ORDER BY s.class, class_rank;

-- Assignment analytics export
SELECT 
    a.assignment_id,
    a.title,
    a.subject,
    a.class,
    t.name as teacher_name,
    a.due_date,
    a.submission_deadline,
    a.max_marks,
    COUNT(sub.submission_id) as submissions_received,
    (SELECT COUNT(*) FROM student WHERE class = a.class) as total_students,
    ROUND(COUNT(sub.submission_id) / 
          (SELECT COUNT(*) FROM student WHERE class = a.class) * 100, 2) as completion_rate,
    AVG(sub.marks_obtained) as average_marks,
    SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) as on_time_count,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) as late_count,
    SUM(CASE WHEN sub.status = 'graded' THEN 1 ELSE 0 END) as graded_count
FROM assignment a
JOIN teacher t ON a.teacher_id = t.teacher_id
LEFT JOIN submission sub ON a.assignment_id = sub.assignment_id
GROUP BY a.assignment_id
ORDER BY a.due_date DESC;