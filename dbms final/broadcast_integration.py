"""
NEUROSYNC: BROADCAST MODULE INTEGRATION
Sends multi-channel notifications based on database records
Integrates with Telegram, Discord, and Email channels
"""

import asyncio
import sys
import os

# Add broadcast_module to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'broadcast_module'))

from channels import email
from channels.telegram import send_telegram_async
from channels.discord import send_discord, close_client
from config import TELEGRAM_BOT_TOKEN, DISCORD_BOT_TOKEN, EMAIL_USER

import mysql.connector
from mysql.connector import Error


def create_db_connection():
    """Create MySQL database connection"""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='neurosync_db',
            user='root',
            password='Sr1*ganesh'
        )
        return connection
    except Error as e:
        print(f"❌ Database connection error: {e}")
        return None


def get_students_for_notification(class_name=None, student_id=None):
    """
    Get student communication details from database
    
    Args:
        class_name: If provided, get all students from this class
        student_id: If provided, get specific student only
    
    Returns:
        List of student dictionaries with communication details
    """
    connection = create_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        if student_id:
            # Get specific student
            query = """
                SELECT DISTINCT
                    s.student_id,
                    s.name,
                    s.email,
                    s.class,
                    sca.platform,
                    sca.account_identifier,
                    sca.account_username,
                    sca.is_preferred,
                    sca.account_status
                FROM student s
                LEFT JOIN student_communication_accounts sca 
                    ON s.student_id = sca.student_id
                WHERE s.student_id = %s
                    AND sca.is_preferred = TRUE
                    AND sca.account_status = 'active'
                ORDER BY s.student_id, sca.platform
            """
            cursor.execute(query, (student_id,))
        elif class_name:
            # Get all students from a class
            query = """
                SELECT DISTINCT
                    s.student_id,
                    s.name,
                    s.email,
                    s.class,
                    sca.platform,
                    sca.account_identifier,
                    sca.account_username,
                    sca.is_preferred,
                    sca.account_status
                FROM student s
                LEFT JOIN student_communication_accounts sca 
                    ON s.student_id = sca.student_id
                WHERE s.class = %s
                    AND sca.is_preferred = TRUE
                    AND sca.account_status = 'active'
                ORDER BY s.student_id, sca.platform
            """
            cursor.execute(query, (class_name,))
        else:
            # Get all students
            query = """
                SELECT DISTINCT
                    s.student_id,
                    s.name,
                    s.email,
                    s.class,
                    sca.platform,
                    sca.account_identifier,
                    sca.account_username,
                    sca.is_preferred,
                    sca.account_status
                FROM student s
                LEFT JOIN student_communication_accounts sca 
                    ON s.student_id = sca.student_id
                WHERE sca.is_preferred = TRUE
                    AND sca.account_status = 'active'
                ORDER BY s.student_id, sca.platform
            """
            cursor.execute(query)
        
        results = cursor.fetchall()
        
        # Group by student to handle multiple preferred channels
        students_dict = {}
        for row in results:
            sid = row['student_id']
            if sid not in students_dict:
                students_dict[sid] = {
                    'student_id': sid,
                    'name': row['name'],
                    'email': row['email'],
                    'class': row['class'],
                    'channels': []
                }
            
            # Add channel info
            students_dict[sid]['channels'].append({
                'platform': row['platform'],
                'identifier': row['account_identifier'],
                'username': row['account_username']
            })
        
        return list(students_dict.values())
        
    except Error as e:
        print(f"❌ Database query error: {e}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


async def send_notification_to_student(student, message, subject="Assignment Notification"):
    """
    Send notification to a single student on all their preferred channels
    
    Args:
        student: Student dictionary with communication details
        message: Message to send
        subject: Email subject (for email channel)
    
    Returns:
        Tuple of (success_count, fail_count, details)
    """
    success_count = 0
    fail_count = 0
    details = []
    
    for channel in student['channels']:
        platform = channel['platform']
        
        try:
            if platform == 'Telegram':
                if not TELEGRAM_BOT_TOKEN:
                    details.append(f"❌ {student['name']}: Telegram not configured")
                    fail_count += 1
                    continue
                    
                telegram_id = channel['identifier']
                await send_telegram_async(telegram_id, message)
                details.append(f"✅ {student['name']}: Telegram sent")
                success_count += 1
                
            elif platform == 'Discord':
                if not DISCORD_BOT_TOKEN:
                    details.append(f"❌ {student['name']}: Discord not configured")
                    fail_count += 1
                    continue
                    
                discord_id = channel['identifier']
                result = await send_discord(discord_id, message)
                if result:
                    details.append(f"✅ {student['name']}: Discord sent")
                    success_count += 1
                else:
                    details.append(f"❌ {student['name']}: Discord failed")
                    fail_count += 1
                    
            elif platform == 'Email':
                if not EMAIL_USER:
                    details.append(f"❌ {student['name']}: Email not configured")
                    fail_count += 1
                    continue
                    
                email_addr = channel['identifier']
                result = email.send_email(email_addr, subject, message)
                if result:
                    details.append(f"✅ {student['name']}: Email sent")
                    success_count += 1
                else:
                    details.append(f"❌ {student['name']}: Email failed")
                    fail_count += 1
                    
            elif platform == 'LMS':
                # LMS notifications are handled in the database
                details.append(f"✅ {student['name']}: LMS notification logged")
                success_count += 1
                
        except Exception as e:
            details.append(f"❌ {student['name']} ({platform}): {str(e)}")
            fail_count += 1
    
    return success_count, fail_count, details


async def broadcast_to_class(class_name, message, subject="Assignment Notification"):
    """
    Broadcast message to all students in a class
    
    Args:
        class_name: Class name to send to
        message: Message content
        subject: Email subject
    
    Returns:
        Tuple of (success_count, fail_count)
    """
    print(f"\n{'='*60}")
    print(f"Broadcasting to class: {class_name}")
    print(f"{'='*60}\n")
    
    students = get_students_for_notification(class_name=class_name)
    
    if not students:
        print(f"❌ No students found in class {class_name} with active communication channels")
        return 0, 0
    
    print(f"Found {len(students)} students with preferred channels\n")
    
    total_success = 0
    total_fail = 0
    
    for student in students:
        print(f"Sending to {student['name']} ({student['class']})...")
        print(f"  Channels: {', '.join([ch['platform'] for ch in student['channels']])}")
        
        success, fail, details = await send_notification_to_student(student, message, subject)
        
        for detail in details:
            print(f"  {detail}")
        
        total_success += success
        total_fail += fail
        print()
    
    # Clean up Discord client
    try:
        await close_client()
    except:
        pass
    
    return total_success, total_fail


async def broadcast_to_student(student_id, message, subject="Assignment Notification"):
    """
    Send notification to a specific student
    
    Args:
        student_id: Student ID
        message: Message content
        subject: Email subject
    
    Returns:
        Tuple of (success_count, fail_count)
    """
    print(f"\n{'='*60}")
    print(f"Sending notification to student ID: {student_id}")
    print(f"{'='*60}\n")
    
    students = get_students_for_notification(student_id=student_id)
    
    if not students:
        print(f"❌ No active communication channels found for student ID {student_id}")
        return 0, 0
    
    student = students[0]
    print(f"Student: {student['name']} ({student['class']})")
    print(f"Channels: {', '.join([ch['platform'] for ch in student['channels']])}\n")
    
    success, fail, details = await send_notification_to_student(student, message, subject)
    
    for detail in details:
        print(f"  {detail}")
    
    # Clean up Discord client
    try:
        await close_client()
    except:
        pass
    
    return success, fail


def broadcast_new_assignment(assignment_id, teacher_id):
    """
    Send notifications when a new assignment is created
    Called from ui.py after assignment creation
    
    Args:
        assignment_id: ID of the created assignment
        teacher_id: ID of the teacher who created it
    
    Returns:
        Tuple of (success_count, fail_count)
    """
    connection = create_db_connection()
    if not connection:
        return 0, 0
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get assignment details
        cursor.execute("""
            SELECT a.*, t.name as teacher_name
            FROM assignment a
            JOIN teacher t ON a.teacher_id = t.teacher_id
            WHERE a.assignment_id = %s
        """, (assignment_id,))
        
        assignment = cursor.fetchone()
        if not assignment:
            print(f"❌ Assignment {assignment_id} not found")
            return 0, 0
        
        # Prepare message
        message = f"""
📢 NEW ASSIGNMENT

📚 Subject: {assignment['subject']}
📝 Title: {assignment['title']}
👨‍🏫 Teacher: {assignment['teacher_name']}
📅 Due Date: {assignment['due_date']}
⏰ Deadline: {assignment['submission_deadline']}
📊 Max Marks: {assignment['max_marks']}

📋 Description:
{assignment['description']}

📌 Submission Instructions:
{assignment['submission_instructions']}

🔗 Submit via: {assignment['submission_mode']}
"""
        
        subject = f"New Assignment: {assignment['title']}"
        
        # Broadcast to class
        success, fail = asyncio.run(
            broadcast_to_class(assignment['class'], message, subject)
        )
        
        print(f"\n{'='*60}")
        print(f"BROADCAST SUMMARY")
        print(f"✅ Sent: {success}")
        print(f"❌ Failed: {fail}")
        print(f"{'='*60}")
        
        return success, fail
        
    except Error as e:
        print(f"❌ Error broadcasting assignment: {e}")
        return 0, 0
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def broadcast_assignment_graded(submission_id):
    """
    Send notification when an assignment is graded
    Called from ui.py after grading
    
    Args:
        submission_id: ID of the graded submission
    
    Returns:
        Tuple of (success_count, fail_count)
    """
    connection = create_db_connection()
    if not connection:
        return 0, 0
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get submission details
        cursor.execute("""
            SELECT s.*, a.title, a.max_marks, st.name as student_name, 
                   st.student_id, t.name as teacher_name
            FROM submission s
            JOIN assignment a ON s.assignment_id = a.assignment_id
            JOIN student st ON s.student_id = st.student_id
            JOIN teacher t ON a.teacher_id = t.teacher_id
            WHERE s.submission_id = %s
        """, (submission_id,))
        
        submission = cursor.fetchone()
        if not submission:
            print(f"❌ Submission {submission_id} not found")
            return 0, 0
        
        # Prepare message
        message = f"""
✅ ASSIGNMENT GRADED

📝 Assignment: {submission['title']}
👨‍🏫 Graded by: {submission['teacher_name']}

📊 YOUR SCORE
   Marks: {submission['marks_obtained']}/{submission['max_marks']}
   Percentage: {(submission['marks_obtained']/submission['max_marks']*100):.1f}%

💬 Remarks:
{submission['grading_remarks'] or 'No remarks provided'}

🔗 View details on LMS
"""
        
        subject = f"Assignment Graded: {submission['title']}"
        
        # Send to specific student
        success, fail = asyncio.run(
            broadcast_to_student(submission['student_id'], message, subject)
        )
        
        print(f"\n{'='*60}")
        print(f"NOTIFICATION SENT TO {submission['student_name']}")
        print(f"✅ Sent: {success} | ❌ Failed: {fail}")
        print(f"{'='*60}")
        
        return success, fail
        
    except Error as e:
        print(f"❌ Error broadcasting grade: {e}")
        return 0, 0
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def broadcast_reminder(assignment_id, days_before_due=1):
    """
    Send reminder notifications for upcoming assignments
    Can be called by a scheduler/cron job
    
    Args:
        assignment_id: Assignment to remind about
        days_before_due: How many days before deadline
    
    Returns:
        Tuple of (success_count, fail_count)
    """
    connection = create_db_connection()
    if not connection:
        return 0, 0
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get assignment details
        cursor.execute("""
            SELECT a.*, t.name as teacher_name,
                   DATEDIFF(a.submission_deadline, NOW()) as days_left
            FROM assignment a
            JOIN teacher t ON a.teacher_id = t.teacher_id
            WHERE a.assignment_id = %s
        """, (assignment_id,))
        
        assignment = cursor.fetchone()
        if not assignment:
            return 0, 0
        
        if assignment['days_left'] != days_before_due:
            print(f"⏭️ Skipping - assignment has {assignment['days_left']} days left, not {days_before_due}")
            return 0, 0
        
        # Get students who haven't submitted
        cursor.execute("""
            SELECT DISTINCT s.student_id
            FROM student s
            WHERE s.class = %s
            AND NOT EXISTS (
                SELECT 1 FROM submission sub
                WHERE sub.assignment_id = %s
                AND sub.student_id = s.student_id
            )
        """, (assignment['class'], assignment_id))
        
        pending_students = cursor.fetchall()
        
        if not pending_students:
            print(f"✅ All students have submitted for assignment: {assignment['title']}")
            return 0, 0
        
        message = f"""
⏰ ASSIGNMENT REMINDER

📝 Assignment: {assignment['title']}
📚 Subject: {assignment['subject']}
👨‍🏫 Teacher: {assignment['teacher_name']}

⚠️ DUE IN {assignment['days_left']} DAY(S)!
📅 Deadline: {assignment['submission_deadline']}

❗ You have NOT submitted this assignment yet!
🔗 Submit now via {assignment['submission_mode']}
"""
        
        subject = f"REMINDER: {assignment['title']} due in {assignment['days_left']} day(s)"
        
        total_success = 0
        total_fail = 0
        
        print(f"\n{'='*60}")
        print(f"Sending reminders for: {assignment['title']}")
        print(f"Pending students: {len(pending_students)}")
        print(f"{'='*60}\n")
        
        for student_record in pending_students:
            success, fail = asyncio.run(
                broadcast_to_student(student_record['student_id'], message, subject)
            )
            total_success += success
            total_fail += fail
        
        print(f"\n{'='*60}")
        print(f"REMINDER SUMMARY")
        print(f"✅ Sent: {total_success}")
        print(f"❌ Failed: {total_fail}")
        print(f"{'='*60}")
        
        return total_success, total_fail
        
    except Error as e:
        print(f"❌ Error sending reminders: {e}")
        return 0, 0
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


# Example usage functions for testing
def test_class_broadcast():
    """Test broadcasting to a class"""
    message = "This is a test notification from NeuroSync DBMS!"
    success, fail = asyncio.run(broadcast_to_class("CSE-3A", message))
    print(f"\nTest complete: {success} sent, {fail} failed")


def test_student_broadcast():
    """Test broadcasting to a specific student"""
    message = "This is a test notification for you!"
    success, fail = asyncio.run(broadcast_to_student(1, message))
    print(f"\nTest complete: {success} sent, {fail} failed")


if __name__ == "__main__":
    print("=" * 60)
    print("NEUROSYNC BROADCAST MODULE")
    print("=" * 60)
    
    # Check configuration
    print("\n🔧 Checking configuration...")
    print(f"  {'✅' if TELEGRAM_BOT_TOKEN else '❌'} Telegram")
    print(f"  {'✅' if DISCORD_BOT_TOKEN else '❌'} Discord")
    print(f"  {'✅' if EMAIL_USER else '❌'} Email")
    
    # Test database connection
    conn = create_db_connection()
    if conn:
        print(f"  ✅ Database")
        conn.close()
    else:
        print(f"  ❌ Database")
    
    print("\n" + "=" * 60)
    print("Available functions:")
    print("  - broadcast_new_assignment(assignment_id, teacher_id)")
    print("  - broadcast_assignment_graded(submission_id)")
    print("  - broadcast_reminder(assignment_id, days_before=1)")
    print("  - test_class_broadcast()")
    print("  - test_student_broadcast()")
    print("=" * 60)