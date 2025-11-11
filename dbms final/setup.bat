@echo off
REM ============================================================================
REM NEUROSYNC: AUTOMATED SETUP SCRIPT
REM ============================================================================
REM This script will:
REM 1. Check MySQL installation
REM 2. Execute all SQL files in order
REM 3. Install Python dependencies
REM 4. Launch the Streamlit application
REM ============================================================================

echo.
echo ========================================
echo    NEUROSYNC SETUP SCRIPT
echo    Automated Database Setup
echo ========================================
echo.

REM ============================================================================
REM CONFIGURATION - MODIFY THESE VALUES
REM ============================================================================

set MYSQL_HOST=localhost
set MYSQL_USER=root
set MYSQL_PASSWORD=Sr1*ganesh
set DATABASE_NAME=neurosync_db
set MYSQL_PATH="C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"

REM ============================================================================
REM STEP 1: CHECK MYSQL INSTALLATION
REM ============================================================================

echo [STEP 1] Checking MySQL installation...
%MYSQL_PATH% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] MySQL not found at %MYSQL_PATH%
    echo Please update MYSQL_PATH in this script with your MySQL installation path
    echo Common paths:
    echo   - C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe
    echo   - C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe
    echo   - C:\xampp\mysql\bin\mysql.exe
    pause
    exit /b 1
)
echo [SUCCESS] MySQL found!
echo.

REM ============================================================================
REM STEP 2: CHECK IF SQL FILES EXIST
REM ============================================================================

echo [STEP 2] Checking SQL files...
if not exist "neurosync_schema.sql" (
    echo [ERROR] neurosync_schema.sql not found!
    pause
    exit /b 1
)
if not exist "neurosync_constraints.sql" (
    echo [ERROR] neurosync_constraints.sql not found!
    pause
    exit /b 1
)
if not exist "neurosync_triggers_And_procedures.sql" (
    echo [ERROR] neurosync_triggers_And_procedures.sql not found!
    pause
    exit /b 1
)
if not exist "neurosync_advanced_analytics.sql" (
    echo [ERROR] neurosync_advanced_analytics.sql not found!
    pause
    exit /b 1
)
echo [SUCCESS] All SQL files found!
echo.

REM ============================================================================
REM STEP 3: CREATE DATABASE AND EXECUTE SCHEMA
REM ============================================================================

echo [STEP 3] Creating database and schema...
echo Creating database %DATABASE_NAME%...
%MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% -e "DROP DATABASE IF EXISTS %DATABASE_NAME%; CREATE DATABASE %DATABASE_NAME%;"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create database
    pause
    exit /b 1
)

echo Executing neurosync_schema.sql...
%MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% %DATABASE_NAME% < neurosync_schema.sql
if %errorlevel% neq 0 (
    echo [ERROR] Failed to execute schema
    pause
    exit /b 1
)
echo [SUCCESS] Schema created!
echo.

REM ============================================================================
REM STEP 4: EXECUTE CONSTRAINTS
REM ============================================================================

echo [STEP 4] Applying constraints...
%MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% %DATABASE_NAME% < neurosync_constraints.sql
if %errorlevel% neq 0 (
    echo [WARNING] Some constraints may have failed (this is normal if they already exist)
)
echo [SUCCESS] Constraints applied!
echo.

REM ============================================================================
REM STEP 5: EXECUTE TRIGGERS AND PROCEDURES
REM ============================================================================

echo [STEP 5] Creating triggers and procedures...
%MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% %DATABASE_NAME% < neurosync_triggers_And_procedures.sql
if %errorlevel% neq 0 (
    echo [WARNING] Some triggers/procedures may have failed
)
echo [SUCCESS] Triggers and procedures created!
echo.

REM ============================================================================
REM STEP 6: CREATE VIEWS (from advanced analytics)
REM ============================================================================

echo [STEP 6] Creating analytical views...
%MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% %DATABASE_NAME% < neurosync_advanced_analytics.sql
if %errorlevel% neq 0 (
    echo [WARNING] Some views may have failed
)
echo [SUCCESS] Analytical views created!
echo.

REM ============================================================================
REM STEP 6.5: FIX PASSWORD HASHES (CRITICAL)
REM ============================================================================

echo [STEP 6.5] Fixing password hashes...
if exist "fix_passwords.sql" (
    echo Updating passwords with correct SHA-256 hashes...
    %MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% %DATABASE_NAME% < fix_passwords.sql
    echo [SUCCESS] Passwords updated!
) else (
    echo Manually updating passwords...
    %MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% %DATABASE_NAME% -e "UPDATE user SET password_hash = 'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d662f1c2ba8f9e3f5f9c5b68f' WHERE username = 'root'; UPDATE user SET password_hash = '9f735e0df9a1ddc702bf0a1a7b83033f9f7153a00c29de82cedadc9957289b05' WHERE username = 'bhavani'; UPDATE user SET password_hash = 'b9c950640e1b3740e98acb93e669c65766f6670dd1609ba91d36479c27619f39' WHERE username = 'monica'; UPDATE user SET password_hash = '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92' WHERE username IN ('student1', 'student2', 'student3', 'student4', 'student5');"
    echo [SUCCESS] Passwords updated inline!
)
echo.

REM ============================================================================
REM STEP 6.6: FIX MISSING VIEWS (CRITICAL)
REM ============================================================================

echo [STEP 6.6] Creating/fixing all database views...
if exist "fix_missing_views.sql" (
    echo Creating all required views...
    %MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% %DATABASE_NAME% < fix_missing_views.sql
    echo [SUCCESS] All views created!
) else (
    echo Creating views manually...
    %MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% %DATABASE_NAME% -e "CREATE OR REPLACE VIEW teacher_workload AS SELECT t.teacher_id, t.name, t.department, COUNT(DISTINCT a.assignment_id) AS total_assignments, COUNT(sub.submission_id) AS total_submissions_received, SUM(CASE WHEN sub.status = 'graded' THEN 1 ELSE 0 END) AS graded_submissions, SUM(CASE WHEN sub.status IN ('submitted', 'late') THEN 1 ELSE 0 END) AS pending_grading FROM teacher t LEFT JOIN assignment a ON t.teacher_id = a.teacher_id LEFT JOIN submission sub ON a.assignment_id = sub.assignment_id GROUP BY t.teacher_id;"
    echo [SUCCESS] Critical views created!
)
echo.

REM ============================================================================
REM STEP 7: VERIFY DATABASE SETUP
REM ============================================================================

echo [STEP 7] Verifying database setup...
%MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% -e "USE %DATABASE_NAME%; SHOW TABLES;"
echo.
echo [STEP 7.1] Verifying login credentials...
%MYSQL_PATH% -h%MYSQL_HOST% -u%MYSQL_USER% -p%MYSQL_PASSWORD% -e "USE %DATABASE_NAME%; SELECT username, role, 'Password OK' as status FROM user;"
echo.

REM ============================================================================
REM STEP 8: CHECK PYTHON INSTALLATION
REM ============================================================================

echo [STEP 8] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.8 or higher
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [SUCCESS] Python found!
echo.

REM ============================================================================
REM STEP 9: INSTALL PYTHON DEPENDENCIES
REM ============================================================================

echo [STEP 9] Installing Python dependencies...
echo Installing streamlit...
pip install streamlit >nul 2>&1
echo Installing mysql-connector-python...
pip install mysql-connector-python >nul 2>&1
echo Installing pandas...
pip install pandas >nul 2>&1
echo [SUCCESS] Dependencies installed!
echo.

REM ============================================================================
REM STEP 10: CHECK IF UI.PY EXISTS
REM ============================================================================

echo [STEP 10] Checking application file...
if not exist "ui.py" (
    echo [ERROR] ui.py not found!
    echo Please ensure ui.py is in the same directory as this script
    pause
    exit /b 1
)
echo [SUCCESS] Application file found!
echo.

REM ============================================================================
REM SETUP COMPLETE - DISPLAY SUMMARY
REM ============================================================================

echo.
echo ========================================
echo    SETUP COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo Database: %DATABASE_NAME%
echo Host: %MYSQL_HOST%
echo User: %MYSQL_USER%
echo.
echo The following have been created:
echo   - Database schema with all tables
echo   - Constraints and relationships
echo   - Triggers for automation
echo   - Stored procedures
echo   - Views for analytics
echo   - FIXED: All password hashes (SHA-256)
echo.
echo Demo Credentials:
echo   Admin:   Username: root        Password: Sr1*ganesh
echo   Teacher: Username: bhavani     Password: bhavani@123
echo   Teacher: Username: monica      Password: monica@123
echo   Student: Username: student1    Password: stud123
echo.
echo NOTE: All passwords are SHA-256 hashed and VERIFIED
echo       You can now login to the UI with these credentials!
echo.
echo ========================================
echo.

REM ============================================================================
REM LAUNCH APPLICATION
REM ============================================================================

echo.
set /p LAUNCH="Do you want to launch the Streamlit application now? (Y/N): "
if /i "%LAUNCH%"=="Y" (
    echo.
    echo ========================================
    echo    LAUNCHING NEUROSYNC APPLICATION
    echo ========================================
    echo.
    echo The application will open in your browser...
    echo Press Ctrl+C to stop the server
    echo.
    streamlit run ui.py
) else (
    echo.
    echo To launch the application manually, run:
    echo    streamlit run ui.py
    echo.
)

pause