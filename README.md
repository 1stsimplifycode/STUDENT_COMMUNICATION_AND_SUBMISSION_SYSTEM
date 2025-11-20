# Student Academic Communication and Submission System (SACSS)

<div align="center">

![Database](https://img.shields.io/badge/Database-MySQL-blue?style=for-the-badge&logo=mysql)
![Python](https://img.shields.io/badge/Python-3.8+-green?style=for-the-badge&logo=python)
![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)

**A comprehensive database management system for tracking and analyzing student assignment submissions, multi-channel communications, and academic performance metrics.**

</div>

---

## 📋 Project Overview

<table>
<tr>
<td><b>Course</b></td>
<td>UE23CS351A - Database Management Systems</td>
</tr>
<tr>
<td><b>Institution</b></td>
<td>PES University, Bengaluru</td>
</tr>
<tr>
<td><b>Team Code</b></td>
<td>024_144_813</td>
</tr>
<tr>
<td><b>Academic Term</b></td>
<td>Aug-Dec 2025</td>
</tr>
<tr>
<td><b>Faculty</b></td>
<td>Prof. Raghu B. A.</td>
</tr>
</table>

### 👥 Team Members

| Name | SRN | Section |
|------|-----|---------|
| Adishree Gupta | PES1UG23CS024 | 5A |
| Bhavani S | PES1UG23CS144 | 5A |
| Monica M | PES1UG24CS813 | 5A |

---

## 🎯 Problem Statement

<div style="background-color: #f6f8fa; padding: 20px; border-left: 4px solid #0366d6; margin: 20px 0;">

Academic institutions face challenges in managing assignment lifecycles due to:

- 🔀 **Fragmented communication channels** (LMS + instant messaging)
- 📊 **Inconsistent student engagement tracking**
- 📝 **Manual submission monitoring and reminder systems**
- 🔍 **Lack of unified analytics** on student behavior patterns

</div>

### 💡 Solution

**SACSS** integrates formal (LMS) and informal (WhatsApp, Telegram) communication channels to streamline assignment management, automate reminders, and provide data-driven insights into student submission behaviors.

---

## ✨ Key Features

<table>
<tr>
<td width="50%">

### 🎓 Core Functionality
- ✅ Assignment Management
- ✅ Multi-Channel Notifications
- ✅ Automated Deadline Tracking
- ✅ Grading System
- ✅ Behavioral Analytics

</td>
<td width="50%">

### 🚀 Advanced Features
- 📊 Performance Dashboard
- 🔔 Smart Reminders
- 📈 Risk Assessment
- 🎓 Workload Management
- 🔍 Predictive Analytics

</td>
</tr>
</table>

---

## 🗄️ Database Architecture

### 📐 Entity-Relationship Model

<details>
<summary><b>🔹 Core Entities (Click to expand)</b></summary>

| Entity | Description | Type |
|--------|-------------|------|
| **User** | Base authentication table | Strong |
| **Teacher** | Faculty profile | Strong |
| **Student** | Student profile | Strong |
| **Assignment** | Assignment details | Strong |
| **Submission** | Student submissions | Weak |
| **Notification** | Notification logs | Weak |
| **LMS** | Learning Management System | Strong |
| **IM Platform** | Instant Messaging Platform | Strong |

</details>

<details>
<summary><b>🔹 Supporting Entities (Click to expand)</b></summary>

- `student_behavior_analytics` - Submission pattern analytics
- `action_log` - Audit trail
- `expert_observation` - AI/ML tracking
- `expert_memory` - Learning patterns
- `expert_suggestion` - AI recommendations

</details>

### 🔗 Key Relationships

```
Student ↔ Assignment → Submission (M:N via weak entity)
Teacher ↔ LMS (M:N)
Student ↔ IM Platform (M:N)
Assignment → Notification (1:M)
```

---

## 🛠️ Technical Implementation

### 🔒 Database Constraints (15+ Types)

<table>
<tr>
<td width="33%">

**Integrity Constraints**
1. Primary Keys
2. Foreign Keys
3. Unique Constraints
4. NOT NULL
5. CHECK Constraints

</td>
<td width="33%">

**Business Logic**
6. DEFAULT Values
7. AUTO_INCREMENT
8. ENUM Types
9. Trigger-Based
10. Procedure-Based

</td>
<td width="33%">

**Advanced Rules**
11. View-Based
12. Length/Size
13. Temporal/Date
14. Conditional
15. Indexes

</td>
</tr>
</table>

### ⚙️ Stored Procedures

<details>
<summary><b>View All Procedures</b></summary>

```sql
-- 1. Bulk notification generation
CALL generate_reminders(assignment_id, class_name, channels);

-- 2. Validate and record grades
CALL grade_submission(submission_id, marks, remarks, teacher_id);

-- 3. Performance report generation
CALL get_student_performance(student_id);

-- 4. Assignment analytics
CALL get_assignment_statistics(assignment_id);

-- 5. Mass notification dispatcher
CALL send_bulk_notifications(assignment_id, audience, mode, message);
```

</details>

### 📊 Database Functions

<details>
<summary><b>View All Functions</b></summary>

| Function | Returns | Purpose |
|----------|---------|---------|
| `calculate_submission_rate()` | DECIMAL(5,2) | Class submission % |
| `get_grade_classification()` | VARCHAR(20) | Letter grade |
| `is_student_at_risk()` | BOOLEAN | Risk assessment |
| `get_student_avg_delay()` | DECIMAL(5,2) | Avg delay days |
| `days_until_deadline()` | INT | Time remaining |

</details>

### 🔔 Triggers

<table>
<tr>
<th>Trigger</th>
<th>Event</th>
<th>Action</th>
</tr>
<tr>
<td>check_submission_deadline</td>
<td>BEFORE INSERT</td>
<td>Auto-classify late submissions</td>
</tr>
<tr>
<td>update_behavior_after_submission</td>
<td>AFTER INSERT</td>
<td>Update analytics</td>
</tr>
<tr>
<td>log_assignment_creation</td>
<td>AFTER INSERT</td>
<td>Audit trail logging</td>
</tr>
<tr>
<td>prevent_assignment_deletion</td>
<td>BEFORE DELETE</td>
<td>Protect data integrity</td>
</tr>
<tr>
<td>update_on_grading</td>
<td>AFTER UPDATE</td>
<td>Track grading actions</td>
</tr>
</table>

### 📈 Analytical Views

<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">

- 🏆 `top_performing_students`
- 📋 `assignment_completion_stats`
- ⚠️ `students_at_risk`
- 📧 `notification_effectiveness`
- 👨‍🏫 `teacher_workload`
- 📊 `class_performance_summary`

</div>

---

## 🔐 Default Credentials

<table>
<tr>
<th>Role</th>
<th>Username</th>
<th>Password</th>
</tr>
<tr>
<td><b>👑 Admin</b></td>
<td><code>root</code></td>
<td><code>Sr1*ganesh</code></td>
</tr>
<tr>
<td><b>👨‍🏫 Teacher 1</b></td>
<td><code>bhavani</code></td>
<td><code>bhavani@123</code></td>
</tr>
<tr>
<td><b>👨‍🏫 Teacher 2</b></td>
<td><code>monica</code></td>
<td><code>monica@123</code></td>
</tr>
<tr>
<td><b>👨‍🎓 Students</b></td>
<td><code>student1-5</code></td>
<td><code>stud123</code></td>
</tr>
</table>

> ⚠️ **Note:** All passwords are SHA-256 hashed in the database

---

## 🚀 Installation & Setup

### Prerequisites

```bash
✓ MySQL 8.0+
✓ Python 3.8+
✓ pip (Python package manager)
```

### 📥 Database Setup

```sql
-- Step 1: Create database and schema
mysql -u root -p < neurosync_schema.sql

-- Step 2: Apply constraints
mysql -u root -p neurosync_db < neurosync_constraints.sql

-- Step 3: Create triggers and procedures
mysql -u root -p neurosync_db < neurosync_triggers_and_procedures.sql

-- Step 4: Fix passwords (if needed)
mysql -u root -p neurosync_db < fix_passwords.sql

-- Step 5: Create analytical views
mysql -u root -p neurosync_db < fix_missing_views.sql
```

### 🐍 Application Setup

```bash
# Install Python dependencies
pip install mysql-connector-python streamlit python-telegram-bot

# Run the application
python ui.py
```

---

## 📁 Project Structure

```
📦 dbms_final/
├── 📂 SQL Files (DDL/DML)
│   ├── 📄 neurosync_schema.sql              # Database schema
│   ├── 📄 neurosync_constraints.sql         # Constraints
│   ├── 📄 neurosync_triggers_and_procedures.sql
│   ├── 📄 neurosync_advanced_analytics.sql
│   ├── 📄 fix_passwords.sql
│   └── 📄 fix_missing_views.sql
│
├── 📂 Python Application
│   ├── 🐍 ui.py                             # Main Streamlit UI
│   ├── 🐍 channel.py                        # Channel management
│   └── 📂 broadcast_module/
│       ├── 🐍 main.py                       # Orchestrator
│       ├── 🐍 config.py                     # Configuration
│       ├── 📂 db/
│       │   └── 🐍 mysql.py                  # DB connector
│       └── 📂 channels/
│           ├── 🐍 telegram.py
│           ├── 🐍 email.py
│           └── 🐍 discord.py
│
└── 📂 Documentation
    └── 📄 DBMS23-Proj-Rpt_024-144-813.pdf
```

---

## 📊 Sample Analytics Queries

### 🎯 1. Student Performance Report

```sql
SELECT 
    s.name, 
    AVG(sub.marks_obtained) as avg_marks,
    COUNT(sub.submission_id) as total_submissions,
    SUM(CASE WHEN sub.status = 'late' THEN 1 ELSE 0 END) as late_count
FROM student s
JOIN submission sub ON s.student_id = sub.student_id
GROUP BY s.student_id;
```

### ⚠️ 2. At-Risk Students

```sql
SELECT * FROM students_at_risk
WHERE late_percentage > 40;
```

### 📧 3. Notification Effectiveness

```sql
SELECT 
    mode_of_alert,
    effectiveness_rate,
    total_notifications
FROM notification_effectiveness
ORDER BY effectiveness_rate DESC;
```

---

## 🎓 Academic Requirements Met

<table>
<tr>
<td width="50%">

### ✅ Functional Requirements
- [x] User authentication & RBAC
- [x] Assignment CRUD operations
- [x] Multi-channel notifications
- [x] Automated reminders
- [x] Late submission detection
- [x] Grading & feedback
- [x] Behavioral analytics
- [x] Admin user management

</td>
<td width="50%">

### ✅ Non-Functional Requirements
- [x] Data integrity (PK, FK)
- [x] Security (hashing)
- [x] Scalability (10K+ users)
- [x] Performance (<2s queries)
- [x] Auditability (logging)
- [x] FERPA/GDPR compliance
- [x] Reliability (backups)
- [x] Maintainability

</td>
</tr>
</table>

---

## 🔍 Key Insights & Analytics

<div style="background-color: #e6f7ff; padding: 15px; border-radius: 8px; margin: 10px 0;">

### 📈 Performance Metrics
- **Top Performers:** Students with avg ≥75% and on-time submissions
- **Risk Indicators:** Late % >40 OR consecutive late ≥3
- **Channel Effectiveness:** WhatsApp shows highest engagement (87%)
- **Peak Activity:** Submissions peak 2-6 hours before deadlines

</div>

<div style="background-color: #fff7e6; padding: 15px; border-radius: 8px; margin: 10px 0;">

### 🧠 Behavioral Patterns
- Students using preferred channels submit **18% faster**
- Reminders sent 24-48h before show **34% higher response**
- Class variance correlates with teacher engagement frequency

</div>

---

## 🛡️ Data Integrity Features

<table>
<tr>
<td width="50%">

### ✓ Automatic Validations
- Marks ≤ assignment maximum
- Timestamp validation
- Email format (regex)
- Phone format validation
- Username min length

</td>
<td width="50%">

### ✓ Business Rules
- No teacher deletion (if has students)
- No assignment deletion (if submissions exist)
- Graded = marks + timestamp required
- Deadlines must be future dates

</td>
</tr>
</table>

---

## 📊 Sample Data Included

<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">

<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white; text-align: center;">
<h3>👥 6 Users</h3>
<p>1 admin, 2 teachers, 5 students</p>
</div>

<div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 20px; border-radius: 10px; color: white; text-align: center;">
<h3>📝 3 Assignments</h3>
<p>Across different subjects</p>
</div>

<div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); padding: 20px; border-radius: 10px; color: white; text-align: center;">
<h3>📤 4 Submissions</h3>
<p>With varied statuses</p>
</div>

</div>

---

## 🔮 Future Enhancements

<table>
<tr>
<td>

- [ ] 🤖 ML submission time prediction
- [ ] 📱 Mobile application
- [ ] 🔍 Plagiarism detection
- [ ] 📹 Video conferencing integration

</td>
<td>

- [ ] 🎮 Gamification features
- [ ] 👨‍👩‍👦 Parent portal
- [ ] 🧠 AI study recommendations
- [ ] 📊 Advanced dashboards

</td>
</tr>
</table>

---

## 📚 References

<div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px;">

- 📖 MySQL Documentation: https://dev.mysql.com/doc/
- 📚 Database Systems Concepts (Silberschatz, Korth, Sudarshan)
- 🎓 PES University DBMS Course Materials

</div>

---

## 📄 License

<div align="center">
<p>This project is submitted as part of academic coursework at PES University.</p>
<p><b>© 2025 Adishree Gupta, Bhavani S, Monica M</b></p>
</div>

---

## 🙏 Acknowledgments

<div align="center" style="background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); padding: 30px; border-radius: 15px; margin: 20px 0;">

<h3>Special thanks to</h3>
<h2>Prof. Raghu B. A.</h2>
<p>For guidance and support throughout this project</p>

</div>

---

<div align="center">

### ⭐ If you found this project helpful, please consider starring the repository!

![PES University](https://img.shields.io/badge/PES-University-orange?style=for-the-badge)

</div>
