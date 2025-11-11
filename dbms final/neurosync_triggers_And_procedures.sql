-- ============================================================================
-- NEUROSYNC: TRIGGERS, STORED PROCEDURES, AND FUNCTIONS
-- ============================================================================

USE neurosync_db;

-- Change delimiter for procedure/trigger creation
DELIMITER $$

-- ============================================================================
-- TRIGGER 1: Auto-check deadline on submission (CRITICAL)
-- ============================================================================
DROP TRIGGER IF EXISTS check_submission_deadline$$
CREATE TRIGGER check_submission_deadline
BEFORE INSERT ON submission
FOR EACH ROW
BEGIN
    DECLARE assignment_deadline DATETIME;
    
    -- Get the assignment deadline
    SELECT submission_deadline INTO assignment_deadline
    FROM assignment
    WHERE assignment_id = NEW.assignment_id;
    
    -- Compare submission time with deadline
    IF NEW.submission_timestamp > assignment_deadline THEN
        SET NEW.status = 'late';
    ELSE
        SET NEW.status = 'submitted';
    END IF;
END$$

-- ============================================================================
-- TRIGGER 2: Update behavior analytics after submission
-- ============================================================================
DROP TRIGGER IF EXISTS update_behavior_after_submission$$
CREATE TRIGGER update_behavior_after_submission
AFTER INSERT ON submission
FOR EACH ROW
BEGIN
    DECLARE delay_days DECIMAL(5,2);
    DECLARE assignment_deadline DATETIME;
    
    -- Get assignment deadline
    SELECT submission_deadline INTO assignment_deadline
    FROM assignment
    WHERE assignment_id = NEW.assignment_id;
    
    -- Calculate delay
    SET delay_days = GREATEST(0, TIMESTAMPDIFF(SECOND, assignment_deadline, NEW.submission_timestamp) / 86400);
    
    -- Update or insert into behavior analytics
    INSERT INTO student_behavior_analytics (
        student_id,
        total_submissions,
        late_submissions,
        on_time_submissions,
        average_delay
    ) VALUES (
        NEW.student_id,
        1,
        IF(NEW.status = 'late', 1, 0),
        IF(NEW.status = 'submitted', 1, 0),
        delay_days
    )
    ON DUPLICATE KEY UPDATE
        total_submissions = total_submissions + 1,
        late_submissions = late_submissions + IF(NEW.status = 'late', 1, 0),
        on_time_submissions = on_time_submissions + IF(NEW.status = 'submitted', 1, 0),
        average_delay = (average_delay * (total_submissions - 1) + delay_days) / total_submissions,
        last_updated = CURRENT_TIMESTAMP;
END$$

-- ============================================================================
-- TRIGGER 3: Log all user actions
-- ============================================================================
DROP TRIGGER IF EXISTS log_assignment_creation$$
CREATE TRIGGER log_assignment_creation
AFTER INSERT ON assignment
FOR EACH ROW
BEGIN
    INSERT INTO action_log (user_id, action, description)
    SELECT user_id, 'CREATE_ASSIGNMENT', 
           CONCAT('Created assignment: ', NEW.title, ' for class ', NEW.class)
    FROM teacher
    WHERE teacher_id = NEW.teacher_id;
END$$

-- ============================================================================
-- TRIGGER 4: Prevent deletion of assignments with submissions
-- ============================================================================
DROP TRIGGER IF EXISTS prevent_assignment_deletion$$
CREATE TRIGGER prevent_assignment_deletion
BEFORE DELETE ON assignment
FOR EACH ROW
BEGIN
    DECLARE submission_count INT;
    
    SELECT COUNT(*) INTO submission_count
    FROM submission
    WHERE assignment_id = OLD.assignment_id;
    
    IF submission_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot delete assignment with existing submissions';
    END IF;
END$$

-- ============================================================================
-- TRIGGER 5: Auto-update submission count on grading
-- ============================================================================
DROP TRIGGER IF EXISTS update_on_grading$$
CREATE TRIGGER update_on_grading
AFTER UPDATE ON submission
FOR EACH ROW
BEGIN
    IF NEW.status = 'graded' AND OLD.status != 'graded' THEN
        INSERT INTO action_log (user_id, action, description)
        VALUES (NEW.graded_by, 'GRADE_SUBMISSION',
                CONCAT('Graded submission ID: ', NEW.submission_id, ' with marks: ', NEW.marks_obtained));
    END IF;
END$$

-- ============================================================================
-- STORED PROCEDURE 1: Generate reminders for all students in a class
-- ============================================================================
DROP PROCEDURE IF EXISTS generate_reminders$$
CREATE PROCEDURE generate_reminders(
    IN p_assignment_id INT,
    IN p_class_name VARCHAR(50),
    IN p_notification_channels VARCHAR(200)
)
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE v_student_id INT;
    DECLARE v_channel VARCHAR(50);
    DECLARE student_cursor CURSOR FOR 
        SELECT student_id FROM student WHERE class = p_class_name;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;
    
    -- Open cursor
    OPEN student_cursor;
    
    student_loop: LOOP
        FETCH student_cursor INTO v_student_id;
        IF done THEN
            LEAVE student_loop;
        END IF;
        
        -- Insert notifications for each channel
        IF FIND_IN_SET('LMS', p_notification_channels) > 0 THEN
            INSERT INTO notification (assignment_id, student_id, mode_of_alert, timestamp, delivery_status, target_audience)
            VALUES (p_assignment_id, v_student_id, 'LMS', NOW(), 'Sent', 'Individual');
        END IF;
        
        IF FIND_IN_SET('WhatsApp', p_notification_channels) > 0 THEN
            INSERT INTO notification (assignment_id, student_id, mode_of_alert, timestamp, delivery_status, target_audience)
            VALUES (p_assignment_id, v_student_id, 'WhatsApp', NOW(), 'Sent', 'Individual');
        END IF;
        
        IF FIND_IN_SET('Telegram', p_notification_channels) > 0 THEN
            INSERT INTO notification (assignment_id, student_id, mode_of_alert, timestamp, delivery_status, target_audience)
            VALUES (p_assignment_id, v_student_id, 'Telegram', NOW(), 'Sent', 'Individual');
        END IF;
    END LOOP;
    
    CLOSE student_cursor;
    
    -- Log the action
    INSERT INTO action_log (action, description)
    VALUES ('SEND_REMINDERS', CONCAT('Sent reminders for assignment ', p_assignment_id, ' to class ', p_class_name));
END$$

-- ============================================================================
-- STORED PROCEDURE 2: Grade submission
-- ============================================================================
DROP PROCEDURE IF EXISTS grade_submission$$
CREATE PROCEDURE grade_submission(
    IN p_submission_id INT,
    IN p_marks_obtained INT,
    IN p_remarks TEXT,
    IN p_graded_by INT
)
BEGIN
    DECLARE v_max_marks INT;
    DECLARE v_assignment_id INT;
    
    -- Get assignment details
    SELECT a.max_marks, s.assignment_id INTO v_max_marks, v_assignment_id
    FROM submission s
    JOIN assignment a ON s.assignment_id = a.assignment_id
    WHERE s.submission_id = p_submission_id;
    
    -- Validate marks
    IF p_marks_obtained > v_max_marks THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marks obtained cannot exceed maximum marks';
    END IF;
    
    -- Update submission
    UPDATE submission
    SET marks_obtained = p_marks_obtained,
        grading_remarks = p_remarks,
        status = 'graded',
        graded_by = p_graded_by,
        graded_at = NOW()
    WHERE submission_id = p_submission_id;
    
    -- Record in expert observation
    INSERT INTO expert_observation (teacher_id, action_type, observation_data, context_data)
    VALUES (p_graded_by, 'grade', 
            JSON_OBJECT('submission_id', p_submission_id, 'marks', p_marks_obtained),
            JSON_OBJECT('timestamp', NOW(), 'day_of_week', DAYNAME(NOW())));
END$$

-- ============================================================================
-- STORED PROCEDURE 3: Get student performance report
-- ============================================================================
DROP PROCEDURE IF EXISTS get_student_performance$$
CREATE PROCEDURE get_student_performance(IN p_student_id INT)
BEGIN
    SELECT 
        s.name AS student_name,
        s.class,
        s.roll_number,
        COUNT(sub.submission_id) AS total_submissions,
        SUM(CASE WHEN sub.status = 'submitted' THEN 1 ELSE 0 END) AS on_time_submissions,
        SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) AS late_submissions,
        AVG(sub.marks_obtained) AS average_marks,
        sba.average_delay
    FROM student s
    LEFT JOIN submission sub ON s.student_id = sub.student_id
    LEFT JOIN student_behavior_analytics sba ON s.student_id = sba.student_id
    WHERE s.student_id = p_student_id
    GROUP BY s.student_id;
END$$

-- ============================================================================
-- STORED PROCEDURE 4: Get assignment statistics
-- ============================================================================
DROP PROCEDURE IF EXISTS get_assignment_statistics$$
CREATE PROCEDURE get_assignment_statistics(IN p_assignment_id INT)
BEGIN
    DECLARE v_total_students INT;
    DECLARE v_class VARCHAR(50);
    
    -- Get class and count total students
    SELECT class INTO v_class FROM assignment WHERE assignment_id = p_assignment_id;
    SELECT COUNT(*) INTO v_total_students FROM student WHERE class = v_class;
    
    -- Return statistics
    SELECT 
        a.title AS assignment_title,
        a.subject,
        a.class,
        a.due_date,
        a.max_marks,
        v_total_students AS total_students,
        COUNT(s.submission_id) AS submitted_count,
        SUM(CASE WHEN s.status = 'submitted' THEN 1 ELSE 0 END) AS on_time_count,
        SUM(CASE WHEN s.status = 'late' THEN 1 ELSE 0 END) AS late_count,
        SUM(CASE WHEN s.status = 'graded' THEN 1 ELSE 0 END) AS graded_count,
        AVG(s.marks_obtained) AS average_marks,
        ROUND((COUNT(s.submission_id) / v_total_students) * 100, 2) AS submission_percentage
    FROM assignment a
    LEFT JOIN submission s ON a.assignment_id = s.assignment_id
    WHERE a.assignment_id = p_assignment_id
    GROUP BY a.assignment_id;
END$$

-- ============================================================================
-- STORED PROCEDURE 5: Bulk notification sender
-- ============================================================================
DROP PROCEDURE IF EXISTS send_bulk_notifications$$
CREATE PROCEDURE send_bulk_notifications(
    IN p_assignment_id INT,
    IN p_target_audience VARCHAR(20),
    IN p_mode VARCHAR(20),
    IN p_message TEXT
)
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE v_student_id INT;
    DECLARE v_class VARCHAR(50);
    DECLARE student_cursor CURSOR FOR 
        SELECT student_id FROM student WHERE class = v_class;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;
    
    -- Get class from assignment
    SELECT class INTO v_class FROM assignment WHERE assignment_id = p_assignment_id;
    
    IF p_target_audience = 'Class' THEN
        OPEN student_cursor;
        
        notification_loop: LOOP
            FETCH student_cursor INTO v_student_id;
            IF done THEN
                LEAVE notification_loop;
            END IF;
            
            INSERT INTO notification (assignment_id, student_id, mode_of_alert, timestamp, 
                                    delivery_status, target_audience, message_content)
            VALUES (p_assignment_id, v_student_id, p_mode, NOW(), 'Sent', 'Class', p_message);
        END LOOP;
        
        CLOSE student_cursor;
    END IF;
END$$

-- ============================================================================
-- FUNCTION 1: Calculate submission rate for a class
-- ============================================================================
DROP FUNCTION IF EXISTS calculate_submission_rate$$
CREATE FUNCTION calculate_submission_rate(
    p_assignment_id INT
) RETURNS DECIMAL(5,2)
DETERMINISTIC
BEGIN
    DECLARE v_total_students INT;
    DECLARE v_submitted_count INT;
    DECLARE v_class VARCHAR(50);
    DECLARE v_rate DECIMAL(5,2);
    
    -- Get class
    SELECT class INTO v_class FROM assignment WHERE assignment_id = p_assignment_id;
    
    -- Count total students
    SELECT COUNT(*) INTO v_total_students FROM student WHERE class = v_class;
    
    -- Count submissions
    SELECT COUNT(*) INTO v_submitted_count 
    FROM submission 
    WHERE assignment_id = p_assignment_id;
    
    -- Calculate rate
    IF v_total_students > 0 THEN
        SET v_rate = (v_submitted_count / v_total_students) * 100;
    ELSE
        SET v_rate = 0;
    END IF;
    
    RETURN v_rate;
END$$

-- ============================================================================
-- FUNCTION 2: Get student grade classification
-- ============================================================================
DROP FUNCTION IF EXISTS get_grade_classification$$
CREATE FUNCTION get_grade_classification(
    p_marks INT,
    p_max_marks INT
) RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
    DECLARE v_percentage DECIMAL(5,2);
    DECLARE v_grade VARCHAR(20);
    
    SET v_percentage = (p_marks / p_max_marks) * 100;
    
    IF v_percentage >= 90 THEN
        SET v_grade = 'A+';
    ELSEIF v_percentage >= 80 THEN
        SET v_grade = 'A';
    ELSEIF v_percentage >= 70 THEN
        SET v_grade = 'B+';
    ELSEIF v_percentage >= 60 THEN
        SET v_grade = 'B';
    ELSEIF v_percentage >= 50 THEN
        SET v_grade = 'C';
    ELSE
        SET v_grade = 'F';
    END IF;
    
    RETURN v_grade;
END$$

-- ============================================================================
-- FUNCTION 3: Check if student is at risk
-- ============================================================================
DROP FUNCTION IF EXISTS is_student_at_risk$$
CREATE FUNCTION is_student_at_risk(
    p_student_id INT
) RETURNS BOOLEAN
DETERMINISTIC
BEGIN
    DECLARE v_late_count INT;
    DECLARE v_total_count INT;
    DECLARE v_late_percentage DECIMAL(5,2);
    
    -- Get submission counts
    SELECT 
        COUNT(*) INTO v_total_count
    FROM submission
    WHERE student_id = p_student_id;
    
    SELECT 
        COUNT(*) INTO v_late_count
    FROM submission
    WHERE student_id = p_student_id AND status = 'late';
    
    -- Calculate late percentage
    IF v_total_count > 0 THEN
        SET v_late_percentage = (v_late_count / v_total_count) * 100;
    ELSE
        SET v_late_percentage = 0;
    END IF;
    
    -- Student is at risk if more than 40% late or average marks < 50
    IF v_late_percentage > 40 OR v_total_count = 0 THEN
        RETURN TRUE;
    ELSE
        RETURN FALSE;
    END IF;
END$$

-- ============================================================================
-- FUNCTION 4: Calculate average delay for a student
-- ============================================================================
DROP FUNCTION IF EXISTS get_student_avg_delay$
CREATE FUNCTION get_student_avg_delay(
    p_student_id INT
) RETURNS DECIMAL(5,2)
DETERMINISTIC
BEGIN
    DECLARE v_avg_delay DECIMAL(5,2);
    
    SELECT 
        AVG(GREATEST(0, TIMESTAMPDIFF(SECOND, a.submission_deadline, s.submission_timestamp) / 86400))
        INTO v_avg_delay
    FROM submission s
    JOIN assignment a ON s.assignment_id = a.assignment_id
    WHERE s.student_id = p_student_id AND s.status = 'late';
    
    RETURN IFNULL(v_avg_delay, 0.00);
END$

-- ============================================================================
-- FUNCTION 5: Get days until deadline
-- ============================================================================
DROP FUNCTION IF EXISTS days_until_deadline$
CREATE FUNCTION days_until_deadline(
    p_assignment_id INT
) RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE v_deadline DATETIME;
    DECLARE v_days INT;
    
    SELECT submission_deadline INTO v_deadline
    FROM assignment
    WHERE assignment_id = p_assignment_id;
    
    SET v_days = TIMESTAMPDIFF(DAY, NOW(), v_deadline);
    
    RETURN v_days;
END$

DELIMITER ;

-- ============================================================================
-- COMPLEX QUERIES FOR ANALYSIS
-- ============================================================================

-- Query 1: Get top performing students
CREATE OR REPLACE VIEW top_performing_students AS
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

-- Query 2: Assignment completion statistics
CREATE OR REPLACE VIEW assignment_completion_stats AS
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

-- Query 3: Students at risk (late submissions pattern)
CREATE OR REPLACE VIEW students_at_risk AS
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

-- Query 4: Notification effectiveness analysis
CREATE OR REPLACE VIEW notification_effectiveness AS
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

-- Query 5: Teacher workload analysis
CREATE OR REPLACE VIEW teacher_workload AS
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