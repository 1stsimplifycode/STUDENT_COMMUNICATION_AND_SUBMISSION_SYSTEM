/*
================================================================================
TRANSACTION PROOF SCRIPT FOR NEUROSYNC DBMS PROJECT
================================================================================
Purpose: Demonstrate MySQL transaction support with COMMIT and ROLLBACK
Team: Adishree, Bhavani & Monica
Database: neurosync_db
Date: 2025

This script provides step-by-step proof that the database supports ACID transactions
with visual verification at each stage for DBMS project documentation.
================================================================================
*/

-- ============================================================================
-- STEP 0: INITIAL SETUP AND DATABASE SELECTION
-- ============================================================================
SELECT '========================================' AS '';
SELECT 'NEUROSYNC TRANSACTION PROOF SCRIPT' AS '';
SELECT '========================================' AS '';
SELECT '' AS '';

-- Use your database (replace with your actual database name if different)
USE neurosync_db;

SELECT 'âœ… Database selected: neurosync_db' AS Status;
SELECT '' AS '';

-- ============================================================================
-- STEP 1: VERIFY TRANSACTION SUPPORT (InnoDB ENGINE)
-- ============================================================================
SELECT '----------------------------------------' AS '';
SELECT 'STEP 1: VERIFY TRANSACTION SUPPORT' AS '';
SELECT '----------------------------------------' AS '';

-- Check available storage engines and their transaction support
SHOW ENGINES;

SELECT '' AS '';
SELECT 'âœ… InnoDB engine supports transactions (Support = YES in SHOW ENGINES output)' AS Verification;
SELECT '' AS '';

-- Verify that action_log table uses InnoDB
SELECT 
    TABLE_NAME,
    ENGINE,
    TABLE_ROWS
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'neurosync_db' 
  AND TABLE_NAME = 'action_log';

SELECT '' AS '';
SELECT 'âœ… action_log table uses InnoDB engine (transaction-safe)' AS Verification;
SELECT '' AS '';

-- ============================================================================
-- STEP 2: DISABLE AUTOCOMMIT FOR MANUAL TRANSACTION CONTROL
-- ============================================================================
SELECT '----------------------------------------' AS '';
SELECT 'STEP 2: DISABLE AUTOCOMMIT' AS '';
SELECT '----------------------------------------' AS '';

-- Save current autocommit status
SELECT @@autocommit AS 'Current Autocommit Status (1=ON, 0=OFF)';

-- Disable autocommit to enable manual transaction control
SET autocommit = 0;

-- Verify autocommit is disabled
SELECT @@autocommit AS 'Autocommit After Disabling (Should be 0)';

SELECT '' AS '';
SELECT 'âœ… Autocommit disabled - Manual transaction mode activated' AS Status;
SELECT '' AS '';

-- ============================================================================
-- STEP 3: DEMONSTRATE SUCCESSFUL TRANSACTION WITH COMMIT
-- ============================================================================
SELECT '========================================' AS '';
SELECT 'PART A: SUCCESSFUL TRANSACTION (COMMIT)' AS '';
SELECT '========================================' AS '';
SELECT '' AS '';

-- Show current record count before transaction
SELECT '----------------------------------------' AS '';
SELECT 'BEFORE TRANSACTION: Initial State' AS '';
SELECT '----------------------------------------' AS '';

SELECT COUNT(*) AS 'Total Records in action_log (BEFORE)' 
FROM action_log;

SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 3A: START TRANSACTION
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 3A: START TRANSACTION #1' AS '';
SELECT '----------------------------------------' AS '';

START TRANSACTION;

SELECT 'âœ… Transaction #1 started' AS Status;
SELECT NOW() AS 'Transaction Start Time';
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 3B: INSERT TEST RECORD WITHIN TRANSACTION
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 3B: INSERT TEST RECORD' AS '';
SELECT '----------------------------------------' AS '';

-- Insert a test record into action_log
INSERT INTO action_log (user_id, action_type, details, timestamp)
VALUES (
    1, 
    'TEST_TRANSACTION_COMMIT', 
    'This record demonstrates successful COMMIT - Transaction Proof Test', 
    NOW()
);

SELECT 'âœ… Test record inserted (not yet committed)' AS Status;
SELECT LAST_INSERT_ID() AS 'Inserted Record ID';
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 3C: VERIFY TRANSACTION STATE
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 3C: VERIFY ACTIVE TRANSACTION STATE' AS '';
SELECT '----------------------------------------' AS '';

-- Check autocommit status
SELECT @@autocommit AS 'Autocommit Status (0 = Manual Mode)';

-- View active transactions in InnoDB
SELECT 
    trx_id AS 'Transaction ID',
    trx_state AS 'Transaction State',
    trx_started AS 'Started At',
    trx_rows_modified AS 'Rows Modified'
FROM information_schema.INNODB_TRX;

SELECT '' AS '';
SELECT 'âœ… Active transaction visible in INNODB_TRX' AS Status;
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 3D: VIEW UNCOMMITTED DATA IN CURRENT SESSION
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 3D: VIEW DATA IN CURRENT SESSION' AS '';
SELECT '----------------------------------------' AS '';

SELECT 
    log_id,
    user_id,
    action_type,
    details,
    timestamp
FROM action_log
WHERE action_type = 'TEST_TRANSACTION_COMMIT'
ORDER BY timestamp DESC
LIMIT 1;

SELECT '' AS '';
SELECT 'âœ… Record VISIBLE in current session (uncommitted)' AS Status;
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- IMPORTANT ISOLATION TEST INSTRUCTION
-- ----------------------------------------------------------------------------
SELECT '****************************************' AS '';
SELECT '⚠️  ISOLATION TEST INSTRUCTION' AS '';
SELECT '****************************************' AS '';
SELECT 'Open a NEW MySQL session/connection now and run:' AS '';
SELECT '' AS '';
SELECT 'USE neurosync_db;' AS 'Command 1';
SELECT 'SELECT * FROM action_log WHERE action_type = ''TEST_TRANSACTION_COMMIT'';' AS 'Command 2';
SELECT '' AS '';
SELECT 'EXPECTED RESULT: Record should NOT be visible in the new session' AS '';
SELECT 'REASON: Transaction not yet committed (ACID Isolation property)' AS '';
SELECT '' AS '';
SELECT 'Press Enter after checking in another session to continue...' AS '';
SELECT '****************************************' AS '';
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 3E: COMMIT THE TRANSACTION
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 3E: COMMIT TRANSACTION #1' AS '';
SELECT '----------------------------------------' AS '';

COMMIT;

SELECT 'âœ… TRANSACTION COMMITTED SUCCESSFULLY' AS Status;
SELECT NOW() AS 'Commit Time';
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 3F: VERIFY DATA PERSISTENCE AFTER COMMIT
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 3F: VERIFY DATA AFTER COMMIT' AS '';
SELECT '----------------------------------------' AS '';

-- Show record count after commit
SELECT COUNT(*) AS 'Total Records in action_log (AFTER COMMIT)' 
FROM action_log;

-- Display the committed record
SELECT 
    log_id,
    user_id,
    action_type,
    details,
    timestamp
FROM action_log
WHERE action_type = 'TEST_TRANSACTION_COMMIT'
ORDER BY timestamp DESC
LIMIT 1;

SELECT '' AS '';
SELECT 'âœ… Record is now PERMANENTLY saved and visible to all sessions' AS Status;
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- VERIFICATION INSTRUCTION AFTER COMMIT
-- ----------------------------------------------------------------------------
SELECT '****************************************' AS '';
SELECT 'âœ… COMMIT VERIFICATION' AS '';
SELECT '****************************************' AS '';
SELECT 'Now check the OTHER MySQL session again:' AS '';
SELECT '' AS '';
SELECT 'SELECT * FROM action_log WHERE action_type = ''TEST_TRANSACTION_COMMIT'';' AS 'Command';
SELECT '' AS '';
SELECT 'EXPECTED RESULT: Record should NOW be visible' AS '';
SELECT 'REASON: Transaction committed - data is persistent (ACID Durability)' AS '';
SELECT '****************************************' AS '';
SELECT '' AS '';

-- ============================================================================
-- STEP 4: DEMONSTRATE FAILED TRANSACTION WITH ROLLBACK
-- ============================================================================
SELECT '========================================' AS '';
SELECT 'PART B: FAILED TRANSACTION (ROLLBACK)' AS '';
SELECT '========================================' AS '';
SELECT '' AS '';

-- Show current record count before second transaction
SELECT '----------------------------------------' AS '';
SELECT 'BEFORE ROLLBACK TEST: Current State' AS '';
SELECT '----------------------------------------' AS '';

SELECT COUNT(*) AS 'Total Records in action_log (BEFORE ROLLBACK TEST)' 
FROM action_log;

SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 4A: START SECOND TRANSACTION
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 4A: START TRANSACTION #2' AS '';
SELECT '----------------------------------------' AS '';

START TRANSACTION;

SELECT 'âœ… Transaction #2 started' AS Status;
SELECT NOW() AS 'Transaction Start Time';
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 4B: INSERT SECOND TEST RECORD
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 4B: INSERT TEST RECORD (TO BE ROLLED BACK)' AS '';
SELECT '----------------------------------------' AS '';

-- Insert another test record
INSERT INTO action_log (user_id, action_type, details, timestamp)
VALUES (
    1, 
    'TEST_TRANSACTION_ROLLBACK', 
    'This record will be ROLLED BACK - will not persist', 
    NOW()
);

SELECT 'âœ… Test record inserted (not yet committed)' AS Status;
SELECT LAST_INSERT_ID() AS 'Inserted Record ID (Will be rolled back)';
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 4C: VERIFY RECORD EXISTS BEFORE ROLLBACK
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 4C: VERIFY RECORD BEFORE ROLLBACK' AS '';
SELECT '----------------------------------------' AS '';

-- Show the record exists in current session
SELECT 
    log_id,
    user_id,
    action_type,
    details,
    timestamp
FROM action_log
WHERE action_type = 'TEST_TRANSACTION_ROLLBACK'
ORDER BY timestamp DESC
LIMIT 1;

SELECT COUNT(*) AS 'Records with ROLLBACK type (Should be 1)' 
FROM action_log 
WHERE action_type = 'TEST_TRANSACTION_ROLLBACK';

SELECT '' AS '';
SELECT 'âœ… Record temporarily visible in current session (before rollback)' AS Status;
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 4D: ROLLBACK THE TRANSACTION
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 4D: ROLLBACK TRANSACTION #2' AS '';
SELECT '----------------------------------------' AS '';

ROLLBACK;

SELECT 'âœ… TRANSACTION ROLLED BACK SUCCESSFULLY' AS Status;
SELECT 'All changes in this transaction have been UNDONE' AS Result;
SELECT NOW() AS 'Rollback Time';
SELECT '' AS '';

-- ----------------------------------------------------------------------------
-- STEP 4E: VERIFY RECORD WAS REMOVED BY ROLLBACK
-- ----------------------------------------------------------------------------
SELECT '----------------------------------------' AS '';
SELECT 'STEP 4E: VERIFY DATA AFTER ROLLBACK' AS '';
SELECT '----------------------------------------' AS '';

-- Check if the rolled-back record exists
SELECT COUNT(*) AS 'Records with ROLLBACK type (Should be 0)' 
FROM action_log 
WHERE action_type = 'TEST_TRANSACTION_ROLLBACK';

-- Try to select the record (should return empty)
SELECT 
    log_id,
    user_id,
    action_type,
    details,
    timestamp
FROM action_log
WHERE action_type = 'TEST_TRANSACTION_ROLLBACK';

SELECT '' AS '';
SELECT 'âœ… Record successfully removed - ROLLBACK worked correctly' AS Status;
SELECT '' AS '';

-- Show only committed records remain
SELECT COUNT(*) AS 'Total Records in action_log (AFTER ROLLBACK)' 
FROM action_log;

SELECT '' AS '';

-- ============================================================================
-- STEP 5: COMPARE COMMIT VS ROLLBACK RESULTS
-- ============================================================================
SELECT '========================================' AS '';
SELECT 'STEP 5: COMPARISON OF RESULTS' AS '';
SELECT '========================================' AS '';
SELECT '' AS '';

SELECT '----------------------------------------' AS '';
SELECT 'FINAL VERIFICATION' AS '';
SELECT '----------------------------------------' AS '';

-- Show committed record exists
SELECT 
    'COMMITTED' AS Transaction_Type,
    COUNT(*) AS Record_Count,
    'âœ… Exists in database' AS Status
FROM action_log
WHERE action_type = 'TEST_TRANSACTION_COMMIT'

UNION ALL

-- Show rolled-back record does not exist
SELECT 
    'ROLLED BACK' AS Transaction_Type,
    COUNT(*) AS Record_Count,
    'âœ… Successfully removed' AS Status
FROM action_log
WHERE action_type = 'TEST_TRANSACTION_ROLLBACK';

SELECT '' AS '';
SELECT 'âœ… COMMIT: Data persisted permanently' AS Result_1;
SELECT 'âœ… ROLLBACK: Data removed completely' AS Result_2;
SELECT '' AS '';

-- ============================================================================
-- STEP 6: RE-ENABLE AUTOCOMMIT
-- ============================================================================
SELECT '----------------------------------------' AS '';
SELECT 'STEP 6: RESTORE AUTOCOMMIT MODE' AS '';
SELECT '----------------------------------------' AS '';

-- Re-enable autocommit
SET autocommit = 1;

-- Verify autocommit is enabled
SELECT @@autocommit AS 'Autocommit Status (1=Restored to Default)';

SELECT '' AS '';
SELECT 'âœ… Autocommit restored to default mode' AS Status;
SELECT '' AS '';

-- ============================================================================
-- FINAL SUMMARY
-- ============================================================================
SELECT '========================================' AS '';
SELECT 'TRANSACTION PROOF COMPLETE' AS '';
SELECT '========================================' AS '';
SELECT '' AS '';

SELECT 'DEMONSTRATED FEATURES:' AS '';
SELECT '1. âœ… InnoDB engine supports transactions' AS Feature_1;
SELECT '2. âœ… Manual transaction control (autocommit=0)' AS Feature_2;
SELECT '3. âœ… START TRANSACTION command' AS Feature_3;
SELECT '4. âœ… COMMIT - successful data persistence' AS Feature_4;
SELECT '5. âœ… ROLLBACK - complete data reversal' AS Feature_5;
SELECT '6. âœ… Transaction isolation between sessions' AS Feature_6;
SELECT '7. âœ… ACID properties verification' AS Feature_7;
SELECT '' AS '';

SELECT 'DATABASE: neurosync_db' AS Detail_1;
SELECT 'TABLE: action_log' AS Detail_2;
SELECT 'ENGINE: InnoDB (Transaction-safe)' AS Detail_3;
SELECT '' AS '';

SELECT '========================================' AS '';
SELECT 'Team: Adishree, Bhavani & Monica' AS '';
SELECT 'NEUROSYNC DBMS PROJECT - 2025' AS '';
SELECT '========================================' AS '';

/*
================================================================================
CLEANUP (OPTIONAL)
================================================================================
If you want to remove the test record after taking screenshots, uncomment:

DELETE FROM action_log WHERE action_type = 'TEST_TRANSACTION_COMMIT';

================================================================================
SCREENSHOT CHECKLIST FOR REPORT
================================================================================
Capture these key outputs for your DBMS report:

âœ… SHOW ENGINES output (proving InnoDB support)
âœ… autocommit status changes (0 and 1)
âœ… INNODB_TRX showing active transaction
âœ… Record visible before COMMIT in same session
âœ… Record NOT visible in another session before COMMIT
âœ… Record visible in both sessions after COMMIT
âœ… Record visible before ROLLBACK
âœ… Record disappeared after ROLLBACK
âœ… Final comparison table (COMMIT vs ROLLBACK)

================================================================================
*/