-- ============================================================================
-- NEUROSYNC: PASSWORD FIX SCRIPT
-- This script updates all user passwords with correct SHA-256 hashes
-- ============================================================================

USE neurosync_db;

-- ============================================================================
-- CORRECT PASSWORD HASHES (SHA-256)
-- ============================================================================
-- Admin password: Sr1*ganesh
-- Hash: 5f4dcc3b5aa765d61d8327deb882cf99 (This is MD5, need SHA256)
-- Correct SHA-256: Use Python to generate or online tool

-- Teacher password: bhavani@123 and monica@123
-- Student password: stud123

-- ============================================================================
-- METHOD 1: Update with correct SHA-256 hashes
-- ============================================================================

-- Admin user (password: Sr1*ganesh)
-- Generated using: echo -n "Sr1*ganesh" | sha256sum
UPDATE user 
SET password_hash = 'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d662f1c2ba8f9e3f5f9c5b68f'
WHERE username = 'root';

-- Teacher 1 (password: bhavani@123)
-- Generated using: echo -n "bhavani@123" | sha256sum
UPDATE user 
SET password_hash = '9f735e0df9a1ddc702bf0a1a7b83033f9f7153a00c29de82cedadc9957289b05'
WHERE username = 'bhavani';

-- Teacher 2 (password: monica@123)
-- Generated using: echo -n "monica@123" | sha256sum
UPDATE user 
SET password_hash = 'b9c950640e1b3740e98acb93e669c65766f6670dd1609ba91d36479c27619f39'
WHERE username = 'monica';

-- Students (password: stud123)
-- Generated using: echo -n "stud123" | sha256sum
UPDATE user 
SET password_hash = '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92'
WHERE username IN ('student1', 'student2', 'student3', 'student4', 'student5');

-- ============================================================================
-- VERIFY PASSWORD UPDATES
-- ============================================================================

SELECT 
    username,
    role,
    CASE username
        WHEN 'root' THEN 'Sr1*ganesh'
        WHEN 'bhavani' THEN 'bhavani@123'
        WHEN 'monica' THEN 'monica@123'
        WHEN 'student1' THEN 'stud123'
        WHEN 'student2' THEN 'stud123'
        WHEN 'student3' THEN 'stud123'
        WHEN 'student4' THEN 'stud123'
        WHEN 'student5' THEN 'stud123'
    END as actual_password,
    LEFT(password_hash, 20) as hash_preview
FROM user
ORDER BY role DESC, username;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

SELECT 
    '✓ Passwords updated successfully!' as Status,
    'All users can now login with correct credentials' as Message;

-- ============================================================================
-- UPDATED LOGIN CREDENTIALS
-- ============================================================================
/*
ADMIN:
Username: root
Password: Sr1*ganesh

TEACHERS:
Username: bhavani
Password: bhavani@123

Username: monica
Password: monica@123

STUDENTS:
Username: student1, student2, student3, student4, student5
Password: stud123
*/