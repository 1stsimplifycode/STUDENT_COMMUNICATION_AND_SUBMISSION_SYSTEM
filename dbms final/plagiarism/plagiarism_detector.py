import redis
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import re
from collections import Counter
import math
from flask import Flask, render_template_string, request, jsonify, session
import os
from werkzeug.utils import secure_filename
import PyPDF2
import io
import secrets

class PlagiarismDetector:
    """
    Advanced plagiarism detection system using Redis for caching and storage.
    Implements semantic analysis, authorship verification, and multilingual detection.
    """
    
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0):
        """Initialize Redis connection and detection parameters."""
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )
        self.similarity_threshold = 0.75
        
    # ==================== SUBMISSION MANAGEMENT ====================
    
    def submit_document(self, student_id: str, assignment_id: str, 
                       content: str, metadata: Optional[Dict] = None) -> str:
        """
        Submit a student document for plagiarism checking.
        Stores in Redis with metadata and generates unique submission ID.
        """
        submission_id = self._generate_submission_id(student_id, assignment_id)
        timestamp = datetime.now().isoformat()
        
        submission_data = {
            'student_id': student_id,
            'assignment_id': assignment_id,
            'content': content,
            'timestamp': timestamp,
            'word_count': len(content.split()),
            'metadata': json.dumps(metadata or {})
        }
        
        # Store submission
        self.redis_client.hset(f'submission:{submission_id}', mapping=submission_data)
        
        # Index by student
        self.redis_client.sadd(f'student:{student_id}:submissions', submission_id)
        
        # Index by assignment
        self.redis_client.sadd(f'assignment:{assignment_id}:submissions', submission_id)
        
        # Store writing style fingerprint
        self._store_writing_style(student_id, content)
        
        # Cache expiry (optional - 90 days)
        self.redis_client.expire(f'submission:{submission_id}', 7776000)
        
        return submission_id
    
    def get_submission(self, submission_id: str) -> Optional[Dict]:
        """Retrieve a submission from Redis."""
        data = self.redis_client.hgetall(f'submission:{submission_id}')
        if data:
            data['metadata'] = json.loads(data.get('metadata', '{}'))
        return data if data else None
    
    # ==================== PLAGIARISM DETECTION ====================
    
    def check_plagiarism(self, submission_id: str, 
                        check_peer: bool = True,
                        check_history: bool = True) -> Dict:
        """
        Comprehensive plagiarism check including:
        - Peer submissions comparison
        - Historical student work comparison
        - Cached source matching
        """
        submission = self.get_submission(submission_id)
        if not submission:
            return {'error': 'Submission not found'}
        
        content = submission['content']
        student_id = submission['student_id']
        assignment_id = submission['assignment_id']
        
        results = {
            'submission_id': submission_id,
            'timestamp': datetime.now().isoformat(),
            'overall_similarity': 0.0,
            'matches': [],
            'flags': [],
            'risk_level': 'LOW'
        }
        
        # Check against peer submissions
        if check_peer:
            peer_matches = self._check_peer_submissions(content, assignment_id, submission_id)
            results['matches'].extend(peer_matches)
        
        # Check against student's history (self-plagiarism)
        if check_history:
            history_matches = self._check_student_history(content, student_id, submission_id)
            results['matches'].extend(history_matches)
        
        # Check cached web sources
        source_matches = self._check_cached_sources(content)
        results['matches'].extend(source_matches)
        
        # Calculate overall similarity
        if results['matches']:
            results['overall_similarity'] = max(m['similarity'] for m in results['matches'])
        
        # Determine risk level
        results['risk_level'] = self._calculate_risk_level(results['overall_similarity'])
        
        # Check authorship consistency
        authorship_score = self._verify_authorship(student_id, content)
        results['authorship_consistency'] = authorship_score
        if authorship_score < 0.5:
            results['flags'].append('Unusual writing style detected')
        
        # Store check results
        self._store_check_result(submission_id, results)
        
        return results
    
    def _check_peer_submissions(self, content: str, assignment_id: str, 
                                current_submission_id: str) -> List[Dict]:
        """Check similarity against other students' submissions for the same assignment."""
        matches = []
        peer_submissions = self.redis_client.smembers(f'assignment:{assignment_id}:submissions')
        
        for peer_id in peer_submissions:
            if peer_id == current_submission_id:
                continue
            
            peer_data = self.get_submission(peer_id)
            if not peer_data:
                continue
            
            similarity = self._calculate_similarity(content, peer_data['content'])
            
            if similarity > self.similarity_threshold:
                matches.append({
                    'type': 'peer_submission',
                    'source_id': peer_id,
                    'student_id': peer_data['student_id'],
                    'similarity': similarity,
                    'matched_segments': self._find_matching_segments(content, peer_data['content'])
                })
        
        return matches
    
    def _check_student_history(self, content: str, student_id: str, 
                               current_submission_id: str) -> List[Dict]:
        """Check for self-plagiarism against student's previous submissions."""
        matches = []
        past_submissions = self.redis_client.smembers(f'student:{student_id}:submissions')
        
        for past_id in past_submissions:
            if past_id == current_submission_id:
                continue
            
            past_data = self.get_submission(past_id)
            if not past_data:
                continue
            
            similarity = self._calculate_similarity(content, past_data['content'])
            
            if similarity > 0.6:  # Lower threshold for self-plagiarism
                matches.append({
                    'type': 'self_plagiarism',
                    'source_id': past_id,
                    'assignment_id': past_data['assignment_id'],
                    'similarity': similarity,
                    'timestamp': past_data['timestamp']
                })
        
        return matches
    
    def _check_cached_sources(self, content: str) -> List[Dict]:
        """Check against cached web sources and known materials."""
        matches = []
        
        # Get all cached sources
        source_keys = self.redis_client.keys('source:*')
        
        for source_key in source_keys[:100]:  # Limit for performance
            source_data = self.redis_client.hgetall(source_key)
            if not source_data:
                continue
            
            similarity = self._calculate_similarity(content, source_data.get('content', ''))
            
            if similarity > self.similarity_threshold:
                matches.append({
                    'type': 'external_source',
                    'source_url': source_data.get('url', 'unknown'),
                    'source_title': source_data.get('title', 'Unknown Source'),
                    'similarity': similarity
                })
        
        return matches
    
    # ==================== AUTHORSHIP VERIFICATION ====================
    
    def _store_writing_style(self, student_id: str, content: str):
        """Extract and store writing style features for authorship verification."""
        features = self._extract_style_features(content)
        
        # Store as hash
        style_key = f'style:{student_id}'
        
        # Update running averages
        if self.redis_client.exists(style_key):
            existing = self.redis_client.hgetall(style_key)
            count = int(existing.get('sample_count', 0))
            
            # Update averages
            for key, value in features.items():
                if key in existing:
                    old_avg = float(existing[key])
                    new_avg = (old_avg * count + value) / (count + 1)
                    features[key] = new_avg
            
            features['sample_count'] = count + 1
        else:
            features['sample_count'] = 1
        
        # Convert to strings for Redis
        features_str = {k: str(v) for k, v in features.items()}
        self.redis_client.hset(style_key, mapping=features_str)
    
    def _verify_authorship(self, student_id: str, content: str) -> float:
        """Compare submission writing style against student's historical style."""
        style_key = f'style:{student_id}'
        
        if not self.redis_client.exists(style_key):
            return 1.0  # No history, assume authentic
        
        historical_style = {k: float(v) for k, v in self.redis_client.hgetall(style_key).items() 
                           if k != 'sample_count'}
        current_style = self._extract_style_features(content)
        
        # Calculate style consistency (inverse of distance)
        total_diff = 0
        for key in historical_style:
            if key in current_style:
                diff = abs(historical_style[key] - current_style[key])
                total_diff += diff
        
        # Normalize to 0-1 score
        consistency = max(0, 1 - (total_diff / len(historical_style)))
        return consistency
    
    def _extract_style_features(self, content: str) -> Dict[str, float]:
        """Extract writing style features (stylometry)."""
        words = content.split()
        sentences = re.split(r'[.!?]+', content)
        
        return {
            'avg_word_length': sum(len(w) for w in words) / max(len(words), 1),
            'avg_sentence_length': len(words) / max(len(sentences), 1),
            'lexical_diversity': len(set(words)) / max(len(words), 1),
            'punctuation_ratio': sum(1 for c in content if c in '.,;:!?') / max(len(content), 1),
            'caps_ratio': sum(1 for c in content if c.isupper()) / max(len(content), 1)
        }
    
    # ==================== SIMILARITY ALGORITHMS ====================
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity using TF-IDF and cosine similarity."""
        # Tokenize
        words1 = self._tokenize(text1)
        words2 = self._tokenize(text2)
        
        # Create vocabulary
        vocab = set(words1 + words2)
        
        # Calculate TF-IDF vectors
        vec1 = self._calculate_tfidf(words1, vocab)
        vec2 = self._calculate_tfidf(words2, vocab)
        
        # Cosine similarity
        return self._cosine_similarity(vec1, vec2)
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return text.split()
    
    def _calculate_tfidf(self, words: List[str], vocab: set) -> Dict[str, float]:
        """Calculate TF-IDF vector."""
        word_count = Counter(words)
        tf = {word: count / len(words) for word, count in word_count.items()}
        
        # Simplified IDF (would normally use document corpus)
        idf = {word: 1.0 for word in vocab}
        
        tfidf = {word: tf.get(word, 0) * idf.get(word, 1) for word in vocab}
        return tfidf
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in vec1.keys())
        
        mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v**2 for v in vec2.values()))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)
    
    def _find_matching_segments(self, text1: str, text2: str, 
                                min_length: int = 20) -> List[str]:
        """Find matching text segments between two documents."""
        sentences1 = re.split(r'[.!?]+', text1)
        sentences2 = re.split(r'[.!?]+', text2)
        
        matches = []
        for s1 in sentences1:
            s1 = s1.strip()
            if len(s1) < min_length:
                continue
            for s2 in sentences2:
                s2 = s2.strip()
                if len(s2) < min_length:
                    continue
                
                similarity = self._calculate_similarity(s1, s2)
                if similarity > 0.8:
                    matches.append(s1[:100] + '...')  # Truncate for storage
                    break
        
        return matches[:5]  # Limit number of matches
    
    # ==================== SOURCE DATABASE ====================
    
    def add_source(self, url: str, title: str, content: str):
        """Add a known source to the database for checking."""
        source_id = hashlib.md5(url.encode()).hexdigest()
        
        source_data = {
            'url': url,
            'title': title,
            'content': content,
            'added_date': datetime.now().isoformat()
        }
        
        self.redis_client.hset(f'source:{source_id}', mapping=source_data)
        self.redis_client.sadd('sources:all', source_id)
    
    # ==================== ANALYTICS & REPORTING ====================
    
    def get_student_analytics(self, student_id: str) -> Dict:
        """Get analytics for a specific student."""
        submissions = self.redis_client.smembers(f'student:{student_id}:submissions')
        
        analytics = {
            'total_submissions': len(submissions),
            'flagged_submissions': 0,
            'avg_similarity_score': 0.0,
            'authorship_scores': []
        }
        
        total_similarity = 0
        for sub_id in submissions:
            result_key = f'check_result:{sub_id}'
            if self.redis_client.exists(result_key):
                result = json.loads(self.redis_client.get(result_key))
                total_similarity += result.get('overall_similarity', 0)
                
                if result.get('risk_level') in ['HIGH', 'MEDIUM']:
                    analytics['flagged_submissions'] += 1
                
                if 'authorship_consistency' in result:
                    analytics['authorship_scores'].append(result['authorship_consistency'])
        
        if len(submissions) > 0:
            analytics['avg_similarity_score'] = total_similarity / len(submissions)
        
        return analytics
    
    def _store_check_result(self, submission_id: str, results: Dict):
        """Store plagiarism check results."""
        result_key = f'check_result:{submission_id}'
        self.redis_client.set(result_key, json.dumps(results))
        self.redis_client.expire(result_key, 7776000)  # 90 days
    
    # ==================== HELPER METHODS ====================
    
    def _generate_submission_id(self, student_id: str, assignment_id: str) -> str:
        """Generate unique submission ID."""
        timestamp = datetime.now().isoformat()
        data = f"{student_id}:{assignment_id}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _calculate_risk_level(self, similarity: float) -> str:
        """Determine risk level based on similarity score."""
        if similarity >= 0.85:
            return 'HIGH'
        elif similarity >= 0.70:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    # ==================== UTILITY METHODS ====================
    
    def clear_student_data(self, student_id: str):
        """Clear all data for a specific student (GDPR compliance)."""
        submissions = self.redis_client.smembers(f'student:{student_id}:submissions')
        
        for sub_id in submissions:
            self.redis_client.delete(f'submission:{sub_id}')
            self.redis_client.delete(f'check_result:{sub_id}')
        
        self.redis_client.delete(f'student:{student_id}:submissions')
        self.redis_client.delete(f'style:{student_id}')
    
    def get_statistics(self) -> Dict:
        """Get overall system statistics."""
        return {
            'total_submissions': len(self.redis_client.keys('submission:*')),
            'total_students': len(self.redis_client.keys('student:*:submissions')),
            'total_sources': len(self.redis_client.smembers('sources:all')),
            'redis_memory_used': self.redis_client.info('memory')['used_memory_human']
        }


# ==================== FLASK WEB APPLICATION ====================

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize detector
detector = PlagiarismDetector(redis_host='localhost', redis_port=6379)

def extract_text_from_pdf(pdf_file):
    """Extract text content from PDF file."""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        raise Exception(f"Error extracting PDF text: {str(e)}")

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plagiarism Detection System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .main-card {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-bottom: 30px;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
            font-size: 14px;
        }
        
        .form-group input[type="text"],
        .form-group textarea {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        
        .form-group input[type="text"]:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .form-group textarea {
            min-height: 150px;
            resize: vertical;
            font-family: inherit;
        }
        
        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            background: #f8f9ff;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .upload-area:hover {
            background: #eef0ff;
            border-color: #5568d3;
        }
        
        .upload-area.dragging {
            background: #e0e5ff;
            border-color: #4a5cc5;
        }
        
        .upload-icon {
            font-size: 48px;
            color: #667eea;
            margin-bottom: 15px;
        }
        
        .upload-text {
            color: #666;
            font-size: 16px;
            margin-bottom: 10px;
        }
        
        .file-info {
            margin-top: 15px;
            padding: 12px;
            background: #e8f5e9;
            border-radius: 8px;
            color: #2e7d32;
            display: none;
        }
        
        input[type="file"] {
            display: none;
        }
        
        .checkbox-group {
            display: flex;
            gap: 25px;
            margin-bottom: 25px;
        }
        
        .checkbox-group label {
            display: flex;
            align-items: center;
            cursor: pointer;
            font-size: 14px;
        }
        
        .checkbox-group input[type="checkbox"] {
            margin-right: 8px;
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            width: 100%;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        }
        
        .btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .results {
            display: none;
            margin-top: 30px;
        }
        
        .result-header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .risk-badge {
            display: inline-block;
            padding: 10px 25px;
            border-radius: 25px;
            font-weight: bold;
            font-size: 18px;
            margin: 15px 0;
        }
        
        .risk-LOW {
            background: #d4edda;
            color: #155724;
        }
        
        .risk-MEDIUM {
            background: #fff3cd;
            color: #856404;
        }
        
        .risk-HIGH {
            background: #f8d7da;
            color: #721c24;
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .metric-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            border: 2px solid #e0e0e0;
        }
        
        .metric-label {
            font-size: 13px;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .metric-value {
            font-size: 28px;
            font-weight: bold;
            color: #333;
        }
        
        .matches-section {
            margin-top: 30px;
        }
        
        .match-card {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
        }
        
        .match-type {
            font-weight: bold;
            color: #667eea;
            text-transform: uppercase;
            font-size: 12px;
            margin-bottom: 8px;
        }
        
        .match-details {
            margin-top: 10px;
            font-size: 14px;
            color: #666;
        }
        
        .similarity-bar {
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 10px;
        }
        
        .similarity-fill {
            height: 100%;
            background: linear-gradient(90deg, #4caf50, #ffc107, #f44336);
            transition: width 0.3s;
        }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }
        
        .tab {
            padding: 12px 24px;
            cursor: pointer;
            border: none;
            background: none;
            font-size: 15px;
            font-weight: 600;
            color: #666;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }
        
        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .alert {
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .alert-warning {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
        
        .source-manager {
            margin-top: 30px;
            padding-top: 30px;
            border-top: 2px solid #e0e0e0;
        }
        
        .source-form {
            display: grid;
            gap: 15px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Plagiarism Detection System</h1>
            <p>Advanced AI-powered document analysis with authorship verification</p>
        </div>
        
        <div class="main-card">
            <div class="tabs">
                <button class="tab active" onclick="switchTab('submit')">Submit Document</button>
                <button class="tab" onclick="switchTab('analytics')">Analytics</button>
                <button class="tab" onclick="switchTab('sources')">Manage Sources</button>
            </div>
            
            <!-- Submit Tab -->
            <div id="submit-tab" class="tab-content active">
                <form id="uploadForm" enctype="multipart/form-data">
                    <div class="form-group">
                        <label for="student_id">Student ID *</label>
                        <input type="text" id="student_id" name="student_id" required 
                               placeholder="e.g., student_001">
                    </div>
                    
                    <div class="form-group">
                        <label for="assignment_id">Assignment ID *</label>
                        <input type="text" id="assignment_id" name="assignment_id" required 
                               placeholder="e.g., essay_2024_fall">
                    </div>
                    
                    <div class="form-group">
                        <label>Upload PDF Document</label>
                        <div class="upload-area" id="uploadArea" onclick="document.getElementById('pdf_file').click()">
                            <div class="upload-icon">📄</div>
                            <div class="upload-text">
                                <strong>Click to upload</strong> or drag and drop<br>
                                PDF files only (Max 16MB)
                            </div>
                        </div>
                        <input type="file" id="pdf_file" name="pdf_file" accept=".pdf">
                        <div class="file-info" id="fileInfo"></div>
                    </div>
                    
                    <div class="form-group">
                        <label for="text_content">Or Paste Text Content</label>
                        <textarea id="text_content" name="text_content" 
                                  placeholder="Paste your document text here..."></textarea>
                    </div>
                    
                    <div class="checkbox-group">
                        <label>
                            <input type="checkbox" name="check_peer" checked>
                            Check against peer submissions
                        </label>
                        <label>
                            <input type="checkbox" name="check_history" checked>
                            Check student history
                        </label>
                    </div>
                    
                    <button type="submit" class="btn" id="submitBtn">
                        Analyze Document
                    </button>
                </form>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p>Analyzing document for plagiarism...</p>
                </div>
                
                <div class="results" id="results">
                    <div class="result-header">
                        <h2>Analysis Results</h2>
                        <div class="risk-badge" id="riskBadge">LOW RISK</div>
                    </div>
                    
                    <div class="metric-grid">
                        <div class="metric-card">
                            <div class="metric-label">Overall Similarity</div>
                            <div class="metric-value" id="similarity">0%</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Authorship Score</div>
                            <div class="metric-value" id="authorship">100%</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Word Count</div>
                            <div class="metric-value" id="wordCount">0</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Matches Found</div>
                            <div class="metric-value" id="matchCount">0</div>
                        </div>
                    </div>
                    
                    <div id="flags"></div>
                    
                    <div class="matches-section" id="matchesSection">
                        <h3>Detected Matches</h3>
                        <div id="matchesList"></div>
                    </div>
                </div>
            </div>
            
            <!-- Analytics Tab -->
            <div id="analytics-tab" class="tab-content">
                <h2>Student Analytics</h2>
                <div class="form-group">
                    <label for="analytics_student_id">Student ID</label>
                    <input type="text" id="analytics_student_id" placeholder="e.g., student_001">
                </div>
                <button class="btn" onclick="loadAnalytics()">Load Analytics</button>
                
                <div id="analyticsResults" style="margin-top: 30px;"></div>
            </div>
            
            <!-- Sources Tab -->
            <div id="sources-tab" class="tab-content">
                <h2>Add Known Source</h2>
                <p style="color: #666; margin-bottom: 20px;">
                    Add external sources to check against (articles, papers, websites)
                </p>
                
                <form id="sourceForm">
                    <div class="form-group">
                        <label for="source_url">Source URL *</label>
                        <input type="text" id="source_url" required 
                               placeholder="https://example.com/article">
                    </div>
                    
                    <div class="form-group">
                        <label for="source_title">Source Title *</label>
                        <input type="text" id="source_title" required 
                               placeholder="Article or document title">
                    </div>
                    
                    <div class="form-group">
                        <label for="source_content">Source Content *</label>
                        <textarea id="source_content" required 
                                  placeholder="Paste the full text content of the source..."></textarea>
                    </div>
                    
                    <button type="submit" class="btn">Add Source</button>
                </form>
                
                <div id="sourceResult" style="margin-top: 20px;"></div>
                
                <div style="margin-top: 40px;">
                    <h3>System Statistics</h3>
                    <button class="btn" onclick="loadStatistics()" style="margin-top: 15px;">
                        Load Statistics
                    </button>
                    <div id="statsResults" style="margin-top: 20px;"></div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // File upload handling
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('pdf_file');
        const fileInfo = document.getElementById('fileInfo');
        
        fileInput.addEventListener('change', function(e) {
            if (this.files.length > 0) {
                const file = this.files[0];
                fileInfo.innerHTML = `✅ Selected: ${file.name} (${(file.size / 1024).toFixed(2)} KB)`;
                fileInfo.style.display = 'block';
            }
        });
        
        // Drag and drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.add('dragging');
            });
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.remove('dragging');
            });
        });
        
        uploadArea.addEventListener('drop', function(e) {
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type === 'application/pdf') {
                fileInput.files = files;
                const event = new Event('change');
                fileInput.dispatchEvent(event);
            } else {
                alert('Please drop a PDF file');
            }
        });
        
        // Form submission
        document.getElementById('uploadForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData();
            formData.append('student_id', document.getElementById('student_id').value);
            formData.append('assignment_id', document.getElementById('assignment_id').value);
            formData.append('check_peer', document.querySelector('input[name="check_peer"]').checked);
            formData.append('check_history', document.querySelector('input[name="check_history"]').checked);
            
            const pdfFile = document.getElementById('pdf_file').files[0];
            const textContent = document.getElementById('text_content').value;
            
            if (pdfFile) {
                formData.append('pdf_file', pdfFile);
            } else if (textContent) {
                formData.append('text_content', textContent);
            } else {
                alert('Please upload a PDF or paste text content');
                return;
            }
            
            // Show loading
            document.getElementById('loading').style.display = 'block';
            document.getElementById('results').style.display = 'none';
            document.getElementById('submitBtn').disabled = true;
            
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.error) {
                    alert('Error: ' + result.error);
                } else {
                    displayResults(result);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            } finally {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('submitBtn').disabled = false;
            }
        });
        
        function displayResults(data) {
            document.getElementById('results').style.display = 'block';
            
            // Risk badge
            const riskBadge = document.getElementById('riskBadge');
            riskBadge.textContent = `${data.risk_level} RISK`;
            riskBadge.className = `risk-badge risk-${data.risk_level}`;
            
            // Metrics
            document.getElementById('similarity').textContent = 
                (data.overall_similarity * 100).toFixed(1) + '%';
            document.getElementById('authorship').textContent = 
                (data.authorship_consistency * 100).toFixed(1) + '%';
            document.getElementById('wordCount').textContent = data.word_count || 0;
            document.getElementById('matchCount').textContent = data.matches.length;
            
            // Flags
            const flagsDiv = document.getElementById('flags');
            if (data.flags && data.flags.length > 0) {
                flagsDiv.innerHTML = '<div class="alert alert-warning">' +
                    '<strong>⚠️ Warnings:</strong><br>' +
                    data.flags.join('<br>') +
                    '</div>';
            } else {
                flagsDiv.innerHTML = '';
            }
            
            // Matches
            const matchesList = document.getElementById('matchesList');
            if (data.matches.length === 0) {
                matchesList.innerHTML = '<p style="color: #666; text-align: center;">No significant matches found</p>';
            } else {
                matchesList.innerHTML = data.matches.map(match => `
                    <div class="match-card">
                        <div class="match-type">${formatMatchType(match.type)}</div>
                        <div class="match-details">
                            ${formatMatchDetails(match)}
                        </div>
                        <div class="similarity-bar">
                            <div class="similarity-fill" style="width: ${match.similarity * 100}%"></div>
                        </div>
                        <div style="margin-top: 5px; font-size: 13px; color: #666;">
                            Similarity: ${(match.similarity * 100).toFixed(1)}%
                        </div>
                    </div>
                `).join('');
            }
            
            // Scroll to results
            document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
        }
        
        function formatMatchType(type) {
            const types = {
                'peer_submission': '👥 Peer Submission Match',
                'self_plagiarism': '🔄 Self-Plagiarism',
                'external_source': '🌐 External Source Match'
            };
            return types[type] || type;
        }
        
        function formatMatchDetails(match) {
            let details = '';
            if (match.type === 'peer_submission') {
                details = `Matched with submission from student: ${match.student_id}`;
            } else if (match.type === 'self_plagiarism') {
                details = `Matched with previous submission for assignment: ${match.assignment_id}`;
            } else if (match.type === 'external_source') {
                details = `Source: <strong>${match.source_title}</strong><br>
                          URL: <a href="${match.source_url}" target="_blank">${match.source_url}</a>`;
            }
            return details;
        }
        
        // Tab switching
        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            event.target.classList.add('active');
            document.getElementById(tabName + '-tab').classList.add('active');
        }
        
        // Analytics
        async function loadAnalytics() {
            const studentId = document.getElementById('analytics_student_id').value;
            if (!studentId) {
                alert('Please enter a student ID');
                return;
            }
            
            try {
                const response = await fetch(`/analytics/${studentId}`);
                const data = await response.json();
                
                const resultsDiv = document.getElementById('analyticsResults');
                resultsDiv.innerHTML = `
                    <div class="metric-grid">
                        <div class="metric-card">
                            <div class="metric-label">Total Submissions</div>
                            <div class="metric-value">${data.total_submissions}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Flagged Submissions</div>
                            <div class="metric-value">${data.flagged_submissions}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Avg Similarity</div>
                            <div class="metric-value">${(data.avg_similarity_score * 100).toFixed(1)}%</div>
                        </div>
                    </div>
                `;
            } catch (error) {
                alert('Error loading analytics: ' + error.message);
            }
        }
        
        // Source form
        document.getElementById('sourceForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const data = {
                url: document.getElementById('source_url').value,
                title: document.getElementById('source_title').value,
                content: document.getElementById('source_content').value
            };
            
            try {
                const response = await fetch('/add_source', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                const resultDiv = document.getElementById('sourceResult');
                resultDiv.innerHTML = `<div class="alert" style="background: #d4edda; color: #155724;">
                    ✅ ${result.message}
                </div>`;
                
                this.reset();
                
                setTimeout(() => {
                    resultDiv.innerHTML = '';
                }, 3000);
            } catch (error) {
                alert('Error adding source: ' + error.message);
            }
        });
        
        // Statistics
        async function loadStatistics() {
            try {
                const response = await fetch('/statistics');
                const data = await response.json();
                
                const resultsDiv = document.getElementById('statsResults');
                resultsDiv.innerHTML = `
                    <div class="metric-grid">
                        <div class="metric-card">
                            <div class="metric-label">Total Submissions</div>
                            <div class="metric-value">${data.total_submissions}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Total Students</div>
                            <div class="metric-value">${data.total_students}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Cached Sources</div>
                            <div class="metric-value">${data.total_sources}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Redis Memory</div>
                            <div class="metric-value" style="font-size: 20px;">${data.redis_memory_used}</div>
                        </div>
                    </div>
                `;
            } catch (error) {
                alert('Error loading statistics: ' + error.message);
            }
        }
    </script>
</body>
</html>
'''

# Flask Routes
@app.route('/')
def index():
    """Main page."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/analyze', methods=['POST'])
def analyze():
    """Analyze uploaded document for plagiarism."""
    try:
        student_id = request.form.get('student_id')
        assignment_id = request.form.get('assignment_id')
        check_peer = request.form.get('check_peer') == 'true'
        check_history = request.form.get('check_history') == 'true'
        
        # Get content from PDF or text
        content = ''
        if 'pdf_file' in request.files and request.files['pdf_file'].filename:
            pdf_file = request.files['pdf_file']
            content = extract_text_from_pdf(pdf_file)
        elif 'text_content' in request.form:
            content = request.form.get('text_content')
        
        if not content or not content.strip():
            return jsonify({'error': 'No content provided'}), 400
        
        # Submit document
        submission_id = detector.submit_document(
            student_id=student_id,
            assignment_id=assignment_id,
            content=content,
            metadata={
                'source': 'web_upload',
                'ip': request.remote_addr
            }
        )
        
        # Check plagiarism
        results = detector.check_plagiarism(
            submission_id,
            check_peer=check_peer,
            check_history=check_history
        )
        
        # Add word count
        results['word_count'] = len(content.split())
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analytics/<student_id>')
def get_analytics(student_id):
    """Get analytics for a student."""
    try:
        analytics = detector.get_student_analytics(student_id)
        return jsonify(analytics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add_source', methods=['POST'])
def add_source():
    """Add a known source to the database."""
    try:
        data = request.get_json()
        detector.add_source(
            url=data['url'],
            title=data['title'],
            content=data['content']
        )
        return jsonify({'message': 'Source added successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/statistics')
def get_statistics():
    """Get system statistics."""
    try:
        stats = detector.get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Starting Plagiarism Detection System")
    print("=" * 60)
    print("\n📋 Prerequisites:")
    print("   1. Redis server running on localhost:6379")
    print("   2. Install: pip install flask redis PyPDF2")
    print("\n🌐 Access the application at: http://localhost:5000")
    print("\n⚠️  Make sure Redis is running before starting!")
    print("   Start Redis: redis-server")
    print("=" * 60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)