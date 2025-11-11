"""
NEUROSYNC: STUDENT ACADEMIC COMMUNICATION AND SUBMISSION SYSTEM
MySQL-Connected Streamlit Application with Multi-Channel Communication
THREE-LAYER PLAGIARISM DETECTION:
1. Traditional Plagiarism (peer + self)
2. AI Content Detection (8 heuristics)
3. Collusion Network Mapping
Team: Adishree, Bhavani & Monica
"""
import streamlit as st
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import hashlib
import json
import pandas as pd
import asyncio
from pathlib import Path
import sys
import os
import re
from collections import defaultdict
import numpy as np

try:
    import redis
    from hashlib import sha256
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    st.warning("Redis not installed. Install with: pip install redis")

broadcast_module_path = Path(__file__).parent / "broadcast_module"
if str(broadcast_module_path) not in sys.path:
    sys.path.insert(0, str(broadcast_module_path))

try:
    from channels.telegram import send_telegram_async
    from channels.discord import send_discord, close_client
    from channels import email as broadcast_email
    from config import TELEGRAM_BOT_TOKEN, DISCORD_BOT_TOKEN, EMAIL_USER
    BROADCAST_AVAILABLE = True
except ImportError:
    BROADCAST_AVAILABLE = False
    print("Warning: broadcast_module not available, using LMS-only mode")

# --- OCR TEXT EXTRACTION UTILITY (Add this once) ---
import os
from pathlib import Path

def extract_clean_text(file_path: str) -> str:
    """
    Extract clean text from a file.
    - For text-based files (txt, code, etc.): reads as UTF-8.
    - For PDFs: tries text extraction first; if fails or empty, runs OCR.
    - Returns clean, stripped string.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return ""

    # Handle plain text or code-like files directly
    if file_path.suffix.lower() in ['.txt', '.py', '.js', '.java', '.cpp', '.c', '.html', '.css', '.md']:
        try:
            return file_path.read_text(encoding='utf-8', errors='ignore').strip()
        except:
            return file_path.read_text(encoding='latin1', errors='ignore').strip()

    # Handle PDFs with fallback to OCR
    if file_path.suffix.lower() == '.pdf':
        try:
            # Try text extraction first
            import PyPDF2
            text = ""
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            if text.strip():
                return text.strip()
        except Exception as e:
            pass  # Fall back to OCR

        # OCR fallback for scanned PDFs
        try:
            from pdf2image import convert_from_path
            import pytesseract
            images = convert_from_path(str(file_path), dpi=150)
            ocr_text = ""
            for img in images:
                ocr_text += pytesseract.image_to_string(img, lang='eng') + "\n"
            return ocr_text.strip()
        except Exception as e:
            return "[OCR not available or failed]"

    # For images (jpg, png, etc.) – optional but useful
    if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
        try:
            import pytesseract
            from PIL import Image
            return pytesseract.image_to_string(Image.open(file_path), lang='eng').strip()
        except:
            return "[Image OCR failed]"

    # Fallback: try reading as text (e.g., .docx not supported here)
    try:
        return file_path.read_text(encoding='utf-8', errors='ignore').strip()
    except:
        return ""

class PlagiarismDetector:
    def __init__(self, redis_host='localhost', redis_port=6379):
        self.redis_available = False
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=False)
                self.redis_client.ping()
                self.redis_available = True
            except:
                pass
    
    def generate_shingles(self, text, k=5):
        shingles = set()
        words = re.findall(r'\w+', text.lower())
        for i in range(len(words) - k + 1):
            shingle = ' '.join(words[i:i+k])
            hashed_shingle = sha256(shingle.encode()).hexdigest()
            shingles.add(hashed_shingle)
        return shingles
    
    def calculate_similarity(self, shingles1, shingles2):
        if not shingles1 or not shingles2:
            return 0.0
        intersection = len(shingles1 & shingles2)
        union = len(shingles1 | shingles2)
        return intersection / union if union > 0 else 0.0
    
    def check_traditional_plagiarism(self, submission_id, content, assignment_id, student_id):
        if not self.redis_available:
            return self._fallback_plagiarism_check(content)
        
        try:
            current_shingles = self.generate_shingles(content)
            key = f"sub:{submission_id}"
            if current_shingles:
                self.redis_client.delete(key)
                self.redis_client.sadd(key, *current_shingles)
            
            query = """
                SELECT s.submission_id, s.student_id, s.file_attachment_path
                FROM submission s
                WHERE s.assignment_id = %s AND s.submission_id != %s
            """
            other_submissions = execute_query(query, (assignment_id, submission_id), fetch=True)
            
            matches = []
            max_similarity = 0.0
            
            for other in other_submissions or []:
                other_key = f"sub:{other['submission_id']}"
                
                if not self.redis_client.exists(other_key):
                    try:
                        with open(other['file_attachment_path'], 'r', encoding='utf-8', errors='ignore') as f:
                            other_content = extract_clean_text(sub['file_attachment_path'])
                        other_shingles = self.generate_shingles(other_content)
                        if other_shingles:
                            self.redis_client.sadd(other_key, *other_shingles)
                    except:
                        continue
                
                if self.redis_client.exists(key) and self.redis_client.exists(other_key):
                    try:
                        inter = len(self.redis_client.sinter(key, other_key))
                        union_size = self.redis_client.scard(key) + self.redis_client.scard(other_key) - inter
                        similarity = inter / union_size if union_size > 0 else 0
                    except:
                        similarity = 0
                    
                    if similarity > 0.3:
                        matches.append({
                            'type': 'peer_submission',
                            'student_id': other['student_id'],
                            'submission_id': other['submission_id'],
                            'similarity': round(similarity * 100, 2)
                        })
                        max_similarity = max(max_similarity, similarity)
            
            self_query = """
                SELECT s.submission_id, s.file_attachment_path, a.title
                FROM submission s
                JOIN assignment a ON s.assignment_id = a.assignment_id
                WHERE s.student_id = %s AND s.assignment_id != %s
                LIMIT 10
            """
            self_submissions = execute_query(self_query, (student_id, assignment_id), fetch=True)
            
            for self_sub in self_submissions or []:
                self_key = f"sub:{self_sub['submission_id']}"
                
                if not self.redis_client.exists(self_key):
                    try:
                        with open(self_sub['file_attachment_path'], 'r', encoding='utf-8', errors='ignore') as f:
                            self_content = f.read()
                        self_shingles = self.generate_shingles(self_content)
                        if self_shingles:
                            self.redis_client.sadd(self_key, *self_shingles)
                    except:
                        continue
                
                if self.redis_client.exists(key) and self.redis_client.exists(self_key):
                    try:
                        inter = len(self.redis_client.sinter(key, self_key))
                        union_size = self.redis_client.scard(key) + self.redis_client.scard(self_key) - inter
                        similarity = inter / union_size if union_size > 0 else 0
                    except:
                        similarity = 0
                    
                    if similarity > 0.3:
                        matches.append({
                            'type': 'self_plagiarism',
                            'assignment': self_sub['title'],
                            'submission_id': self_sub['submission_id'],
                            'similarity': round(similarity * 100, 2)
                        })
                        max_similarity = max(max_similarity, similarity)
            
            if max_similarity >= 0.7:
                risk_level = "HIGH"
            elif max_similarity >= 0.5:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
            
            authorship_score = round((1 - max_similarity) * 100, 2)
            
            return {
                'overall_similarity': round(max_similarity * 100, 2),
                'risk_level': risk_level,
                'matches': matches,
                'authorship_score': authorship_score,
                'word_count': len(content.split())
            }
            
        except Exception as e:
            return self._fallback_plagiarism_check(content)
    
    def _fallback_plagiarism_check(self, content):
        return {
            'overall_similarity': 0.0,
            'risk_level': "UNKNOWN",
            'matches': [],
            'authorship_score': 100.0,
            'word_count': len(content.split()),
            'error': 'Redis unavailable'
        }
    
    def detect_ai_content(self, content):
        sentences = self._split_sentences(content)
        
        if len(sentences) < 3:
            return {
                'ai_probability': 0.0,
                'ai_risk_level': 'LOW',
                'indicators': ['Too short to analyze'],
                'sentence_scores': []
            }
        
        indicators = []
        scores = []
        
        perplexity_score = self._analyze_perplexity(sentences)
        if perplexity_score < 0.3:
            indicators.append("Low perplexity (too predictable)")
            scores.append(0.8)
        else:
            scores.append(0.2)
        
        burstiness_score = self._analyze_burstiness(sentences)
        if burstiness_score < 0.4:
            indicators.append("Uniform sentence lengths (not human-like)")
            scores.append(0.7)
        else:
            scores.append(0.3)
        
        vocab_score = self._analyze_vocabulary(content)
        if vocab_score > 0.7:
            indicators.append("Excessive rare word usage")
            scores.append(0.6)
        else:
            scores.append(0.2)
        
        transition_score = self._detect_transition_overuse(content)
        if transition_score > 0.5:
            indicators.append("Excessive transition words")
            scores.append(0.7)
        else:
            scores.append(0.1)
        
        uniformity_score = self._analyze_sentence_uniformity(sentences)
        if uniformity_score > 0.6:
            indicators.append("Suspiciously similar sentence structures")
            scores.append(0.6)
        else:
            scores.append(0.2)
        
        personal_voice = self._detect_personal_voice(content)
        if personal_voice < 0.3:
            indicators.append("Lacks personal voice")
            scores.append(0.5)
        else:
            scores.append(0.1)
        
        grammar_score = self._analyze_grammar_perfection(content)
        if grammar_score > 0.9:
            indicators.append("Unnaturally perfect grammar")
            scores.append(0.6)
        else:
            scores.append(0.1)
        
        signature_score = self._detect_ai_phrases(content)
        if signature_score > 0.3:
            indicators.append("Contains AI signature phrases")
            scores.append(0.8)
        else:
            scores.append(0.1)
        
        ai_probability = np.mean(scores) if scores else 0.0
        
        sentence_scores = []
        for i, sentence in enumerate(sentences[:10]):
            sent_score = self._score_sentence_ai(sentence)
            sentence_scores.append({
                'sentence_num': i,
                'text': sentence[:100] + '...' if len(sentence) > 100 else sentence,
                'ai_prob': round(sent_score * 100, 2)
            })
        
        if ai_probability >= 0.7:
            risk_level = "HIGH"
        elif ai_probability >= 0.5:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            'ai_probability': round(ai_probability * 100, 2),
            'ai_risk_level': risk_level,
            'indicators': indicators if indicators else ['No significant AI indicators'],
            'sentence_scores': sentence_scores
        }
    
    def _split_sentences(self, text):
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _analyze_perplexity(self, sentences):
        if not sentences:
            return 0.5
        word_counts = [len(s.split()) for s in sentences]
        if not word_counts:
            return 0.5
        variance = np.var(word_counts)
        mean_length = np.mean(word_counts)
        perplexity = variance / (mean_length + 1)
        return min(perplexity / 10, 1.0)
    
    def _analyze_burstiness(self, sentences):
        if len(sentences) < 2:
            return 0.5
        lengths = [len(s.split()) for s in sentences]
        std_dev = np.std(lengths)
        mean_length = np.mean(lengths)
        cv = std_dev / (mean_length + 1)
        return min(cv, 1.0)
    
    def _analyze_vocabulary(self, text):
        words = re.findall(r'\w+', text.lower())
        if len(words) < 10:
            return 0.0
        rare_words = [w for w in words if len(w) > 8]
        rare_ratio = len(rare_words) / len(words)
        return min(rare_ratio * 3, 1.0)
    
    def _detect_transition_overuse(self, text):
        transitions = [
            'furthermore', 'moreover', 'additionally', 'consequently',
            'nevertheless', 'nonetheless', 'therefore', 'thus',
            'hence', 'indeed', 'in conclusion', 'to summarize'
        ]
        text_lower = text.lower()
        count = sum(text_lower.count(t) for t in transitions)
        words = len(text.split())
        ratio = count / (words / 100) if words > 0 else 0
        return min(ratio / 2, 1.0)
    
    def _analyze_sentence_uniformity(self, sentences):
        if len(sentences) < 3:
            return 0.0
        first_words = [s.split()[0].lower() if s.split() else '' for s in sentences]
        unique_ratio = len(set(first_words)) / len(first_words)
        return 1 - unique_ratio
    
    def _detect_personal_voice(self, text):
        personal_markers = ['i ', 'my ', 'me ', 'mine ', "i'm ", "i've ", 'personally', 'in my opinion']
        text_lower = ' ' + text.lower() + ' '
        count = sum(text_lower.count(marker) for marker in personal_markers)
        words = len(text.split())
        ratio = count / (words / 100) if words > 0 else 0
        return min(ratio / 3, 1.0)
    
    def _analyze_grammar_perfection(self, text):
        has_contractions = bool(re.search(r"\w+n't|\w+'ll|\w+'ve", text))
        has_casual_language = bool(re.search(r'\b(gonna|wanna|gotta|kinda|sorta)\b', text, re.I))
        if not has_contractions and not has_casual_language:
            return 0.95
        return 0.3
    
    def _detect_ai_phrases(self, text):
        ai_phrases = [
            "it's worth noting", "it is important to note", "delve into",
            "multifaceted", "plethora", "myriad", "intricate", "nuanced",
            "complex interplay", "it's crucial to understand"
        ]
        text_lower = text.lower()
        matches = sum(1 for phrase in ai_phrases if phrase in text_lower)
        return min(matches / 5, 1.0)
    
    def _score_sentence_ai(self, sentence):
        words = sentence.split()
        if len(words) < 5:
            return 0.0
        score = 0.0
        if any(phrase in sentence.lower() for phrase in ['furthermore', 'moreover', 'additionally']):
            score += 0.3
        if len(words) > 15 and ',' in sentence:
            score += 0.2
        if any(len(w) > 10 for w in words):
            score += 0.2
        if not any(marker in sentence.lower() for marker in ['i ', 'my ', 'me ']):
            score += 0.3
        return min(score, 1.0)
    
    def analyze_collusion_network(self, assignment_id):
        if not self.redis_available:
            return {'error': 'Redis required for network analysis'}
        
        try:
            query = """
                SELECT s.submission_id, s.student_id, s.submission_timestamp,
                       s.file_attachment_path, st.name, st.roll_number
                FROM submission s
                JOIN student st ON s.student_id = st.student_id
                WHERE s.assignment_id = %s
                ORDER BY s.submission_timestamp
            """
            submissions = execute_query(query, (assignment_id,), fetch=True)
            
            if not submissions or len(submissions) < 2:
                return {'error': 'Not enough submissions'}
            
            similarity_matrix = defaultdict(dict)
            submission_data = {}
            
            for sub in submissions:
                submission_data[sub['submission_id']] = {
                    'student_id': sub['student_id'],
                    'student_name': sub['name'],
                    'roll_number': sub['roll_number'],
                    'timestamp': sub['submission_timestamp'],
                    'shingles': None
                }
                
                try:
                    with open(sub['file_attachment_path'], 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    shingles = self.generate_shingles(content)
                    submission_data[sub['submission_id']]['shingles'] = shingles
                    
                    key = f"sub:{sub['submission_id']}"
                    if shingles:
                        self.redis_client.delete(key)
                        self.redis_client.sadd(key, *shingles)
                except Exception as e:
                    pass
            
            connections = []
            sub_ids = list(submission_data.keys())
            
            for i in range(len(sub_ids)):
                for j in range(i + 1, len(sub_ids)):
                    sub1_id = sub_ids[i]
                    sub2_id = sub_ids[j]
                    
                    key1 = f"sub:{sub1_id}"
                    key2 = f"sub:{sub2_id}"
                    
                    if self.redis_client.exists(key1) and self.redis_client.exists(key2):
                        try:
                            inter = len(self.redis_client.sinter(key1, key2))
                            union_size = self.redis_client.scard(key1) + self.redis_client.scard(key2) - inter
                            similarity = inter / union_size if union_size > 0 else 0
                        except:
                            similarity = 0
                        
                        similarity_matrix[sub1_id][sub2_id] = similarity
                        similarity_matrix[sub2_id][sub1_id] = similarity
                        
                        if similarity > 0.7:
                            time1 = submission_data[sub1_id]['timestamp']
                            time2 = submission_data[sub2_id]['timestamp']
                            
                            if time1 < time2:
                                source_id = sub1_id
                                target_id = sub2_id
                            else:
                                source_id = sub2_id
                                target_id = sub1_id
                            
                            connections.append({
                                'source_student': submission_data[source_id]['student_name'],
                                'source_roll': submission_data[source_id]['roll_number'],
                                'source_id': submission_data[source_id]['student_id'],
                                'target_student': submission_data[target_id]['student_name'],
                                'target_roll': submission_data[target_id]['roll_number'],
                                'target_id': submission_data[target_id]['student_id'],
                                'similarity': round(similarity * 100, 2),
                                'time_diff': str(submission_data[target_id]['timestamp'] - submission_data[source_id]['timestamp'])
                            })
            
            clusters = self._detect_clusters(connections)
            hub_students = self._identify_hubs(connections, submission_data)
            
            timeline = [{
                'student_name': data['student_name'],
                'roll_number': data['roll_number'],
                'timestamp': data['timestamp'],
                'submission_id': sub_id
            } for sub_id, data in submission_data.items()]
            timeline.sort(key=lambda x: x['timestamp'])
            
            return {
                'total_submissions': len(submissions),
                'suspicious_connections': len(connections),
                'clusters': clusters,
                'connections': connections,
                'timeline': timeline,
                'hub_students': hub_students
            }
            
        except Exception as e:
            return {'error': f'Network analysis failed: {str(e)}'}
    
    def _detect_clusters(self, connections):
        if not connections:
            return []
        
        graph = defaultdict(set)
        for conn in connections:
            graph[conn['source_id']].add(conn['target_id'])
            graph[conn['target_id']].add(conn['source_id'])
        
        visited = set()
        clusters = []
        
        def dfs(node, cluster):
            visited.add(node)
            cluster.add(node)
            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor, cluster)
        
        for node in graph:
            if node not in visited:
                cluster = set()
                dfs(node, cluster)
                if len(cluster) >= 2:
                    clusters.append(list(cluster))
        
        return clusters
    
    def _identify_hubs(self, connections, submission_data):
        hub_scores = defaultdict(int)
        
        for conn in connections:
            hub_scores[conn['source_id']] += 1
        
        hubs = sorted(hub_scores.items(), key=lambda x: x[1], reverse=True)
        
        return [{
            'student_id': student_id,
            'student_name': next((d['student_name'] for d in submission_data.values() if d['student_id'] == student_id), 'Unknown'),
            'connections_count': score,
            'role': 'LIKELY SOURCE' if score >= 2 else 'Involved'
        } for student_id, score in hubs[:5]]

plagiarism_detector = PlagiarismDetector()



def create_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='neurosync_db',
            user='root',
            password='Sr1*ganesh'
        )
        if connection.is_connected():
            return connection
    except Error as e:
        st.error(f"Error connecting to MySQL: {e}")
        return None

def execute_query(query, params=None, fetch=False, fetchone=False):
    connection = create_connection()
    if connection is None:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params or ())
        
        if fetch:
            result = cursor.fetchone() if fetchone else cursor.fetchall()
            return result
        else:
            connection.commit()
            return cursor.lastrowid
    except Error as e:
        st.error(f"Database error: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def call_procedure(proc_name, params):
    connection = create_connection()
    if connection is None:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.callproc(proc_name, params)
        
        results = []
        for result in cursor.stored_results():
            results.extend(result.fetchall())
        
        connection.commit()
        return results
    except Error as e:
        st.error(f"Procedure error: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def initialize_database():
    connection = create_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plagiarism_results (
                result_id INT PRIMARY KEY AUTO_INCREMENT,
                submission_id INT NOT NULL,
                assignment_id INT NOT NULL,
                student_id INT NOT NULL,
                overall_similarity DECIMAL(5,2) DEFAULT 0.00,
                plagiarism_risk_level ENUM('LOW', 'MEDIUM', 'HIGH', 'UNKNOWN') DEFAULT 'LOW',
                authorship_score DECIMAL(5,2) DEFAULT 100.00,
                peer_matches JSON,
                self_matches JSON,
                ai_probability DECIMAL(5,2) DEFAULT 0.00,
                ai_risk_level ENUM('LOW', 'MEDIUM', 'HIGH') DEFAULT 'LOW',
                ai_indicators JSON,
                sentence_scores JSON,
                word_count INT DEFAULT 0,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (submission_id) REFERENCES submission(submission_id) ON DELETE CASCADE,
                FOREIGN KEY (assignment_id) REFERENCES assignment(assignment_id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
                INDEX idx_submission (submission_id),
                INDEX idx_assignment (assignment_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collusion_networks (
                network_id INT PRIMARY KEY AUTO_INCREMENT,
                assignment_id INT NOT NULL,
                total_submissions INT DEFAULT 0,
                suspicious_connections INT DEFAULT 0,
                clusters JSON,
                connections JSON,
                timeline JSON,
                hub_students JSON,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignment_id) REFERENCES assignment(assignment_id) ON DELETE CASCADE,
                INDEX idx_assignment (assignment_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_communication_accounts (
                account_id INT PRIMARY KEY AUTO_INCREMENT,
                student_id INT NOT NULL,
                platform ENUM('LMS', 'Email', 'Telegram', 'Discord') NOT NULL,
                account_identifier VARCHAR(255),
                account_username VARCHAR(100),
                is_preferred BOOLEAN DEFAULT FALSE,
                account_status ENUM('active', 'inactive') DEFAULT 'inactive',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
                UNIQUE KEY unique_platform_per_student (student_id, platform)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # Add preferred_communication_channel column to student table if it doesn't exist
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'neurosync_db' 
            AND TABLE_NAME = 'student' 
            AND COLUMN_NAME = 'preferred_communication_channel'
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE student 
                ADD COLUMN preferred_communication_channel VARCHAR(100) DEFAULT 'LMS' 
                COMMENT 'Comma-separated list of preferred channels'
            """)
        
        # Check if notification table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = 'neurosync_db' 
            AND TABLE_NAME = 'notification'
        """)
        
        if cursor.fetchone()[0] == 0:
            # Create notification table if it doesn't exist
            cursor.execute("""
                CREATE TABLE notification (
                    notification_id INT PRIMARY KEY AUTO_INCREMENT,
                    student_id INT,
                    assignment_id INT,
                    teacher_id INT,
                    message TEXT NOT NULL,
                    notification_channel ENUM('LMS', 'Email', 'Telegram', 'Discord') DEFAULT 'LMS',
                    notification_status ENUM('sent', 'delivered', 'read', 'failed') DEFAULT 'sent',
                    sent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    read_timestamp TIMESTAMP NULL,
                    FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
                    FOREIGN KEY (assignment_id) REFERENCES assignment(assignment_id) ON DELETE CASCADE,
                    FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id) ON DELETE SET NULL,
                    INDEX idx_student_channel (student_id, notification_channel),
                    INDEX idx_assignment (assignment_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            # Notification table exists - add missing columns one by one
            
            # Add teacher_id column if it doesn't exist
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = 'neurosync_db' 
                AND TABLE_NAME = 'notification' 
                AND COLUMN_NAME = 'teacher_id'
            """)
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE notification 
                    ADD COLUMN teacher_id INT AFTER assignment_id,
                    ADD FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id) ON DELETE SET NULL
                """)
            
            # Add message column if it doesn't exist
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = 'neurosync_db' 
                AND TABLE_NAME = 'notification' 
                AND COLUMN_NAME = 'message'
            """)
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE notification 
                    ADD COLUMN message TEXT NOT NULL AFTER teacher_id
                """)
            
            # Add notification_channel column to notification table if it doesn't exist
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = 'neurosync_db' 
                AND TABLE_NAME = 'notification' 
                AND COLUMN_NAME = 'notification_channel'
            """)
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE notification 
                    ADD COLUMN notification_channel ENUM('LMS', 'Email', 'Telegram', 'Discord') DEFAULT 'LMS'
                    AFTER message
                """)
            
            # Add notification_status column if it doesn't exist
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = 'neurosync_db' 
                AND TABLE_NAME = 'notification' 
                AND COLUMN_NAME = 'notification_status'
            """)
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE notification 
                    ADD COLUMN notification_status ENUM('sent', 'delivered', 'read', 'failed') DEFAULT 'sent'
                    AFTER notification_channel
                """)
            
            # Add sent_timestamp column if it doesn't exist
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = 'neurosync_db' 
                AND TABLE_NAME = 'notification' 
                AND COLUMN_NAME = 'sent_timestamp'
            """)
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE notification 
                    ADD COLUMN sent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    AFTER notification_status
                """)
            
            # Add read_timestamp column if it doesn't exist
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = 'neurosync_db' 
                AND TABLE_NAME = 'notification' 
                AND COLUMN_NAME = 'read_timestamp'
            """)
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE notification 
                    ADD COLUMN read_timestamp TIMESTAMP NULL
                    AFTER sent_timestamp
                """)
            
            # Add indexes if they don't exist
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.STATISTICS 
                WHERE TABLE_SCHEMA = 'neurosync_db' 
                AND TABLE_NAME = 'notification' 
                AND INDEX_NAME = 'idx_student_channel'
            """)
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE notification
                    ADD INDEX idx_student_channel (student_id, notification_channel)
                """)
            
            # Add assignment index if it doesn't exist
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.STATISTICS 
                WHERE TABLE_SCHEMA = 'neurosync_db' 
                AND TABLE_NAME = 'notification' 
                AND INDEX_NAME = 'idx_assignment'
            """)
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE notification
                    ADD INDEX idx_assignment (assignment_id)
                """)
        
        connection.commit()
        return True
        
    except Error as e:
        st.error(f"Error initializing database: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

            
def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_account(username, email, password, role, full_name, additional_info):
    """Create new user account with communication preferences"""
    # Check if username exists
    existing = execute_query(
        "SELECT user_id FROM user WHERE username = %s OR email = %s",
        (username, email), fetch=True, fetchone=True
    )
    
    if existing:
        return False, "Username or email already exists"
    
    try:
        # Insert user
        user_id = execute_query(
            "INSERT INTO user (username, password_hash, email, role, access_level) VALUES (%s, %s, %s, %s, %s)",
            (username, hash_password(password), email, role, 2 if role == 'teacher' else 1)
        )
        
        if not user_id:
            return False, "Failed to create user account"
        
        # Insert role-specific details
        if role == 'teacher':
            execute_query(
                """INSERT INTO teacher (user_id, name, subject_taught, department, email, contact_number, office_location) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (user_id, full_name, additional_info.get('subject', 'Not Specified'), 
                 additional_info.get('department', 'Not Specified'), email, 
                 additional_info.get('contact', ''), additional_info.get('office_location', ''))
            )
        elif role == 'student':
            # Build preferred channels (LMS is always included)
            preferred_channels = ['LMS']
            if additional_info.get('use_email', False):
                preferred_channels.append('Email')
            if additional_info.get('use_telegram', False):
                preferred_channels.append('Telegram')
            if additional_info.get('use_discord', False):
                preferred_channels.append('Discord')
            
            # Insert student with preferred channels
            execute_query(
                """INSERT INTO student (user_id, name, class, roll_number, email, contact_number, 
                   preferred_communication_channel, teacher_id) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, full_name, additional_info.get('class', 'Not Assigned'), 
                 additional_info.get('roll_number', 'TBD'), email, 
                 additional_info.get('contact', ''), ','.join(preferred_channels), 
                 additional_info.get('teacher_id', None))
            )
            
            # Get student_id
            student = execute_query(
                "SELECT student_id FROM student WHERE user_id = %s",
                (user_id,), fetch=True, fetchone=True
            )
            
            if student:
                student_id = student['student_id']
                
                # Store communication account details for ALL platforms
                # Email Account (always store)
                execute_query(
                    """INSERT INTO student_communication_accounts 
                       (student_id, platform, account_identifier, is_preferred, account_status)
                       VALUES (%s, 'Email', %s, %s, %s)""",
                    (student_id, additional_info.get('email_account', email), 
                     additional_info.get('use_email', False), 
                     'active' if additional_info.get('use_email', False) else 'inactive')
                )
                
                # Telegram Account (always store)
                telegram_id = additional_info.get('telegram_id', '')
                execute_query(
                    """INSERT INTO student_communication_accounts 
                       (student_id, platform, account_identifier, is_preferred, account_status)
                       VALUES (%s, 'Telegram', %s, %s, %s)""",
                    (student_id, telegram_id,
                     additional_info.get('use_telegram', False),
                     'active' if (additional_info.get('use_telegram', False) and telegram_id) else 'inactive')
                )
                
                # Discord Account (always store)
                discord_id = additional_info.get('discord_id', '')
                execute_query(
                    """INSERT INTO student_communication_accounts 
                       (student_id, platform, account_identifier, account_username, is_preferred, account_status)
                       VALUES (%s, 'Discord', %s, %s, %s, %s)""",
                    (student_id, discord_id, additional_info.get('discord_username', ''),
                     additional_info.get('use_discord', False),
                     'active' if (additional_info.get('use_discord', False) and discord_id) else 'inactive')
                )
                
                # LMS is always preferred (no separate account needed)
                execute_query(
                    """INSERT INTO student_communication_accounts 
                       (student_id, platform, account_identifier, is_preferred, account_status)
                       VALUES (%s, 'LMS', %s, %s, 'active')""",
                    (student_id, username, True)
                )
        
        return True, "Account created successfully!"
    except Exception as e:
        return False, f"Error creating account: {str(e)}"
        
def admin_dashboard():
    st.markdown('<div class="main-header"><h1>🔧 Admin Dashboard</h1><p>System Management</p></div>', unsafe_allow_html=True)
    
    # Quick stats
    stats = execute_query("""
        SELECT 
            (SELECT COUNT(*) FROM user) as total_users,
            (SELECT COUNT(*) FROM teacher) as total_teachers,
            (SELECT COUNT(*) FROM student) as total_students,
            (SELECT COUNT(*) FROM assignment) as total_assignments,
            (SELECT COUNT(*) FROM submission) as total_submissions
    """, fetch=True, fetchone=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(" Users", stats['total_users'])
    col2.metric(" Teachers", stats['total_teachers'])
    col3.metric(" Students", stats['total_students'])
    col4.metric(" Assignments", stats['total_assignments'])
    col5.metric(" Submissions", stats['total_submissions'])
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([" Teachers", " Students", " Communication", " Analytics", " System Logs"])
    
    with tab1:
        st.markdown("### Add New Teacher")
        with st.form("add_teacher"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Full Name")
                subject = st.text_input("Subject Taught")
                department = st.text_input("Department")
            with col2:
                contact = st.text_input("Contact Number")
                email = st.text_input("Email")
                office = st.text_input("Office Location")
            
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            if st.form_submit_button("➕ Add Teacher"):
                if all([name, subject, department, email, username, password]):
                    user_id = execute_query(
                        "INSERT INTO user (username, password_hash, email, role, access_level) VALUES (%s, %s, %s, 'teacher', 2)",
                        (username, hash_password(password), email)
                    )
                    
                    if user_id:
                        execute_query(
                            """INSERT INTO teacher (user_id, name, subject_taught, department, 
                               contact_number, email, office_location) 
                               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                            (user_id, name, subject, department, contact, email, office)
                        )
                        st.success(f"✅ Teacher {name} added successfully!")
                        st.rerun()
                else:
                    st.error("Please fill all fields")
        
        st.markdown("### Existing Teachers")
        teachers = execute_query("SELECT * FROM teacher", fetch=True)
        if teachers:
            st.dataframe(pd.DataFrame(teachers), use_container_width=True)
    
    with tab2:
        st.markdown("### Add New Student")
        
        teachers = execute_query("SELECT teacher_id, name FROM teacher", fetch=True)
        teacher_options = {t['teacher_id']: t['name'] for t in teachers} if teachers else {}
        
        with st.form("add_student"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Full Name")
                class_name = st.text_input("Class")
                roll = st.text_input("Roll Number")
                email = st.text_input("Email")
            with col2:
                contact = st.text_input("Contact Number")
                teacher_id = st.selectbox("Class Teacher", options=list(teacher_options.keys()), 
                                        format_func=lambda x: teacher_options[x]) if teacher_options else None
            
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            if st.form_submit_button("➕ Add Student"):
                if all([name, class_name, roll, email, username, password, teacher_id]):
                    user_id = execute_query(
                        "INSERT INTO user (username, password_hash, email, role, access_level) VALUES (%s, %s, %s, 'student', 1)",
                        (username, hash_password(password), email)
                    )
                    
                    if user_id:
                        execute_query(
                            """INSERT INTO student (user_id, name, class, roll_number, 
                               contact_number, email, preferred_communication_channel, teacher_id) 
                               VALUES (%s, %s, %s, %s, %s, %s, 'LMS', %s)""",
                            (user_id, name, class_name, roll, contact, email, teacher_id)
                        )
                        st.success(f" Student {name} added successfully!")
                        st.rerun()
                else:
                    st.error("Please fill all fields")
        
        st.markdown("### Existing Students")
        students = execute_query("SELECT * FROM student", fetch=True)
        if students:
            st.dataframe(pd.DataFrame(students), use_container_width=True)
    
    with tab3:
        st.markdown("###  Student Communication Preferences")
        
        # View all student communication accounts
        comm_data = execute_query("""
            SELECT s.name, s.class, s.roll_number, s.preferred_communication_channel,
                   sca.platform, sca.account_identifier, sca.account_username, 
                   sca.is_preferred, sca.account_status
            FROM student s
            LEFT JOIN student_communication_accounts sca ON s.student_id = sca.student_id
            ORDER BY s.class, s.name, sca.platform
        """, fetch=True)
        
        if comm_data:
            df = pd.DataFrame(comm_data)
            
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                selected_class = st.selectbox("Filter by Class", 
                    ["All"] + sorted(df['class'].unique().tolist()))
            with col2:
                selected_platform = st.selectbox("Filter by Platform",
                    ["All", "LMS", "Email", "Telegram", "Discord"])
            
            # Apply filters
            filtered_df = df.copy()
            if selected_class != "All":
                filtered_df = filtered_df[filtered_df['class'] == selected_class]
            if selected_platform != "All":
                filtered_df = filtered_df[filtered_df['platform'] == selected_platform]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Summary statistics
            st.markdown("####  Platform Usage Summary")
            platform_stats = df[df['is_preferred'] == True]['platform'].value_counts()
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(" LMS Users", platform_stats.get('LMS', 0))
            col2.metric(" Email Users", platform_stats.get('Email', 0))
            col3.metric(" Telegram Users", platform_stats.get('Telegram', 0))
            col4.metric(" Discord Users", platform_stats.get('Discord', 0))
    
    with tab4:
        st.markdown("### System Analytics")
        
        st.markdown("####  Top Performing Students")
        top_students = execute_query("SELECT * FROM top_performing_students LIMIT 10", fetch=True)
        if top_students:
            st.dataframe(pd.DataFrame(top_students), use_container_width=True)
        
        st.markdown("####  Students at Risk")
        at_risk = execute_query("SELECT * FROM students_at_risk", fetch=True)
        if at_risk:
            st.dataframe(pd.DataFrame(at_risk), use_container_width=True)
        else:
            st.success("No students at risk!")
    
    with tab5:
        st.markdown("### Recent Actions")
        logs = execute_query("""
            SELECT al.*, u.username 
            FROM action_log al
            LEFT JOIN user u ON al.user_id = u.user_id
            ORDER BY al.timestamp DESC
            LIMIT 50
        """, fetch=True)
        if logs:
            st.dataframe(pd.DataFrame(logs), use_container_width=True)

def login(username, password):
    """Authenticate user"""
    query = """
    SELECT u.user_id, u.username, u.role, u.access_level
    FROM user u
    WHERE u.username = %s AND u.password_hash = %s
    """
    result = execute_query(query, (username, hash_password(password)), fetch=True, fetchone=True)
    
    if result:
        # Update last login
        execute_query("UPDATE user SET last_login = NOW() WHERE user_id = %s", (result['user_id'],))
        return result
    return None

def load_custom_css():
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #2B547E 0%, #4B9CD3 100%);
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .custom-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        margin-bottom: 1rem;
        border-left: 4px solid #4B9CD3;
    }
    
    .risk-high {
        background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        border-left: 4px solid #f44336;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    .risk-medium {
        background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
        border-left: 4px solid #ff9800;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    .risk-low {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        border-left: 4px solid #4caf50;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    .network-card {
        background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
        padding: 1.2rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #9c27b0;
    }
    
    .ai-indicator {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 15px;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 0.2rem;
        background: #ff5722;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)
def render_status_badge(status):
    """Render status badge"""
    badges = {
        'submitted': '<span class="status-badge status-submitted">✓ On Time</span>',
        'late': '<span class="status-badge status-late"> Late</span>',
        'graded': '<span class="status-badge status-graded">✓ Graded</span>',
        'pending': '<span class="status-badge status-pending">⏳ Pending</span>'
    }
    return badges.get(status, '<span class="status-badge">Unknown</span>')

def render_platform_badge(platform):
    """Render communication platform badge"""
    badges = {
        'LMS': '<span class="platform-badge platform-lms"> LMS</span>',
        'Email': '<span class="platform-badge platform-email"> Email</span>',
        'Telegram': '<span class="platform-badge platform-telegram"> Telegram</span>',
        'Discord': '<span class="platform-badge platform-discord"> Discord</span>'
    }
    return badges.get(platform, '')

def send_notifications_to_students(assignment_id, class_name, teacher_id):
    """Send notifications to students based on their preferences"""
    # Get all students in the class with their communication preferences
    students = execute_query("""
        SELECT s.student_id, s.name, s.email, s.preferred_communication_channel,
               sca.platform, sca.account_identifier, sca.account_username, sca.is_preferred
        FROM student s
        LEFT JOIN student_communication_accounts sca ON s.student_id = sca.student_id
        WHERE s.class = %s AND sca.is_preferred = TRUE
        ORDER BY s.student_id
    """, (class_name,), fetch=True)
    
    if not students:
        return
    
    # Get assignment details
    assignment = execute_query(
        "SELECT title, due_date FROM assignment WHERE assignment_id = %s",
        (assignment_id,), fetch=True, fetchone=True
    )
    
    if not assignment:
        return
    
    notification_count = 0
    
    for student in students:
        platform = student['platform']
        
        # Create notification for each preferred platform
        execute_query("""
            INSERT INTO notification 
            (student_id, assignment_id, teacher_id, message, notification_channel, 
             notification_status, sent_timestamp)
            VALUES (%s, %s, %s, %s, %s, 'sent', NOW())
        """, (
            student['student_id'],
            assignment_id,
            teacher_id,
            f"New assignment: {assignment['title']} - Due: {assignment['due_date']}",
            platform
        ))
        notification_count += 1
    
    return notification_count
    
def teacher_dashboard(user):
    st.markdown('<div class="main-header"><h1> Teacher Dashboard</h1></div>', unsafe_allow_html=True)
    
    teacher = execute_query(
        "SELECT * FROM teacher WHERE user_id = %s",
        (user['user_id'],), fetch=True, fetchone=True
    )
    
    if not teacher:
        st.error("Teacher profile not found")
        return
    
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"**Name:** {teacher['name']}")
    col2.markdown(f"**Subject:** {teacher['subject_taught']}")
    col3.markdown(f"**Department:** {teacher['department']}")
    st.markdown('</div>', unsafe_allow_html=True)
    
    stats = execute_query("""
        SELECT 
            COUNT(DISTINCT a.assignment_id) as my_assignments,
            COUNT(s.submission_id) as total_submissions,
            SUM(CASE WHEN s.status IN ('submitted', 'late') THEN 1 ELSE 0 END) as pending_grading
        FROM assignment a
        LEFT JOIN submission s ON a.assignment_id = s.assignment_id
        WHERE a.teacher_id = %s
    """, (teacher['teacher_id'],), fetch=True, fetchone=True)
    
    col1, col2, col3 = st.columns(3)
    col1.metric(" My Assignments", stats['my_assignments'] or 0)
    col2.metric(" Total Submissions", stats['total_submissions'] or 0)
    col3.metric(" Pending Grading", stats['pending_grading'] or 0)
    
    tab1, tab2, tab3 = st.tabs([" Create Assignment", " View Submissions", " Analytics"])
    
    with tab1:
        st.markdown("### Create New Assignment")
        
        with st.form("create_assignment"):
            title = st.text_input("Assignment Title")
            description = st.text_area("Description")
            
            col1, col2 = st.columns(2)
            with col1:
                subject = st.text_input("Subject", value=teacher['subject_taught'])
                class_name = st.text_input("Class")
                max_marks = st.number_input("Maximum Marks", min_value=1, value=100)
            with col2:
                due_date = st.date_input("Due Date", min_value=datetime.now().date())
                deadline_time = st.time_input("Deadline Time")
                submission_mode = st.selectbox("Submission Mode", ["Online", "Offline", "Email"])
            
            instructions = st.text_area("Submission Instructions")
            
            st.info(" Notifications will be sent to ALL students on ALL platforms (LMS, Email, Telegram, Discord). Students will receive notifications on their preferred channels only.")
            
            if st.form_submit_button(" Create Assignment & Send Notifications"):
                if all([title, class_name, subject]):
                    deadline = f"{due_date} {deadline_time}"
                    
                    assignment_id = execute_query("""
                        INSERT INTO assignment 
                        (teacher_id, subject, class, title, description, max_marks, 
                         due_date, submission_mode, submission_deadline, submission_instructions)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (teacher['teacher_id'], subject, class_name, title, description,
                          max_marks, due_date, submission_mode, deadline, instructions))
                    
                    if assignment_id:
                        # ADDED: Smart broadcast to students based on their channel preferences
                        try:
                            # Get students with their communication preferences
                            students = execute_query("""
                                SELECT s.student_id, s.name, sca.platform, sca.account_identifier
                                FROM student s
                                LEFT JOIN student_communication_accounts sca 
                                    ON s.student_id = sca.student_id
                                WHERE s.class = %s AND sca.is_preferred = TRUE AND sca.account_status = 'active'
                            """, (class_name,), fetch=True)
                            
                            message = f"New Assignment: {title}\nSubject: {subject}\nDue: {due_date}\n{description}"
                            notification_count = 0
                            
                            async def send_notifications_async():
                                count = 0
                                failed_channels = []
                                for student in students:
                                    channel = student['platform']
                                    try:
                                        if channel == 'LMS' or not BROADCAST_AVAILABLE:
                                            execute_query("""
                                                INSERT INTO notification 
                                                (student_id, assignment_id, teacher_id, message, 
                                                 notification_channel, notification_status)
                                                VALUES (%s, %s, %s, %s, 'LMS', 'sent')
                                            """, (student['student_id'], assignment_id, teacher['teacher_id'], message))
                                            count += 1
                                        elif channel == 'Email':
                                            if broadcast_email.send_email(student['account_identifier'], f"Assignment: {title}", message):
                                                execute_query("""
                                                    INSERT INTO notification 
                                                    (student_id, assignment_id, teacher_id, message, 
                                                     notification_channel, notification_status)
                                                    VALUES (%s, %s, %s, %s, 'Email', 'delivered')
                                                """, (student['student_id'], assignment_id, teacher['teacher_id'], message))
                                                count += 1
                                            else:
                                                failed_channels.append(f"{student['name']} (Email)")
                                                # Fallback to LMS
                                                execute_query("""
                                                    INSERT INTO notification 
                                                    (student_id, assignment_id, teacher_id, message, 
                                                     notification_channel, notification_status)
                                                    VALUES (%s, %s, %s, %s, 'LMS', 'sent')
                                                """, (student['student_id'], assignment_id, teacher['teacher_id'], message))
                                        elif channel == 'Telegram':
                                            try:
                                                await send_telegram_async(student['account_identifier'], message)
                                                execute_query("""
                                                    INSERT INTO notification 
                                                    (student_id, assignment_id, teacher_id, message, 
                                                     notification_channel, notification_status)
                                                    VALUES (%s, %s, %s, %s, 'Telegram', 'delivered')
                                                """, (student['student_id'], assignment_id, teacher['teacher_id'], message))
                                                count += 1
                                            except Exception as tg_error:
                                                error_msg = str(tg_error)
                                                if "Chat not found" in error_msg or "Forbidden" in error_msg:
                                                    failed_channels.append(f"{student['name']} (Telegram - not started bot)")
                                                else:
                                                    failed_channels.append(f"{student['name']} (Telegram - {error_msg})")
                                                # Fallback to LMS
                                                execute_query("""
                                                    INSERT INTO notification 
                                                    (student_id, assignment_id, teacher_id, message, 
                                                     notification_channel, notification_status)
                                                    VALUES (%s, %s, %s, %s, 'LMS', 'sent')
                                                """, (student['student_id'], assignment_id, teacher['teacher_id'], message))
                                        elif channel == 'Discord':
                                            if await send_discord(student['account_identifier'], message):
                                                execute_query("""
                                                    INSERT INTO notification 
                                                    (student_id, assignment_id, teacher_id, message, 
                                                     notification_channel, notification_status)
                                                    VALUES (%s, %s, %s, %s, 'Discord', 'delivered')
                                                """, (student['student_id'], assignment_id, teacher['teacher_id'], message))
                                                count += 1
                                            else:
                                                failed_channels.append(f"{student['name']} (Discord)")
                                                # Fallback to LMS
                                                execute_query("""
                                                    INSERT INTO notification 
                                                    (student_id, assignment_id, teacher_id, message, 
                                                     notification_channel, notification_status)
                                                    VALUES (%s, %s, %s, %s, 'LMS', 'sent')
                                                """, (student['student_id'], assignment_id, teacher['teacher_id'], message))
                                    except Exception as e:
                                        print(f"Failed to notify student {student['student_id']} on {channel}: {e}")
                                        failed_channels.append(f"{student['name']} ({channel})")
                                        # Fallback to LMS for any error
                                        try:
                                            execute_query("""
                                                INSERT INTO notification 
                                                (student_id, assignment_id, teacher_id, message, 
                                                 notification_channel, notification_status)
                                                VALUES (%s, %s, %s, %s, 'LMS', 'sent')
                                            """, (student['student_id'], assignment_id, teacher['teacher_id'], message))
                                        except:
                                            pass
                                
                                if BROADCAST_AVAILABLE:
                                    try:
                                        await close_client()
                                    except:
                                        pass
                                return count, failed_channels
                            
                            notification_count, failed_list = asyncio.run(send_notifications_async())
                            
                        except Exception as e:
                            print(f"Broadcast module error: {e}")
                            notification_count = 0
                            failed_list = []
                        
                        if failed_list:
                            st.success(f" Assignment created! {notification_count} notifications sent successfully!")
                            st.warning(f" Some notifications failed (sent via LMS instead):\n" + "\n".join(f"• {name}" for name in failed_list))
                            with st.expander(" Telegram Troubleshooting"):
                                st.markdown("""
                                **If Telegram notifications failed:**
                                1. Students MUST start the bot first by searching for it in Telegram
                                2. Click START or send /start to the bot
                                3. Only then can the bot send messages to them
                                4. Ask students to message your bot, then try sending again
                                
                                **All failed notifications were automatically sent via LMS as fallback.**
                                """)
                        else:
                            st.success(f" Assignment created! {notification_count} notifications sent successfully!")
                        st.balloons()
                        st.rerun()
    
    with tab2:
        st.markdown("###  THREE-LAYER PLAGIARISM DETECTION")
        
        assignments = execute_query("""
            SELECT assignment_id, title, class, due_date
            FROM assignment
            WHERE teacher_id = %s
            ORDER BY due_date DESC
        """, (teacher['teacher_id'],), fetch=True)
        
        if assignments:
            assignment_options = {a['assignment_id']: f"{a['title']} ({a['class']})"
                                for a in assignments}
            selected_id = st.selectbox("Select Assignment",
                                      options=list(assignment_options.keys()),
                                      format_func=lambda x: assignment_options[x])
            
            submissions = execute_query("""
                SELECT s.submission_id, st.name, st.roll_number, s.submission_timestamp,
                       s.file_attachment_path, s.status, s.marks_obtained,
                       st.student_id
                FROM submission s
                JOIN student st ON s.student_id = st.student_id
                WHERE s.assignment_id = %s
                ORDER BY s.submission_timestamp
            """, (selected_id,), fetch=True)
            
            if submissions:
                st.markdown(f"**Total Submissions:** {len(submissions)}")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    if st.button(" Run Complete 3-Layer Plagiarism Analysis", type="primary", use_container_width=True):
                        with st.spinner(" Running comprehensive analysis..."):
                            progress_bar = st.progress(0)
                            
                            st.info("**LAYER 1 & 2:** Analyzing individual submissions...")
                            progress_bar.progress(10)
                            
                            for idx, sub in enumerate(submissions):
                                try:
                                    with open(sub['file_attachment_path'], 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read()
                                    
                                    plag_results = plagiarism_detector.check_traditional_plagiarism(
                                        sub['submission_id'], content, selected_id, sub['student_id']
                                    )
                                    
                                    ai_results = plagiarism_detector.detect_ai_content(content)
                                    
                                    execute_query("""
                                        INSERT INTO plagiarism_results
                                        (submission_id, assignment_id, student_id,
                                        overall_similarity, plagiarism_risk_level, authorship_score,
                                        peer_matches, self_matches,
                                        ai_probability, ai_risk_level, ai_indicators, sentence_scores,
                                        word_count)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        ON DUPLICATE KEY UPDATE
                                        overall_similarity = VALUES(overall_similarity),
                                        plagiarism_risk_level = VALUES(plagiarism_risk_level),
                                        authorship_score = VALUES(authorship_score),
                                        ai_probability = VALUES(ai_probability),
                                        ai_risk_level = VALUES(ai_risk_level)
                                    """, (
                                        int(sub['submission_id']), 
                                        int(selected_id), 
                                        int(sub['student_id']),
                                        float(plag_results['overall_similarity']),
                                        plag_results['risk_level'],
                                        float(plag_results['authorship_score']),
                                        json.dumps([m for m in plag_results['matches'] if m['type'] == 'peer_submission']),
                                        json.dumps([m for m in plag_results['matches'] if m['type'] == 'self_plagiarism']),
                                        float(ai_results['ai_probability']),
                                        ai_results['ai_risk_level'],
                                        json.dumps(ai_results['indicators']),
                                        json.dumps(ai_results['sentence_scores']),
                                        int(plag_results['word_count'])
                                    ))
                                    
                                    progress_bar.progress(10 + int(50 * (idx + 1) / len(submissions)))
                                    
                                except Exception as e:
                                    st.warning(f"Could not analyze {sub['name']}: {str(e)}")
                            
                            st.info("**LAYER 3:** Building collusion network map...")
                            progress_bar.progress(70)
                            
                            network_results = plagiarism_detector.analyze_collusion_network(selected_id)
                            
                            if 'error' not in network_results:
                                execute_query("""
                                    INSERT INTO collusion_networks
                                    (assignment_id, total_submissions, suspicious_connections,
                                     clusters, connections, timeline, hub_students)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    ON DUPLICATE KEY UPDATE
                                    total_submissions = VALUES(total_submissions),
                                    suspicious_connections = VALUES(suspicious_connections),
                                    clusters = VALUES(clusters),
                                    connections = VALUES(connections),
                                    hub_students = VALUES(hub_students)
                                """, (
                                    selected_id,
                                    network_results['total_submissions'],
                                    network_results['suspicious_connections'],
                                    json.dumps(network_results['clusters']),
                                    json.dumps(network_results['connections']),
                                    json.dumps(network_results['timeline'], default=str),
                                    json.dumps(network_results['hub_students'])
                                ))
                            
                            progress_bar.progress(100)
                            st.success(" Complete 3-layer analysis finished!")
                            st.balloons()
                            st.rerun()
                
                st.markdown("---")
                
                st.markdown("##  ANALYSIS RESULTS")
                
                plag_data = execute_query("""
                    SELECT pr.*, st.name, st.roll_number
                    FROM plagiarism_results pr
                    JOIN student st ON pr.student_id = st.student_id
                    WHERE pr.assignment_id = %s
                    ORDER BY pr.overall_similarity DESC, pr.ai_probability DESC
                """, (selected_id,), fetch=True)
                
                if plag_data:
                    st.markdown("###  Summary Statistics")
                    
                    high_plag = sum(1 for p in plag_data if p['plagiarism_risk_level'] == 'HIGH')
                    high_ai = sum(1 for p in plag_data if p['ai_risk_level'] == 'HIGH')
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Analyzed", len(plag_data))
                    col2.metric(" High Plagiarism Risk", high_plag)
                    col3.metric(" High AI Risk", high_ai)
                    col4.metric(" Total Alerts", high_plag + high_ai)
                    
                    st.markdown("---")
                    st.markdown("###  LAYER 3: COLLUSION NETWORK ANALYSIS")
                    
                    network_data = execute_query("""
                        SELECT * FROM collusion_networks
                        WHERE assignment_id = %s
                        ORDER BY analyzed_at DESC
                        LIMIT 1
                    """, (selected_id,), fetch=True, fetchone=True)
                    
                    if network_data and network_data['suspicious_connections'] > 0:
                        st.markdown('<div class="network-card">', unsafe_allow_html=True)
                        
                        connections = json.loads(network_data['connections'])
                        clusters = json.loads(network_data['clusters'])
                        hub_students = json.loads(network_data['hub_students'])
                        
                        st.markdown(f"** COLLUSION DETECTED:** {network_data['suspicious_connections']} suspicious connections found")
                        
                        if clusters:
                            st.markdown("####  Identified Cheating Groups:")
                            for idx, cluster in enumerate(clusters, 1):
                                st.markdown(f"**Group {idx}:** {len(cluster)} students involved")
                        
                        if hub_students:
                            st.markdown("####  Hub Students (Likely Sources):")
                            for hub in hub_students:
                                st.markdown(f"- **{hub['student_name']}** ({hub['role']}) - {hub['connections_count']} connections")
                        
                        st.markdown("#### 🔗 Similarity Connections (>70%):")
                        for conn in connections:
                            st.markdown(f"""
                            - **{conn['target_student']} ({conn['target_roll']})** → 
                            **{conn['source_student']} ({conn['source_roll']})**: 
                            **{conn['similarity']}%** similar 
                            (submitted {conn['time_diff']} later)
                            """)
                        
                        with st.expander(" View Network Graph Data"):
                            st.json(connections)
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.success(" No significant collusion patterns detected (all similarities < 70%)")
                    
                    st.markdown("---")
                    st.markdown("###  INDIVIDUAL STUDENT ANALYSIS")
                    
                    for result in plag_data:
                        is_high_risk = (result['plagiarism_risk_level'] == 'HIGH' or 
                                      result['ai_risk_level'] == 'HIGH')
                        
                        risk_class = 'risk-high' if is_high_risk else \
                                   'risk-medium' if (result['plagiarism_risk_level'] == 'MEDIUM' or 
                                                    result['ai_risk_level'] == 'MEDIUM') else 'risk-low'
                        
                        with st.expander(f"{'🚨' if is_high_risk else '✅'} {result['name']} ({result['roll_number']})", 
                                       expanded=is_high_risk):
                            st.markdown(f'<div class="{risk_class}">', unsafe_allow_html=True)
                            
                            st.markdown("####  LAYER 1: Traditional Plagiarism")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Similarity Score", f"{result['overall_similarity']}%")
                            col2.metric("Risk Level", result['plagiarism_risk_level'])
                            col3.metric("Authorship Score", f"{result['authorship_score']}%")
                            
                            peer_matches = json.loads(result['peer_matches']) if result['peer_matches'] else []
                            self_matches = json.loads(result['self_matches']) if result['self_matches'] else []
                            
                            if peer_matches:
                                st.markdown("** Peer Plagiarism Detected:**")
                                for match in peer_matches:
                                    st.markdown(f"- Student ID {match['student_id']}: {match['similarity']}% similar")
                            
                            if self_matches:
                                st.markdown("** Self-Plagiarism Detected:**")
                                for match in self_matches:
                                    st.markdown(f"- Previous assignment '{match['assignment']}': {match['similarity']}% similar")
                            
                            st.markdown("---")
                            st.markdown("####  LAYER 2: AI Content Detection")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("AI Probability", f"{result['ai_probability']}%")
                            col2.metric("AI Risk Level", result['ai_risk_level'])
                            col3.metric("Word Count", result['word_count'])
                            
                            ai_indicators = json.loads(result['ai_indicators']) if result['ai_indicators'] else []
                            if ai_indicators:
                                st.markdown("** AI Indicators Detected:**")
                                for indicator in ai_indicators:
                                    st.markdown(f'<span class="ai-indicator">{indicator}</span>', 
                                              unsafe_allow_html=True)
                            
                            sentence_scores = json.loads(result['sentence_scores']) if result['sentence_scores'] else []
                            if sentence_scores:
                                with st.expander(" Sentence-Level AI Analysis"):
                                    for sent in sentence_scores:
                                        color = "🔴" if sent['ai_prob'] > 70 else "🟡" if sent['ai_prob'] > 50 else "🟢"
                                        st.markdown(f"{color} **Sentence {sent['sentence_num']}** ({sent['ai_prob']}% AI): {sent['text']}")
                            
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            st.markdown("---")
                            st.markdown("#### ️ Grade Submission")
                            
                            sub_data = next((s for s in submissions if s['student_id'] == result['student_id']), None)
                            
                            if sub_data:
                                with st.form(f"grade_{sub_data['submission_id']}"):
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        marks = st.number_input("Marks", 0, 100, 
                                                              value=int(sub_data['marks_obtained'] or 0))
                                    with col2:
                                        remarks = st.text_area("Remarks", value="")
                                    
                                    if st.form_submit_button(" Save Grade"):
                                        execute_query("""
                                            UPDATE submission
                                            SET marks_obtained = %s, grading_remarks = %s, status = 'graded'
                                            WHERE submission_id = %s
                                        """, (marks, remarks, sub_data['submission_id']))
                                        st.success("Grade saved!")
                                        st.rerun()
                else:
                    st.info(" No plagiarism analysis data yet. Click 'Run Complete 3-Layer Analysis' to start.")
            else:
                st.info("No submissions yet for this assignment")
        else:
            st.info("No assignments created yet")

def student_dashboard(user):
    st.markdown('<div class="main-header"><h1> Student Dashboard</h1></div>', unsafe_allow_html=True)
    
    student = execute_query(
        "SELECT * FROM student WHERE user_id = %s",
        (user['user_id'],), fetch=True, fetchone=True
    )
    
    if not student:
        st.error("Student profile not found")
        return
    
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(f"**Name:** {student['name']}")
    col2.markdown(f"**Class:** {student['class']}")
    col3.markdown(f"**Roll:** {student['roll_number']}")
    col4.markdown(f"**Channels:** {student['preferred_communication_channel']}")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Show communication preferences
    comm_accounts = execute_query("""
        SELECT platform, account_identifier, account_username, is_preferred, account_status
        FROM student_communication_accounts
        WHERE student_id = %s
        ORDER BY is_preferred DESC, platform
    """, (student['student_id'],), fetch=True)
    
    if comm_accounts:
        st.markdown('<div class="comm-card">', unsafe_allow_html=True)
        st.markdown("####  My Communication Preferences")
        
        preferred = [acc for acc in comm_accounts if acc['is_preferred']]
        inactive = [acc for acc in comm_accounts if not acc['is_preferred']]
        
        if preferred:
            st.markdown("**Active Channels:**")
            for acc in preferred:
                badge = render_platform_badge(acc['platform'])
                st.markdown(f"{badge} - {acc['account_identifier']}", unsafe_allow_html=True)
        
        if inactive:
            with st.expander("View Inactive Accounts"):
                for acc in inactive:
                    st.markdown(f"**{acc['platform']}:** {acc['account_identifier']} (Inactive)")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    performance = call_procedure('get_student_performance', (student['student_id'],))
    if performance:
        perf = performance[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Submissions", perf['total_submissions'] or 0)
        col2.metric("On Time", perf['on_time_submissions'] or 0)
        col3.metric("Late", perf['late_submissions'] or 0)
        col4.metric("Avg Marks", f"{perf['average_marks']:.1f}" if perf['average_marks'] else "N/A")
    
    tab1, tab2, tab3, tab4 = st.tabs([" My Assignments", " Submit", " My Progress", " Notifications"])
    
    with tab1:
        st.markdown("### My Assignments")
        
        assignments = execute_query("""
            SELECT a.*, 
                   s.submission_id, s.status, s.marks_obtained,
                   DATEDIFF(a.submission_deadline, NOW()) as days_left
            FROM assignment a
            LEFT JOIN submission s ON a.assignment_id = s.assignment_id 
                                   AND s.student_id = %s
            WHERE a.class = %s
            ORDER BY a.due_date
        """, (student['student_id'], student['class']), fetch=True)
        
        if assignments:
            for assignment in assignments:
                st.markdown('<div class="custom-card">', unsafe_allow_html=True)
                
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"###  {assignment['title']}")
                with col2:
                    if assignment['submission_id']:
                        st.markdown(render_status_badge(assignment['status']), unsafe_allow_html=True)
                    else:
                        st.markdown(render_status_badge('pending'), unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                col1.markdown(f"**Subject:** {assignment['subject']}")
                col2.markdown(f"**Due Date:** {assignment['due_date']}")
                col3.markdown(f"**Max Marks:** {assignment['max_marks']}")
                
                if assignment['days_left'] is not None:
                    if assignment['days_left'] > 0:
                        st.info(f" {assignment['days_left']} days remaining")
                    elif assignment['days_left'] == 0:
                        st.warning(" Due today!")
                    else:
                        st.error(" Deadline passed!")
                
                with st.expander("View Details"):
                    st.markdown(f"**Description:** {assignment['description']}")
                    st.markdown(f"**Instructions:** {assignment['submission_instructions']}")
                    st.markdown(f"**Submission Mode:** {assignment['submission_mode']}")
                    
                    if assignment['marks_obtained']:
                        st.success(f"**Your Marks:** {assignment['marks_obtained']}/{assignment['max_marks']}")
                
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No assignments available")
    
    with tab2:
        st.markdown("### Submit Assignment")

        pending = execute_query("""
            SELECT a.assignment_id, a.title, a.submission_deadline
            FROM assignment a
            WHERE a.class = %s
            AND NOT EXISTS (
                SELECT 1 FROM submission s 
                WHERE s.assignment_id = a.assignment_id 
                AND s.student_id = %s
            )
            ORDER BY a.submission_deadline
        """, (student['class'], student['student_id']), fetch=True)

        if pending:
            with st.form("submit_assignment"):
                assignment_options = {a['assignment_id']: f"{a['title']} (Deadline: {a['submission_deadline']})"
                                    for a in pending}
                selected_id = st.selectbox("Select Assignment", 
                                          options=list(assignment_options.keys()),
                                          format_func=lambda x: assignment_options[x])
        
                # File uploader instead of text input
                uploaded_file = st.file_uploader(
                    "Upload Assignment File",
                    type=['pdf', 'doc', 'docx', 'txt', 'zip', 'jpg', 'jpeg', 'png'],
                    help="Supported formats: PDF, DOC, DOCX, TXT, ZIP, JPG, PNG"
                )
        
                if st.form_submit_button(" Submit Assignment"):
                    if uploaded_file:
                        try:
                            # Create uploads directory if it doesn't exist
                            import os
                            upload_dir = "uploads/assignments"
                            os.makedirs(upload_dir, exist_ok=True)
                    
                            # Generate unique filename
                            import time
                            timestamp = int(time.time())
                            file_extension = uploaded_file.name.split('.')[-1]
                            filename = f"{student['student_id']}_{selected_id}_{timestamp}.{file_extension}"
                            file_path = os.path.join(upload_dir, filename)
                    
                            # Save the file
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                    
                            # Insert submission record
                            submission_id = execute_query("""
                                INSERT INTO submission 
                                (assignment_id, student_id, submission_timestamp, file_attachment_path, status)
                                VALUES (%s, %s, NOW(), %s, 'pending')
                            """, (selected_id, student['student_id'], file_path))
                    
                            if submission_id:
                                try:
                                    submission_info = execute_query("""
                                        SELECT a.teacher_id, a.title, s.name as student_name, s.roll_number
                                        FROM assignment a
                                        JOIN student s ON s.student_id = %s
                                        WHERE a.assignment_id = %s
                                    """, (student['student_id'], selected_id), fetch=True, fetchone=True)
                                    
                                    if submission_info:
                                        teacher_id = submission_info['teacher_id']
                                        notification_msg = (
                                            f"New Submission: {submission_info['student_name']} ({submission_info['roll_number']}) "
                                            f"submitted {submission_info['title']}"
                                        )
                                        execute_query("""
                                            INSERT INTO notification 
                                            (student_id, assignment_id, teacher_id, message, 
                                             notification_channel, notification_status)
                                            VALUES (NULL, %s, %s, %s, 'LMS', 'sent')
                                        """, (selected_id, teacher_id, notification_msg))
                                except Exception as e:
                                    print(f"Teacher notification failed: {e}")
                    
                            st.success(f"✅ Assignment submitted successfully! File: {uploaded_file.name}")
                            st.balloons()
                            st.rerun()
                    
                        except Exception as e:
                            st.error(f" File upload failed: {str(e)}")
                    else:
                        st.error("Please upload a file")
        else:
            st.success(" All assignments submitted!")
    
    with tab3:
        st.markdown("### My Progress Analytics")
        
        behavior = execute_query("""
            SELECT * FROM student_behavior_analytics WHERE student_id = %s
        """, (student['student_id'],), fetch=True, fetchone=True)
        
        if behavior:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total", behavior['total_submissions'])
            col2.metric("On Time", behavior['on_time_submissions'])
            col3.metric("Late", behavior['late_submissions'])
            col4.metric("Avg Delay", f"{behavior['average_delay']:.2f} days")
            
            if behavior['total_submissions'] > 0:
                on_time_pct = (behavior['on_time_submissions'] / behavior['total_submissions']) * 100
                
                if on_time_pct >= 80:
                    st.markdown('<div class="success-card">', unsafe_allow_html=True)
                    st.markdown(f"###  Excellent Performance!")
                    st.markdown(f"**{on_time_pct:.1f}%** on-time submission rate")
                    st.progress(on_time_pct / 100)
                    st.markdown('</div>', unsafe_allow_html=True)
                elif on_time_pct >= 50:
                    st.markdown('<div class="info-card">', unsafe_allow_html=True)
                    st.markdown(f"###  Good Performance")
                    st.markdown(f"**{on_time_pct:.1f}%** on-time submission rate")
                    st.progress(on_time_pct / 100)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="warning-card">', unsafe_allow_html=True)
                    st.markdown(f"###  Needs Improvement")
                    st.markdown(f"**{on_time_pct:.1f}%** on-time submission rate")
                    st.progress(on_time_pct / 100)
                    st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown("###  Recent Submissions")
            recent = execute_query("""
                SELECT a.title, s.submission_timestamp, s.status, s.marks_obtained
                FROM submission s
                JOIN assignment a ON s.assignment_id = a.assignment_id
                WHERE s.student_id = %s
                ORDER BY s.submission_timestamp DESC
                LIMIT 10
            """, (student['student_id'],), fetch=True)
            
            if recent:
                for sub in recent:
                    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{sub['title']}**")
                        st.caption(f"Submitted: {sub['submission_timestamp']}")
                    with col2:
                        st.markdown(render_status_badge(sub['status']), unsafe_allow_html=True)
                        if sub['marks_obtained']:
                            st.success(f"Marks: {sub['marks_obtained']}")
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No submission data yet. Submit your first assignment!")
    
    with tab4:
        st.markdown("###  My Notifications")
        
        notifications = execute_query("""
            SELECT n.*, a.title as assignment_title, t.name as teacher_name
            FROM notification n
            LEFT JOIN assignment a ON n.assignment_id = a.assignment_id
            LEFT JOIN teacher t ON n.teacher_id = t.teacher_id
            WHERE n.student_id = %s
            ORDER BY n.sent_timestamp DESC
            LIMIT 50
        """, (student['student_id'],), fetch=True)
        
        if notifications:
            # Group by channel
            channels = {}
            for notif in notifications:
                channel = notif['notification_channel']
                if channel not in channels:
                    channels[channel] = []
                channels[channel].append(notif)
            
            # Display notifications by channel
            for channel, notifs in channels.items():
                with st.expander(f"{render_platform_badge(channel)} {channel} Notifications ({len(notifs)})", expanded=(channel=='LMS')):
                    for notif in notifs:
                        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
                        st.markdown(f"**From:** {notif['teacher_name']}")
                        st.markdown(f"**Assignment:** {notif['assignment_title']}")
                        st.markdown(f"**Message:** {notif['message']}")
                        st.caption(f"📅 {notif['sent_timestamp']}")
                        st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No notifications yet")
            
def main():
    st.set_page_config(
        page_title="NeuroSync - 3-Layer Plagiarism Detection",
        page_icon="🧠",
        layout="wide"
    )
    
    load_custom_css()
    
    if 'db_initialized' not in st.session_state:
        with st.spinner(" Initializing database..."):
            if initialize_database():
                st.session_state.db_initialized = True
            else:
                st.error(" Failed to initialize database")
                st.stop()
    
    if 'user' not in st.session_state:
        st.session_state.user = None
    
    with st.sidebar:
        st.markdown("#  NeuroSync")
        st.markdown("**3-Layer Plagiarism Detection**")
        st.markdown("---")
        
        if st.session_state.user:
            role = st.session_state.user['role']
            
            role_badges = {
                'admin': '<div style="background: linear-gradient(135deg, #9C27B0, #E91E63); color: white; padding: 0.5rem; border-radius: 20px; text-align: center; font-weight: 600;">🔧 ADMIN</div>',
                'teacher': '<div style="background: linear-gradient(135deg, #2B547E, #4B9CD3); color: white; padding: 0.5rem; border-radius: 20px; text-align: center; font-weight: 600;">👨‍🏫 TEACHER</div>',
                'student': '<div style="background: linear-gradient(135deg, #4CAF50, #8BC34A); color: white; padding: 0.5rem; border-radius: 20px; text-align: center; font-weight: 600;">🎓 STUDENT</div>'
            }
            
            st.markdown(role_badges.get(role, ''), unsafe_allow_html=True)
            st.markdown(f"**User:** {st.session_state.user['username']}")
            st.markdown("---")
            
            if st.button(" Logout", use_container_width=True):
                st.session_state.user = None
                st.rerun()
            
            st.markdown("---")
            st.markdown("### 🔍 System Features")
            st.markdown("""
            **3-Layer Detection:**
            - Traditional Plagiarism
            - AI Content (8 heuristics)
            - Collusion Networks
            
            **Analysis Includes:**
            - Peer comparison
            - Self-plagiarism
            - AI probability scoring
            - Network graph mapping
            - Hub student identification
            """)
        else:
            st.info(" Please login to continue")
        
        st.markdown("---")
        st.markdown("###  DBMS Project")
        st.caption("**Team:**")
        st.caption("• Adishree")
        st.caption("• Bhavani")
        st.caption("• Monica")
    
    if not st.session_state.user:
        st.markdown('<div class="main-header"><h1> NeuroSync</h1><p>Advanced Academic Integrity System</p><p>3-Layer Plagiarism Detection</p></div>', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown('<div class="risk-low">', unsafe_allow_html=True)
            st.markdown("###  Layer 1")
            st.markdown("**Traditional Plagiarism**")
            st.markdown("• Peer comparison")
            st.markdown("• Self-plagiarism detection")
            st.markdown("• Similarity scoring")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="risk-medium">', unsafe_allow_html=True)
            st.markdown("###  Layer 2")
            st.markdown("**AI Content Detection**")
            st.markdown("• 8 heuristic analysis")
            st.markdown("• Sentence-level scoring")
            st.markdown("• AI signature phrases")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="risk-high">', unsafe_allow_html=True)
            st.markdown("###  Layer 3")
            st.markdown("**Collusion Networks**")
            st.markdown("• Similarity matrix")
            st.markdown("• Cluster detection")
            st.markdown("• Hub identification")
            st.markdown('</div>', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs([" Login", " Register"])
            
            with tab1:
                with st.form("login_form"):
                    st.markdown("###  Login")
                    username = st.text_input(" Username")
                    password = st.text_input(" Password", type="password")
                    
                    if st.form_submit_button(" Login", use_container_width=True):
                        user = login(username, password)
                        if user:
                            st.session_state.user = user
                            st.success(" Login successful!")
                            st.rerun()
                        else:
                            st.error(" Invalid credentials")
            
            with tab2:
                with st.form("register_form"):
                    st.markdown("###  Create Account")
                    
                    reg_col1, reg_col2 = st.columns(2)
                    with reg_col1:
                        reg_username = st.text_input(" Username*", placeholder="Choose a username")
                        reg_email = st.text_input(" Email*", placeholder="your.email@example.com")
                        reg_password = st.text_input(" Password*", type="password", placeholder="Choose a password")
                    with reg_col2:
                        reg_confirm_password = st.text_input(" Confirm Password*", type="password", placeholder="Re-enter password")
                        reg_full_name = st.text_input(" Full Name*", placeholder="Your full name")
                        reg_role = st.selectbox(" Role*", ["student", "teacher"])
                    
                    st.markdown("#### Additional Information")
                    
                    if reg_role == "teacher":
                        add_col1, add_col2 = st.columns(2)
                        with add_col1:
                            reg_subject = st.text_input(" Subject Taught*", placeholder="e.g., Database Management")
                            reg_department = st.text_input(" Department*", placeholder="e.g., Computer Science")
                        with add_col2:
                            reg_contact = st.text_input(" Contact Number", placeholder="+91-XXXXXXXXXX")
                            reg_office = st.text_input(" Office Location", placeholder="e.g., CS-Block, Room 301")
                    else:
                        add_col1, add_col2 = st.columns(2)
                        with add_col1:
                            reg_class = st.text_input(" Class*", placeholder="e.g., CSE-3A")
                            reg_roll = st.text_input(" Roll Number*", placeholder="e.g., 001")
                        with add_col2:
                            reg_contact = st.text_input(" Contact Number", placeholder="+91-XXXXXXXXXX")
                            teachers = execute_query("SELECT teacher_id, name FROM teacher", fetch=True)
                            if teachers:
                                teacher_options = {0: "Not Assigned"} | {t['teacher_id']: t['name'] for t in teachers}
                                reg_teacher = st.selectbox(" Class Teacher", options=list(teacher_options.keys()), 
                                                          format_func=lambda x: teacher_options[x])
                            else:
                                reg_teacher = 0
                        
                        st.markdown("---")
                        st.markdown("####  Communication Preferences")
                        st.info(" LMS is always enabled. Select additional channels you want to receive notifications on:")
                        
                        st.checkbox(" LMS (Learning Management System)", value=True, disabled=True, 
                                   help="LMS notifications are mandatory")
                        
                        reg_use_email = st.checkbox("📧 Email Notifications")
                        if reg_use_email:
                            reg_email_account = st.text_input("Email Address for Notifications", 
                                                             value=reg_email, 
                                                             placeholder="your.email@example.com",
                                                             help="Email where you'll receive assignment notifications")
                        else:
                            reg_email_account = st.text_input("Email Address (Optional - for future use)", 
                                                             placeholder="your.email@example.com",
                                                             help="Provide email even if not using now")
                        
                        reg_use_telegram = st.checkbox("✈️ Telegram Notifications")
                        if reg_use_telegram:
                            st.warning(" **IMPORTANT: Before enabling Telegram notifications:**\n"
                                   "1. Open Telegram and search for your bot (ask your admin for the bot username)\n"
                                   "2. Click **START** or send **/start** to the bot\n"
                                   "3. Then find your User ID using **@userinfobot**\n"
                                   "4. The bot MUST have an active chat with you to send messages!")
                            st.info(" **How to find your Telegram ID:**\n"
                                   "1. Search for **@userinfobot** in Telegram\n"
                                   "2. Start the bot and send any message\n"
                                   "3. Bot will reply with your numeric User ID (e.g., 1572365453)")
                        
                        reg_telegram_id = st.text_input(
                            "Telegram User ID" + (" *" if reg_use_telegram else " (Optional)"),
                            placeholder="Example: 1572365453",
                            help="Your numeric Telegram user ID (9-10 digits). MUST start the bot first!"
                        )
                        if reg_use_telegram and reg_telegram_id:
                            if not reg_telegram_id.isdigit() or len(reg_telegram_id) < 8:
                                st.warning(" Telegram ID should be 8-10 digits")
                        
                        reg_use_discord = st.checkbox("💬 Discord Notifications")
                        if reg_use_discord:
                            st.info(" **How to find your Discord details:**\n"
                                   "1. Enable Developer Mode: Settings → Advanced → Developer Mode\n"
                                   "2. Right-click your profile picture → Copy User ID\n"
                                   "3. Your username is visible in User Settings → My Account")
                        
                        discord_col1, discord_col2 = st.columns(2)
                        with discord_col1:
                            reg_discord_id = st.text_input(
                                "Discord User ID" + (" *" if reg_use_discord else " (Optional)"),
                                placeholder="Example: 123456789012345678",
                                help="Your 18-digit Discord user ID (enable Developer Mode to copy)"
                            )
                            if reg_use_discord and reg_discord_id:
                                if not reg_discord_id.isdigit() or len(reg_discord_id) < 17:
                                    st.warning(" Discord ID should be 17-19 digits")
                        
                        with discord_col2:
                            reg_discord_username = st.text_input(
                                "Discord Username" + (" *" if reg_use_discord else " (Optional)"),
                                placeholder="Example: johndoe or johndoe#1234",
                                help="Your Discord username (with or without discriminator #1234)"
                            )
                    
                    st.markdown("---")
                    st.caption("*Required fields")
                    
                    if st.form_submit_button(" Create Account", use_container_width=True):
                        if not all([reg_username, reg_email, reg_password, reg_confirm_password, reg_full_name]):
                            st.error(" Please fill all required fields")
                        elif reg_password != reg_confirm_password:
                            st.error(" Passwords do not match")
                        elif len(reg_password) < 6:
                            st.error(" Password must be at least 6 characters")
                        elif '@' not in reg_email:
                            st.error(" Invalid email format")
                        else:
                            additional_info = {}
                            if reg_role == "teacher":
                                if not reg_subject or not reg_department:
                                    st.error(" Please fill all required teacher fields")
                                else:
                                    additional_info = {
                                        'subject': reg_subject,
                                        'department': reg_department,
                                        'contact': reg_contact,
                                        'office_location': reg_office
                                    }
                            else:
                                if not reg_class or not reg_roll:
                                    st.error(" Please fill all required student fields")
                                else:
                                    error_msg = None
                                    
                                    if reg_use_telegram:
                                        if not reg_telegram_id:
                                            error_msg = " Telegram User ID is required when Telegram is selected"
                                        elif not reg_telegram_id.isdigit() or len(reg_telegram_id) < 8:
                                            error_msg = " Invalid Telegram User ID. Must be 8-10 digits (e.g., 1572365453)"
                                    
                                    if reg_use_discord and not error_msg:
                                        if not reg_discord_id:
                                            error_msg = " Discord User ID is required when Discord is selected"
                                        elif not reg_discord_id.isdigit() or len(reg_discord_id) < 17:
                                            error_msg = " Invalid Discord User ID. Must be 17-19 digits (e.g., 123456789012345678)"
                                        elif not reg_discord_username:
                                            error_msg = " Discord Username is required when Discord is selected"
                                    
                                    if reg_use_email and not reg_email_account and not error_msg:
                                        error_msg = " Email address is required when Email is selected"
                                    
                                    if error_msg:
                                        st.error(error_msg)
                                    else:
                                        additional_info = {
                                            'class': reg_class,
                                            'roll_number': reg_roll,
                                            'contact': reg_contact,
                                            'teacher_id': reg_teacher if reg_teacher != 0 else None,
                                            'use_email': reg_use_email,
                                            'email_account': reg_email_account if reg_email_account else reg_email,
                                            'use_telegram': reg_use_telegram,
                                            'telegram_id': reg_telegram_id if reg_telegram_id else '',
                                            'use_discord': reg_use_discord,
                                            'discord_id': reg_discord_id if reg_discord_id else '',
                                            'discord_username': reg_discord_username if reg_discord_username else ''
                                        }
                            
                            if additional_info:
                                success, message = create_account(
                                    reg_username, reg_email, reg_password, 
                                    reg_role, reg_full_name, additional_info
                                )
                                
                                if success:
                                    st.success(f" {message}")
                                    st.balloons()
                                    if reg_role == 'student':
                                        channels = ["LMS"]
                                        if reg_use_email: channels.append("Email")
                                        if reg_use_telegram: channels.append("Telegram")
                                        if reg_use_discord: channels.append("Discord")
                                        st.info(f" You will receive notifications on: {', '.join(channels)}")
                                    st.success(f"You can now login with username: {reg_username}")
                                else:
                                    st.error(f" {message}")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            with st.expander(" Demo Credentials"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**🔧 Admin:**")
                    st.code("Username: root\nPassword: Sr1*ganesh")
                    st.markdown("** Teacher:**")
                    st.code("Username: bhavani\nPassword: bhavani@123")
                
                with col2:
                    st.markdown("** Teacher:**")
                    st.code("Username: monica\nPassword: monica@123")
                    st.markdown("** Student:**")
                    st.code("Username: student1\nPassword: stud123")
    
    else:
        role = st.session_state.user['role']
        
        if role == 'teacher':
            teacher_dashboard(st.session_state.user)
        elif role == 'student':
            student_dashboard(st.session_state.user)
        else:
            st.info("Admin dashboard under construction. Please use teacher or student accounts.")
    
    st.markdown("---")
    st.markdown('<div style="text-align: center; padding: 1rem; color: #666;">', unsafe_allow_html=True)
    st.markdown("**NeuroSync - 3-Layer Plagiarism Detection System** | Team: Adishree, Bhavani & Monica © 2025")
    st.markdown('Powered by: MySQL + Redis + NLP + Graph Theory')
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()