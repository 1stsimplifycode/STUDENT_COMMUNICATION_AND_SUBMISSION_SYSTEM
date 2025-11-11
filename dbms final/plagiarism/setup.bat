@echo off
REM ========================================
REM Plagiarism Detection System Setup Script
REM ========================================

echo.
echo ==========================================
echo Plagiarism Detection System Setup
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.7+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python found
python --version
echo.

REM Create requirements.txt first
echo Creating requirements.txt...
echo redis==5.0.1> requirements.txt
echo [OK] Created requirements.txt
echo.

REM Install dependencies
echo Installing Python dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet

if errorlevel 1 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

echo [OK] All dependencies installed!
echo.

REM Create Python file using Python itself (avoids batch escaping issues)
echo Creating plagiarism_detector.py...

python -c "import sys; open('plagiarism_detector.py', 'w').write('''import redis\nimport json\nimport hashlib\nfrom datetime import datetime, timedelta\nfrom typing import List, Dict, Optional, Tuple\nimport re\nfrom collections import Counter\nimport math\n\nclass PlagiarismDetector:\n    def __init__(self, redis_host=\"localhost\", redis_port=6379, redis_db=0):\n        self.redis_client = redis.Redis(\n            host=redis_host,\n            port=redis_port,\n            db=redis_db,\n            decode_responses=True\n        )\n        self.similarity_threshold = 0.75\n    \n    def submit_document(self, student_id: str, assignment_id: str, content: str, metadata: Optional[Dict] = None) -> str:\n        submission_id = self._generate_submission_id(student_id, assignment_id)\n        timestamp = datetime.now().isoformat()\n        \n        submission_data = {\n            \"student_id\": student_id,\n            \"assignment_id\": assignment_id,\n            \"content\": content,\n            \"timestamp\": timestamp,\n            \"word_count\": len(content.split()),\n            \"metadata\": json.dumps(metadata or {})\n        }\n        \n        self.redis_client.hset(f\"submission:{submission_id}\", mapping=submission_data)\n        self.redis_client.sadd(f\"student:{student_id}:submissions\", submission_id)\n        self.redis_client.sadd(f\"assignment:{assignment_id}:submissions\", submission_id)\n        self._store_writing_style(student_id, content)\n        self.redis_client.expire(f\"submission:{submission_id}\", 7776000)\n        \n        return submission_id\n    \n    def get_submission(self, submission_id: str) -> Optional[Dict]:\n        data = self.redis_client.hgetall(f\"submission:{submission_id}\")\n        if data:\n            data[\"metadata\"] = json.loads(data.get(\"metadata\", \"{}\"))\n        return data if data else None\n    \n    def check_plagiarism(self, submission_id: str, check_peer: bool = True, check_history: bool = True) -> Dict:\n        submission = self.get_submission(submission_id)\n        if not submission:\n            return {\"error\": \"Submission not found\"}\n        \n        content = submission[\"content\"]\n        student_id = submission[\"student_id\"]\n        assignment_id = submission[\"assignment_id\"]\n        \n        results = {\n            \"submission_id\": submission_id,\n            \"timestamp\": datetime.now().isoformat(),\n            \"overall_similarity\": 0.0,\n            \"matches\": [],\n            \"flags\": [],\n            \"risk_level\": \"LOW\"\n        }\n        \n        if check_peer:\n            peer_matches = self._check_peer_submissions(content, assignment_id, submission_id)\n            results[\"matches\"].extend(peer_matches)\n        \n        if check_history:\n            history_matches = self._check_student_history(content, student_id, submission_id)\n            results[\"matches\"].extend(history_matches)\n        \n        source_matches = self._check_cached_sources(content)\n        results[\"matches\"].extend(source_matches)\n        \n        if results[\"matches\"]:\n            results[\"overall_similarity\"] = max(m[\"similarity\"] for m in results[\"matches\"])\n        \n        results[\"risk_level\"] = self._calculate_risk_level(results[\"overall_similarity\"])\n        \n        authorship_score = self._verify_authorship(student_id, content)\n        results[\"authorship_consistency\"] = authorship_score\n        if authorship_score < 0.5:\n            results[\"flags\"].append(\"Unusual writing style detected\")\n        \n        self._store_check_result(submission_id, results)\n        \n        return results\n    \n    def _check_peer_submissions(self, content: str, assignment_id: str, current_submission_id: str) -> List[Dict]:\n        matches = []\n        peer_submissions = self.redis_client.smembers(f\"assignment:{assignment_id}:submissions\")\n        \n        for peer_id in peer_submissions:\n            if peer_id == current_submission_id:\n                continue\n            \n            peer_data = self.get_submission(peer_id)\n            if not peer_data:\n                continue\n            \n            similarity = self._calculate_similarity(content, peer_data[\"content\"])\n            \n            if similarity > self.similarity_threshold:\n                matches.append({\n                    \"type\": \"peer_submission\",\n                    \"source_id\": peer_id,\n                    \"student_id\": peer_data[\"student_id\"],\n                    \"similarity\": similarity,\n                    \"matched_segments\": self._find_matching_segments(content, peer_data[\"content\"])\n                })\n        \n        return matches\n    \n    def _check_student_history(self, content: str, student_id: str, current_submission_id: str) -> List[Dict]:\n        matches = []\n        past_submissions = self.redis_client.smembers(f\"student:{student_id}:submissions\")\n        \n        for past_id in past_submissions:\n            if past_id == current_submission_id:\n                continue\n            \n            past_data = self.get_submission(past_id)\n            if not past_data:\n                continue\n            \n            similarity = self._calculate_similarity(content, past_data[\"content\"])\n            \n            if similarity > 0.6:\n                matches.append({\n                    \"type\": \"self_plagiarism\",\n                    \"source_id\": past_id,\n                    \"assignment_id\": past_data[\"assignment_id\"],\n                    \"similarity\": similarity,\n                    \"timestamp\": past_data[\"timestamp\"]\n                })\n        \n        return matches\n    \n    def _check_cached_sources(self, content: str) -> List[Dict]:\n        matches = []\n        source_keys = self.redis_client.keys(\"source:*\")\n        \n        for source_key in source_keys[:100]:\n            source_data = self.redis_client.hgetall(source_key)\n            if not source_data:\n                continue\n            \n            similarity = self._calculate_similarity(content, source_data.get(\"content\", \"\"))\n            \n            if similarity > self.similarity_threshold:\n                matches.append({\n                    \"type\": \"external_source\",\n                    \"source_url\": source_data.get(\"url\", \"unknown\"),\n                    \"source_title\": source_data.get(\"title\", \"Unknown Source\"),\n                    \"similarity\": similarity\n                })\n        \n        return matches\n    \n    def _store_writing_style(self, student_id: str, content: str):\n        features = self._extract_style_features(content)\n        style_key = f\"style:{student_id}\"\n        \n        if self.redis_client.exists(style_key):\n            existing = self.redis_client.hgetall(style_key)\n            count = int(existing.get(\"sample_count\", 0))\n            \n            for key, value in features.items():\n                if key in existing:\n                    old_avg = float(existing[key])\n                    new_avg = (old_avg * count + value) / (count + 1)\n                    features[key] = new_avg\n            \n            features[\"sample_count\"] = count + 1\n        else:\n            features[\"sample_count\"] = 1\n        \n        features_str = {k: str(v) for k, v in features.items()}\n        self.redis_client.hset(style_key, mapping=features_str)\n    \n    def _verify_authorship(self, student_id: str, content: str) -> float:\n        style_key = f\"style:{student_id}\"\n        \n        if not self.redis_client.exists(style_key):\n            return 1.0\n        \n        historical_style = {k: float(v) for k, v in self.redis_client.hgetall(style_key).items() if k != \"sample_count\"}\n        current_style = self._extract_style_features(content)\n        \n        total_diff = 0\n        for key in historical_style:\n            if key in current_style:\n                diff = abs(historical_style[key] - current_style[key])\n                total_diff += diff\n        \n        consistency = max(0, 1 - (total_diff / len(historical_style)))\n        return consistency\n    \n    def _extract_style_features(self, content: str) -> Dict[str, float]:\n        words = content.split()\n        sentences = re.split(r\"[.!?]+\", content)\n        \n        return {\n            \"avg_word_length\": sum(len(w) for w in words) / max(len(words), 1),\n            \"avg_sentence_length\": len(words) / max(len(sentences), 1),\n            \"lexical_diversity\": len(set(words)) / max(len(words), 1),\n            \"punctuation_ratio\": sum(1 for c in content if c in \".,;:!?\") / max(len(content), 1),\n            \"caps_ratio\": sum(1 for c in content if c.isupper()) / max(len(content), 1)\n        }\n    \n    def _calculate_similarity(self, text1: str, text2: str) -> float:\n        words1 = self._tokenize(text1)\n        words2 = self._tokenize(text2)\n        vocab = set(words1 + words2)\n        vec1 = self._calculate_tfidf(words1, vocab)\n        vec2 = self._calculate_tfidf(words2, vocab)\n        return self._cosine_similarity(vec1, vec2)\n    \n    def _tokenize(self, text: str) -> List[str]:\n        text = text.lower()\n        text = re.sub(r\"[^\\w\\s]\", \"\", text)\n        return text.split()\n    \n    def _calculate_tfidf(self, words: List[str], vocab: set) -> Dict[str, float]:\n        word_count = Counter(words)\n        tf = {word: count / len(words) for word, count in word_count.items()}\n        idf = {word: 1.0 for word in vocab}\n        tfidf = {word: tf.get(word, 0) * idf.get(word, 1) for word in vocab}\n        return tfidf\n    \n    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:\n        dot_product = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in vec1.keys())\n        mag1 = math.sqrt(sum(v**2 for v in vec1.values()))\n        mag2 = math.sqrt(sum(v**2 for v in vec2.values()))\n        if mag1 == 0 or mag2 == 0:\n            return 0.0\n        return dot_product / (mag1 * mag2)\n    \n    def _find_matching_segments(self, text1: str, text2: str, min_length: int = 20) -> List[str]:\n        sentences1 = re.split(r\"[.!?]+\", text1)\n        sentences2 = re.split(r\"[.!?]+\", text2)\n        matches = []\n        for s1 in sentences1:\n            s1 = s1.strip()\n            if len(s1) < min_length:\n                continue\n            for s2 in sentences2:\n                s2 = s2.strip()\n                if len(s2) < min_length:\n                    continue\n                similarity = self._calculate_similarity(s1, s2)\n                if similarity > 0.8:\n                    matches.append(s1[:100] + \"...\")\n                    break\n        return matches[:5]\n    \n    def add_source(self, url: str, title: str, content: str):\n        source_id = hashlib.md5(url.encode()).hexdigest()\n        source_data = {\n            \"url\": url,\n            \"title\": title,\n            \"content\": content,\n            \"added_date\": datetime.now().isoformat()\n        }\n        self.redis_client.hset(f\"source:{source_id}\", mapping=source_data)\n        self.redis_client.sadd(\"sources:all\", source_id)\n    \n    def get_student_analytics(self, student_id: str) -> Dict:\n        submissions = self.redis_client.smembers(f\"student:{student_id}:submissions\")\n        analytics = {\n            \"total_submissions\": len(submissions),\n            \"flagged_submissions\": 0,\n            \"avg_similarity_score\": 0.0,\n            \"authorship_scores\": []\n        }\n        total_similarity = 0\n        for sub_id in submissions:\n            result_key = f\"check_result:{sub_id}\"\n            if self.redis_client.exists(result_key):\n                result = json.loads(self.redis_client.get(result_key))\n                total_similarity += result.get(\"overall_similarity\", 0)\n                if result.get(\"risk_level\") in [\"HIGH\", \"MEDIUM\"]:\n                    analytics[\"flagged_submissions\"] += 1\n                if \"authorship_consistency\" in result:\n                    analytics[\"authorship_scores\"].append(result[\"authorship_consistency\"])\n        if len(submissions) > 0:\n            analytics[\"avg_similarity_score\"] = total_similarity / len(submissions)\n        return analytics\n    \n    def _store_check_result(self, submission_id: str, results: Dict):\n        result_key = f\"check_result:{submission_id}\"\n        self.redis_client.set(result_key, json.dumps(results))\n        self.redis_client.expire(result_key, 7776000)\n    \n    def _generate_submission_id(self, student_id: str, assignment_id: str) -> str:\n        timestamp = datetime.now().isoformat()\n        data = f\"{student_id}:{assignment_id}:{timestamp}\"\n        return hashlib.sha256(data.encode()).hexdigest()[:16]\n    \n    def _calculate_risk_level(self, similarity: float) -> str:\n        if similarity >= 0.85:\n            return \"HIGH\"\n        elif similarity >= 0.70:\n            return \"MEDIUM\"\n        else:\n            return \"LOW\"\n    \n    def clear_student_data(self, student_id: str):\n        submissions = self.redis_client.smembers(f\"student:{student_id}:submissions\")\n        for sub_id in submissions:\n            self.redis_client.delete(f\"submission:{sub_id}\")\n            self.redis_client.delete(f\"check_result:{sub_id}\")\n        self.redis_client.delete(f\"student:{student_id}:submissions\")\n        self.redis_client.delete(f\"style:{student_id}\")\n    \n    def get_statistics(self) -> Dict:\n        return {\n            \"total_submissions\": len(self.redis_client.keys(\"submission:*\")),\n            \"total_students\": len(self.redis_client.keys(\"student:*:submissions\")),\n            \"total_sources\": len(self.redis_client.smembers(\"sources:all\")),\n            \"redis_memory_used\": self.redis_client.info(\"memory\")[\"used_memory_human\"]\n        }\n\nif __name__ == \"__main__\":\n    detector = PlagiarismDetector(redis_host=\"localhost\", redis_port=6379)\n    print(\"=\"*50)\n    print(\"Plagiarism Detection System - Demo\")\n    print(\"=\"*50)\n    print()\n    try:\n        detector.redis_client.ping()\n        print(\"[OK] Redis connection successful!\")\n        print()\n    except Exception as e:\n        print(f\"[ERROR] Could not connect to Redis: {e}\")\n        print(\"Please make sure Redis server is running on localhost:6379\")\n        print()\n        input(\"Press Enter to exit...\")\n        exit(1)\n    student_content = \"\"\"Artificial intelligence has revolutionized many aspects of modern life. Machine learning algorithms can now process vast amounts of data to make predictions and decisions. Deep learning, a subset of machine learning, uses neural networks to achieve remarkable results in image recognition and natural language processing.\"\"\"\n    print(\"Submitting student document...\")\n    submission_id = detector.submit_document(student_id=\"student_001\", assignment_id=\"ai_essay_2024\", content=student_content, metadata={\"course\": \"CS101\", \"semester\": \"Fall 2024\"})\n    print(f\"Submission ID: {submission_id}\")\n    print()\n    print(\"Adding known source to database...\")\n    detector.add_source(url=\"https://example.com/ai-article\", title=\"Introduction to AI\", content=\"Artificial intelligence has revolutionized many aspects of modern life.\")\n    print(\"[OK] Source added\")\n    print()\n    print(\"Running plagiarism check...\")\n    results = detector.check_plagiarism(submission_id)\n    print(\"\\n\" + \"=\"*50)\n    print(\"PLAGIARISM CHECK RESULTS\")\n    print(\"=\"*50)\n    print(f\"Overall Similarity: {results[\"overall_similarity\"]:.2%}\")\n    print(f\"Risk Level: {results[\"risk_level\"]}\")\n    if \"authorship_consistency\" in results:\n        print(f\"Authorship Consistency: {results[\"authorship_consistency\"]:.2%}\")\n    print(f\"\\nMatches Found: {len(results[\"matches\"])}\")\n    for i, match in enumerate(results[\"matches\"], 1):\n        print(f\"\\n--- Match {i} ---\")\n        print(f\"Type: {match[\"type\"]}\")\n        print(f\"Similarity: {match[\"similarity\"]:.2%}\")\n        if \"source_title\" in match:\n            print(f\"Source: {match[\"source_title\"]}\")\n    print(\"\\n\" + \"=\"*50)\n    print(\"STUDENT ANALYTICS\")\n    print(\"=\"*50)\n    analytics = detector.get_student_analytics(\"student_001\")\n    print(f\"Total Submissions: {analytics[\"total_submissions\"]}\")\n    print(f\"Flagged Submissions: {analytics[\"flagged_submissions\"]}\")\n    print(f\"Average Similarity: {analytics[\"avg_similarity_score\"]:.2%}\")\n    print(\"\\n\" + \"=\"*50)\n    print(\"SYSTEM STATISTICS\")\n    print(\"=\"*50)\n    stats = detector.get_statistics()\n    print(f\"Total Submissions: {stats[\"total_submissions\"]}\")\n    print(f\"Total Students: {stats[\"total_students\"]}\")\n    print(f\"Total Sources: {stats[\"total_sources\"]}\")\n    print(f\"Memory Used: {stats[\"redis_memory_used\"]}\")\n    print(\"\\n\" + \"=\"*50)\n    print(\"Demo completed successfully!\")\n    print(\"=\"*50)\n    print()\n    input(\"Press Enter to exit...\")\n''')"

if errorlevel 1 (
    echo [ERROR] Failed to create Python file!
    pause
    exit /b 1
)

echo [OK] Created plagiarism_detector.py
echo.

REM Redis check
echo ==========================================
echo Important: Redis Server Required
echo ==========================================
echo.
echo Make sure Redis is running on localhost:6379
echo.
echo Windows: Download from https://github.com/microsoftarchive/redis/releases
echo          Or Docker: docker run -d -p 6379:6379 redis
echo.
echo Linux/Mac: redis-server
echo.
set /p CONTINUE="Is Redis running? (y/n): "

if /i "%CONTINUE%" NEQ "y" (
    echo.
    echo Please start Redis and run: python plagiarism_detector.py
    echo.
    pause
    exit /b 0
)

echo.
echo ==========================================
echo Running Plagiarism Detection System...
echo ==========================================
echo.

python plagiarism_detector.py

echo.
echo ==========================================
echo Setup Complete!
echo ==========================================
echo.
echo Files created:
echo - plagiarism_detector.py
echo - requirements.txt
echo.
echo To run again: python plagiarism_detector.py
echo.
pause