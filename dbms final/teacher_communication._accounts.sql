-- ============================================================================
-- TEACHER COMMUNICATION ACCOUNTS TABLE
-- Stores teacher platform account details for all communication channels
-- Teachers don't choose channels - they send to all platforms
-- Students receive based on their preferences
-- ============================================================================

CREATE TABLE IF NOT EXISTS teacher_communication_accounts (
    account_id INT PRIMARY KEY AUTO_INCREMENT,
    teacher_id INT NOT NULL,
    platform ENUM('LMS', 'Email', 'Telegram', 'Discord') NOT NULL,
    account_identifier VARCHAR(255) COMMENT 'Email, Telegram ID, Discord ID, or LMS username',
    account_username VARCHAR(100) COMMENT '@username for Telegram/Discord',
    account_status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id) ON DELETE CASCADE,
    UNIQUE KEY unique_platform_per_teacher (teacher_id, platform),
    INDEX idx_teacher_platform (teacher_id, platform)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 
COMMENT='Stores teacher communication platform account details';

-- ============================================================================
-- SAMPLE DATA FOR TESTING
-- ============================================================================

-- Teacher 1: Adishree
INSERT INTO teacher_communication_accounts 
(teacher_id, platform, account_identifier, account_username, account_status)
VALUES 
    (1, 'LMS', 'Guptashree', NULL, 'active'),
    (1, 'Email', 'maltoadishreegupta@gmail.com', NULL, 'active'),
    (1, 'Telegram', '9831057844', '@adishree_teacher', 'active'),
    (1, 'Discord', '123456789012345678', 'adishree_teacher#4977', 'active');
	
-- Teacher 2: Bhavani
INSERT INTO teacher_communication_accounts 
(teacher_id, platform, account_identifier, account_username, account_status)
VALUES 
    (1, 'LMS', 'bhavani', NULL, 'active'),
    (1, 'Email', 'bhavani.teacher@college.edu', NULL, 'active'),
    (1, 'Telegram', '987654321', '@bhavani_teacher', 'active'),
    (1, 'Discord', '123456789012345678', 'bhavani_teacher#1234', 'active');

-- Teacher 3: Monica
INSERT INTO teacher_communication_accounts 
(teacher_id, platform, account_identifier, account_username, account_status)
VALUES 
    (2, 'LMS', 'monica', NULL, 'active'),
    (2, 'Email', 'monica.teacher@college.edu', NULL, 'active'),
    (2, 'Telegram', '987654322', '@monica_teacher', 'active'),
    (2, 'Discord', '123456789012345679', 'monica_teacher#5678', 'active');

-- ============================================================================
-- UPDATE NOTIFICATION TABLE TO INCLUDE SENDER INFO
-- ============================================================================

-- Add columns to track who sent the notification
ALTER TABLE notification
ADD COLUMN IF NOT EXISTS sender_platform ENUM('LMS', 'Email', 'Telegram', 'Discord') DEFAULT 'LMS'
    COMMENT 'Platform used by teacher to send notification';

ALTER TABLE notification
ADD COLUMN IF NOT EXISTS sender_identifier VARCHAR(255)
    COMMENT 'Teacher account identifier used for sending';

-- ============================================================================
-- VIEW: TEACHER BROADCAST CAPABILITY
-- Shows which teachers can broadcast on which platforms
-- ============================================================================

CREATE OR REPLACE VIEW teacher_broadcast_capability AS
SELECT 
    t.teacher_id,
    t.name AS teacher_name,
    t.subject_taught,
    GROUP_CONCAT(DISTINCT tca.platform ORDER BY tca.platform) AS available_platforms,
    COUNT(DISTINCT tca.platform) AS platform_count,
    CASE 
        WHEN COUNT(DISTINCT tca.platform) >= 4 THEN 'Full Multi-Channel'
        WHEN COUNT(DISTINCT tca.platform) >= 2 THEN 'Partial Multi-Channel'
        ELSE 'Limited'
    END AS broadcast_capability
FROM teacher t
LEFT JOIN teacher_communication_accounts tca 
    ON t.teacher_id = tca.teacher_id 
    AND tca.account_status = 'active'
GROUP BY t.teacher_id, t.name, t.subject_taught;

-- ============================================================================
-- VIEW: COMMUNICATION COVERAGE REPORT
-- Shows how many students can be reached on each platform
-- ============================================================================

CREATE OR REPLACE VIEW communication_coverage_report AS
SELECT 
    s.class,
    COUNT(DISTINCT s.student_id) AS total_students,
    SUM(CASE WHEN sca.platform = 'LMS' AND sca.is_preferred = TRUE THEN 1 ELSE 0 END) AS lms_users,
    SUM(CASE WHEN sca.platform = 'Email' AND sca.is_preferred = TRUE THEN 1 ELSE 0 END) AS email_users,
    SUM(CASE WHEN sca.platform = 'Telegram' AND sca.is_preferred = TRUE THEN 1 ELSE 0 END) AS telegram_users,
    SUM(CASE WHEN sca.platform = 'Discord' AND sca.is_preferred = TRUE THEN 1 ELSE 0 END) AS discord_users,
    ROUND(AVG(
        (CASE WHEN sca.platform = 'LMS' AND sca.is_preferred = TRUE THEN 1 ELSE 0 END) +
        (CASE WHEN sca.platform = 'Email' AND sca.is_preferred = TRUE THEN 1 ELSE 0 END) +
        (CASE WHEN sca.platform = 'Telegram' AND sca.is_preferred = TRUE THEN 1 ELSE 0 END) +
        (CASE WHEN sca.platform = 'Discord' AND sca.is_preferred = TRUE THEN 1 ELSE 0 END)
    ), 2) AS avg_channels_per_student
FROM student s
LEFT JOIN student_communication_accounts sca ON s.student_id = sca.student_id
GROUP BY s.class
ORDER BY s.class;

-- ============================================================================
-- STORED PROCEDURE: GET TEACHER SENDING CAPABILITIES
-- Returns all active platforms a teacher can use for broadcasting
-- ============================================================================

DELIMITER //

CREATE PROCEDURE IF NOT EXISTS get_teacher_broadcast_channels(
    IN p_teacher_id INT
)
BEGIN
    SELECT 
        platform,
        account_identifier,
        account_username,
        account_status
    FROM teacher_communication_accounts
    WHERE teacher_id = p_teacher_id
        AND account_status = 'active'
    ORDER BY platform;
END //

DELIMITER ;

-- ============================================================================
-- STORED PROCEDURE: LOG BROADCAST ACTIVITY
-- Logs when a teacher sends a broadcast message
-- ============================================================================

DELIMITER //

CREATE PROCEDURE IF NOT EXISTS log_broadcast_activity(
    IN p_teacher_id INT,
    IN p_assignment_id INT,
    IN p_class VARCHAR(50),
    IN p_message TEXT,
    IN p_total_recipients INT,
    IN p_successful_deliveries INT,
    IN p_failed_deliveries INT
)
BEGIN
    -- Create a log entry (you may want to create a broadcast_log table)
    INSERT INTO action_log (user_id, action_type, action_description, timestamp)
    SELECT 
        u.user_id,
        'BROADCAST_SENT',
        CONCAT('Teacher sent broadcast for assignment ', p_assignment_id, 
               ' to class ', p_class, 
               '. Recipients: ', p_total_recipients,
               ', Success: ', p_successful_deliveries,
               ', Failed: ', p_failed_deliveries),
        NOW()
    FROM teacher t
    JOIN user u ON t.user_id = u.user_id
    WHERE t.teacher_id = p_teacher_id;
    
    SELECT 'Broadcast activity logged' AS result;
END //

DELIMITER ;

-- ============================================================================
-- STORED PROCEDURE: GET NOTIFICATION DELIVERY STATISTICS
-- Returns delivery statistics for a specific assignment or teacher
-- ============================================================================

DELIMITER //

CREATE PROCEDURE IF NOT EXISTS get_notification_delivery_stats(
    IN p_assignment_id INT
)
BEGIN
    SELECT 
        notification_channel AS platform,
        COUNT(*) AS total_sent,
        SUM(CASE WHEN notification_status = 'sent' THEN 1 ELSE 0 END) AS sent,
        SUM(CASE WHEN notification_status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
        SUM(CASE WHEN notification_status = 'read' THEN 1 ELSE 0 END) AS read_count,
        SUM(CASE WHEN notification_status = 'failed' THEN 1 ELSE 0 END) AS failed,
        ROUND(AVG(CASE 
            WHEN notification_status IN ('delivered', 'read') THEN 100 
            ELSE 0 
        END), 2) AS delivery_rate_percent
    FROM notification
    WHERE assignment_id = p_assignment_id
    GROUP BY notification_channel
    ORDER BY notification_channel;
END //

DELIMITER ;

-- ============================================================================
-- TRIGGER: VALIDATE TEACHER ACCOUNT ON INSERT
-- Ensures teacher account details are properly formatted
-- ============================================================================

DELIMITER //

CREATE TRIGGER IF NOT EXISTS validate_teacher_account_insert
BEFORE INSERT ON teacher_communication_accounts
FOR EACH ROW
BEGIN
    -- Validate Telegram ID (should be numeric and 8-10 digits)
    IF NEW.platform = 'Telegram' THEN
        IF NEW.account_identifier IS NOT NULL 
           AND (NEW.account_identifier NOT REGEXP '^[0-9]{8,10}$') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid Telegram ID format. Must be 8-10 digits.';
        END IF;
        
        -- Ensure @ prefix for username
        IF NEW.account_username IS NOT NULL 
           AND LEFT(NEW.account_username, 1) != '@' THEN
            SET NEW.account_username = CONCAT('@', NEW.account_username);
        END IF;
    END IF;
    
    -- Validate Discord ID (should be numeric and 17-19 digits)
    IF NEW.platform = 'Discord' THEN
        IF NEW.account_identifier IS NOT NULL 
           AND (NEW.account_identifier NOT REGEXP '^[0-9]{17,19}$') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid Discord ID format. Must be 17-19 digits.';
        END IF;
    END IF;
    
    -- Validate Email format
    IF NEW.platform = 'Email' THEN
        IF NEW.account_identifier IS NOT NULL 
           AND (NEW.account_identifier NOT LIKE '%@%') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid email format.';
        END IF;
    END IF;
END //

DELIMITER ;

-- ============================================================================
-- SAMPLE QUERIES FOR TESTING
-- ============================================================================

-- 1. Check teacher broadcast capabilities
SELECT * FROM teacher_broadcast_capability;

-- 2. Get communication coverage by class
SELECT * FROM communication_coverage_report;

-- 3. Get teacher's active channels
CALL get_teacher_broadcast_channels(1);

-- 4. Get delivery statistics for an assignment
CALL get_notification_delivery_stats(1);

-- 5. Check which students will receive notifications in a class
SELECT 
    s.student_id,
    s.name,
    s.class,
    GROUP_CONCAT(DISTINCT sca.platform ORDER BY sca.platform) AS will_receive_on
FROM student s
LEFT JOIN student_communication_accounts sca 
    ON s.student_id = sca.student_id
WHERE s.class = 'CSE-3A'
    AND sca.is_preferred = TRUE
    AND sca.account_status = 'active'
GROUP BY s.student_id, s.name, s.class;

-- 6. View all notifications sent for a specific assignment with delivery status
SELECT 
    n.notification_id,
    s.name AS student_name,
    s.class,
    n.notification_channel AS platform,
    n.notification_status,
    n.sent_timestamp,
    n.read_timestamp,
    CASE 
        WHEN n.notification_status IN ('delivered', 'read') THEN '✅ Success'
        WHEN n.notification_status = 'failed' THEN '❌ Failed'
        ELSE '📤 Pending'
    END AS delivery_status
FROM notification n
JOIN student s ON n.student_id = s.student_id
WHERE n.assignment_id = 1
ORDER BY s.name, n.notification_channel;

-- 7. Teacher sending history (how many messages sent via each platform)
SELECT 
    t.teacher_id,
    t.name AS teacher_name,
    n.notification_channel AS platform,
    COUNT(*) AS messages_sent,
    SUM(CASE WHEN n.notification_status IN ('delivered', 'read') THEN 1 ELSE 0 END) AS successful,
    SUM(CASE WHEN n.notification_status = 'failed' THEN 1 ELSE 0 END) AS failed,
    ROUND(AVG(CASE WHEN n.notification_status IN ('delivered', 'read') THEN 100 ELSE 0 END), 2) AS success_rate
FROM teacher t
LEFT JOIN notification n ON t.teacher_id = n.teacher_id
GROUP BY t.teacher_id, t.name, n.notification_channel
ORDER BY t.name, n.notification_channel;

-- ============================================================================
-- BROADCAST LOG TABLE (Optional - for detailed tracking)
-- ============================================================================

CREATE TABLE IF NOT EXISTS broadcast_log (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    teacher_id INT NOT NULL,
    assignment_id INT,
    broadcast_type ENUM('assignment_created', 'assignment_graded', 'reminder', 'custom') NOT NULL,
    target_class VARCHAR(50),
    message_preview TEXT,
    total_recipients INT DEFAULT 0,
    lms_sent INT DEFAULT 0,
    email_sent INT DEFAULT 0,
    telegram_sent INT DEFAULT 0,
    discord_sent INT DEFAULT 0,
    total_successful INT DEFAULT 0,
    total_failed INT DEFAULT 0,
    broadcast_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id) ON DELETE CASCADE,
    FOREIGN KEY (assignment_id) REFERENCES assignment(assignment_id) ON DELETE SET NULL,
    INDEX idx_teacher_broadcast (teacher_id, broadcast_timestamp),
    INDEX idx_assignment_broadcast (assignment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
COMMENT='Detailed log of all broadcast activities';

-- ============================================================================
-- TRIGGER: AUTO-LOG BROADCAST WHEN NOTIFICATIONS ARE CREATED
-- ============================================================================

DELIMITER //

CREATE TRIGGER IF NOT EXISTS auto_log_broadcast
AFTER INSERT ON notification
FOR EACH ROW
BEGIN
    DECLARE v_broadcast_exists INT;
    
    -- Check if a broadcast log entry exists for this assignment in the last minute
    SELECT COUNT(*) INTO v_broadcast_exists
    FROM broadcast_log
    WHERE assignment_id = NEW.assignment_id
        AND broadcast_timestamp > DATE_SUB(NOW(), INTERVAL 1 MINUTE);
    
    -- If no recent log exists, create one
    IF v_broadcast_exists = 0 AND NEW.assignment_id IS NOT NULL THEN
        INSERT INTO broadcast_log (
            teacher_id, 
            assignment_id, 
            broadcast_type,
            target_class,
            message_preview,
            total_recipients
        )
        SELECT 
            a.teacher_id,
            a.assignment_id,
            'assignment_created',
            a.class,
            SUBSTRING(NEW.message, 1, 100),
            COUNT(DISTINCT s.student_id)
        FROM assignment a
        JOIN student s ON s.class = a.class
        WHERE a.assignment_id = NEW.assignment_id;
    END IF;
    
    -- Update the broadcast log with channel-specific counts
    UPDATE broadcast_log bl
    SET 
        lms_sent = lms_sent + CASE WHEN NEW.notification_channel = 'LMS' THEN 1 ELSE 0 END,
        email_sent = email_sent + CASE WHEN NEW.notification_channel = 'Email' THEN 1 ELSE 0 END,
        telegram_sent = telegram_sent + CASE WHEN NEW.notification_channel = 'Telegram' THEN 1 ELSE 0 END,
        discord_sent = discord_sent + CASE WHEN NEW.notification_channel = 'Discord' THEN 1 ELSE 0 END,
        total_successful = total_successful + CASE WHEN NEW.notification_status IN ('sent', 'delivered') THEN 1 ELSE 0 END,
        total_failed = total_failed + CASE WHEN NEW.notification_status = 'failed' THEN 1 ELSE 0 END
    WHERE bl.assignment_id = NEW.assignment_id
        AND bl.broadcast_timestamp > DATE_SUB(NOW(), INTERVAL 1 MINUTE);
END //

DELIMITER ;

-- ============================================================================
-- VIEW: REAL-TIME BROADCAST DASHBOARD
-- Shows current broadcast activities and their status
-- ============================================================================

CREATE OR REPLACE VIEW broadcast_dashboard AS
SELECT 
    bl.log_id,
    bl.broadcast_type,
    t.name AS teacher_name,
    a.title AS assignment_title,
    bl.target_class,
    bl.total_recipients,
    bl.lms_sent,
    bl.email_sent,
    bl.telegram_sent,
    bl.discord_sent,
    bl.total_successful,
    bl.total_failed,
    ROUND((bl.total_successful / NULLIF(bl.total_recipients, 0)) * 100, 2) AS success_rate,
    bl.broadcast_timestamp,
    TIMESTAMPDIFF(SECOND, bl.broadcast_timestamp, NOW()) AS seconds_ago
FROM broadcast_log bl
JOIN teacher t ON bl.teacher_id = t.teacher_id
LEFT JOIN assignment a ON bl.assignment_id = a.assignment_id
ORDER BY bl.broadcast_timestamp DESC
LIMIT 50;

-- ============================================================================
-- STORED PROCEDURE: UPDATE NOTIFICATION STATUS
-- Used by broadcast module to update delivery status
-- ============================================================================

DELIMITER //

CREATE PROCEDURE IF NOT EXISTS update_notification_status(
    IN p_notification_id INT,
    IN p_new_status ENUM('sent', 'delivered', 'read', 'failed')
)
BEGIN
    UPDATE notification
    SET 
        notification_status = p_new_status,
        read_timestamp = CASE WHEN p_new_status = 'read' THEN NOW() ELSE read_timestamp END
    WHERE notification_id = p_notification_id;
    
    SELECT 'Notification status updated' AS result;
END //

DELIMITER ;

-- ============================================================================
-- STORED PROCEDURE: GET PENDING NOTIFICATIONS FOR STUDENT
-- Returns unread notifications for a specific student
-- ============================================================================

DELIMITER //

CREATE PROCEDURE IF NOT EXISTS get_pending_notifications_for_student(
    IN p_student_id INT
)
BEGIN
    SELECT 
        n.notification_id,
        n.message,
        n.notification_channel,
        n.notification_status,
        n.sent_timestamp,
        a.title AS assignment_title,
        t.name AS teacher_name,
        TIMESTAMPDIFF(HOUR, n.sent_timestamp, NOW()) AS hours_ago
    FROM notification n
    LEFT JOIN assignment a ON n.assignment_id = a.assignment_id
    LEFT JOIN teacher t ON n.teacher_id = t.teacher_id
    WHERE n.student_id = p_student_id
        AND n.notification_status != 'read'
    ORDER BY n.sent_timestamp DESC;
END //

DELIMITER ;

-- ============================================================================
-- FUNCTION: CALCULATE TEACHER BROADCAST EFFICIENCY
-- Returns percentage of successful message deliveries for a teacher
-- ============================================================================

DELIMITER //

CREATE FUNCTION IF NOT EXISTS calculate_teacher_broadcast_efficiency(
    p_teacher_id INT
) RETURNS DECIMAL(5,2)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_efficiency DECIMAL(5,2);
    
    SELECT 
        ROUND(
            (SUM(CASE WHEN notification_status IN ('delivered', 'read') THEN 1 ELSE 0 END) / 
            NULLIF(COUNT(*), 0)) * 100, 
            2
        ) INTO v_efficiency
    FROM notification
    WHERE teacher_id = p_teacher_id;
    
    RETURN IFNULL(v_efficiency, 0.00);
END //

DELIMITER ;

-- ============================================================================
-- SAMPLE DATA: ADD TEACHER ACCOUNTS FOR EXISTING TEACHERS
-- Run this after teachers are created
-- ============================================================================

-- Check if teachers exist, then add their communication accounts
INSERT IGNORE INTO teacher_communication_accounts 
(teacher_id, platform, account_identifier, account_username, account_status)
SELECT 
    t.teacher_id,
    'LMS',
    u.username,
    NULL,
    'active'
FROM teacher t
JOIN user u ON t.user_id = u.user_id;

-- Add email accounts for all teachers (using their existing email)
INSERT IGNORE INTO teacher_communication_accounts 
(teacher_id, platform, account_identifier, account_username, account_status)
SELECT 
    t.teacher_id,
    'Email',
    t.email,
    NULL,
    'active'
FROM teacher t
WHERE t.email IS NOT NULL AND t.email != '';

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- 1. Verify teacher accounts are created
SELECT 
    t.teacher_id,
    t.name,
    tca.platform,
    tca.account_identifier,
    tca.account_status
FROM teacher t
LEFT JOIN teacher_communication_accounts tca ON t.teacher_id = tca.teacher_id
ORDER BY t.name, tca.platform;

-- 2. Check broadcast coverage for each class
SELECT 
    class,
    total_students,
    lms_users,
    email_users,
    telegram_users,
    discord_users,
    CONCAT(
        ROUND((lms_users / total_students) * 100, 1), '% LMS, ',
        ROUND((email_users / total_students) * 100, 1), '% Email, ',
        ROUND((telegram_users / total_students) * 100, 1), '% Telegram, ',
        ROUND((discord_users / total_students) * 100, 1), '% Discord'
    ) AS coverage_summary
FROM communication_coverage_report;

-- 3. Teacher broadcast efficiency scores
SELECT 
    t.teacher_id,
    t.name,
    calculate_teacher_broadcast_efficiency(t.teacher_id) AS efficiency_percent,
    COUNT(DISTINCT n.notification_id) AS total_notifications_sent
FROM teacher t
LEFT JOIN notification n ON t.teacher_id = n.teacher_id
GROUP BY t.teacher_id, t.name
ORDER BY efficiency_percent DESC;

-- 4. Recent broadcast activity
SELECT * FROM broadcast_dashboard;

-- 5. Platform-wise notification distribution
SELECT 
    notification_channel AS platform,
    COUNT(*) AS total_notifications,
    SUM(CASE WHEN notification_status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
    SUM(CASE WHEN notification_status = 'read' THEN 1 ELSE 0 END) AS read_by_students,
    SUM(CASE WHEN notification_status = 'failed' THEN 1 ELSE 0 END) AS failed,
    ROUND(AVG(CASE WHEN notification_status IN ('delivered', 'read') THEN 100 ELSE 0 END), 2) AS delivery_rate
FROM notification
GROUP BY notification_channel
ORDER BY total_notifications DESC;

-- ============================================================================
-- MAINTENANCE QUERIES
-- ============================================================================

-- Clean up old notifications (older than 6 months)
-- Uncomment to run:
-- DELETE FROM notification WHERE sent_timestamp < DATE_SUB(NOW(), INTERVAL 6 MONTH);

-- Archive old broadcast logs (older than 1 year)
-- CREATE TABLE IF NOT EXISTS broadcast_log_archive LIKE broadcast_log;
-- INSERT INTO broadcast_log_archive SELECT * FROM broadcast_log WHERE broadcast_timestamp < DATE_SUB(NOW(), INTERVAL 1 YEAR);
-- DELETE FROM broadcast_log WHERE broadcast_timestamp < DATE_SUB(NOW(), INTERVAL 1 YEAR);

-- ============================================================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Add index for faster notification queries by date
CREATE INDEX IF NOT EXISTS idx_notification_timestamp 
ON notification(sent_timestamp DESC);

-- Add index for faster student communication lookup
CREATE INDEX IF NOT EXISTS idx_student_comm_preferred 
ON student_communication_accounts(student_id, is_preferred, account_status);

-- Add composite index for notification channel queries
CREATE INDEX IF NOT EXISTS idx_notification_channel_status 
ON notification(notification_channel, notification_status);

-- ============================================================================
-- GRANT PERMISSIONS (if needed)
-- ============================================================================

-- Grant permissions to the application user
-- GRANT SELECT, INSERT, UPDATE ON neurosync_db.teacher_communication_accounts TO 'your_app_user'@'localhost';
-- GRANT SELECT, INSERT, UPDATE ON neurosync_db.broadcast_log TO 'your_app_user'@'localhost';
-- GRANT EXECUTE ON PROCEDURE neurosync_db.get_teacher_broadcast_channels TO 'your_app_user'@'localhost';
-- GRANT EXECUTE ON PROCEDURE neurosync_db.log_broadcast_activity TO 'your_app_user'@'localhost';
-- GRANT EXECUTE ON FUNCTION neurosync_db.calculate_teacher_broadcast_efficiency TO 'your_app_user'@'localhost';

-- ============================================================================
-- COMPLETE!
-- ============================================================================

SELECT '✅ Teacher communication accounts schema created successfully!' AS status;
SELECT '✅ Broadcast logging system initialized!' AS status;
SELECT '✅ All views, procedures, and triggers created!' AS status;
SELECT '' AS '';
SELECT 'Next steps:' AS info;
SELECT '1. Add teacher platform accounts (Telegram, Discord IDs)' AS step;
SELECT '2. Configure broadcast_module with API tokens' AS step;
SELECT '3. Test broadcast functionality from admin dashboard' AS step;
SELECT '4. Monitor broadcast_dashboard view for delivery stats' AS step;