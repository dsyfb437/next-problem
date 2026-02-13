"""
Flask web application for intelligent math practice system.

Features:
- Multi-subject question banks
- BKT-based adaptive recommendations
- User progress persistence (JSON + database)
- Real-time knowledge tracking
"""

import json
import os
import subprocess
from datetime import datetime
from typing import Dict, List
import hmac
import hashlib

from flask import Flask, request, render_template_string, session, redirect, url_for, flash, Response
from dotenv import load_dotenv

from bkt_core import BKTUser, SimpleBKTEngine, recommend_question, check_answer
from db import init_db

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration from environment
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
deploy_key = os.environ.get('DEPLOY_KEY', '')

# Global state
engine = SimpleBKTEngine()
SUBJECT_FILES = {
    '高等数学': 'math1.json',
    '线性代数': 'linalg.json',
    '概率论': 'prob.json'
}


def load_questions(subject: str) -> List[Dict]:
    """
    Load question bank for a specific subject.

    Args:
        subject: Subject name (must be in SUBJECT_FILES)

    Returns:
        List of question dictionaries
    """
    filename = SUBJECT_FILES.get(subject, 'math1.json')
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


# Initialize global state
current_subject = '高等数学'
questions = load_questions(current_subject)

# Initialize database on startup
init_db()

# HTML template
INDEX_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能刷题·考研数学</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css"
          integrity="sha384-wcIxkf4k558AjM3Yz3BBFQUbk/zgIYC2R0QpeeYb+TwlBVMrlgLqwRjRtGZiK7ww"
          crossorigin="anonymous">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.js"
            integrity="sha384-hIoBPJpTUs74ddyc4bFZSM1TVlQDA60VBbJS0oA934VSz82sBx1X7kSx2ATBDIyd"
            crossorigin="anonymous"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/contrib/auto-render.min.js"
            integrity="sha384-43gviWU0YVjaDtb/GhzOouOXtZMP/7XUzwPTstBeZFe/+rCMvRwr4yROQP43s0Xk"
            crossorigin="anonymous"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
        .feedback { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
        .correct { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .wrong { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .progress { background: #e9ecef; padding: 15px; border-radius: 6px; }
        .katex { font-size: 1.2em; }
        select { padding: 8px; border-radius: 4px; border: 1px solid #ddd; }
        input[type="text"] { padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        button[type="submit"] { padding: 8px 20px;
                               background: #007bff; color: white; border: none;
                               border-radius: 4px; cursor: pointer; }
        button[type="submit"]:hover { background: #0056b3; }
    </style>
</head>
<body>
    <h2>考研数学·智能推送</h2>
    <p style="color: #6c757d;">欢迎回来，{{ user_id }}！</p>

    <form method="post" action="/select_subject" style="margin-bottom: 20px;">
        <label for="subject">当前题库：</label>
        <select name="subject" id="subject" onchange="this.form.submit()">
            <option value="高等数学" {% if current_subject == '高等数学' %}selected{% endif %}>高等数学</option>
            <option value="线性代数" {% if current_subject == '线性代数' %}selected{% endif %}>线性代数</option>
            <option value="概率论" {% if current_subject == '概率论' %}selected{% endif %}>概率论</option>
        </select>
        <noscript><button type="submit">切换</button></noscript>
    </form>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="feedback {{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    {% if question %}
        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
            <p><strong>【{{ question.subject }}】{{ question.chapter }}</strong> · 难度 {{ question.difficulty }}</p>
            <p style="font-size: 1.2rem;">{{ question.question_text | safe }}</p>

            <form method="post" action="/answer" style="margin-top: 20px;">
                <input type="hidden" name="qid" value="{{ question.id }}">
                <input type="text" name="answer" placeholder="输入你的答案"
                       style="width: 70%; padding: 8px; font-size: 1rem;" autofocus>
                <button type="submit" style="padding: 8px 20px; font-size: 1rem;">提交</button>
            </form>
        </div>

        <div class="progress">
            <h4>当前知识点掌握度</h4>
            <ul>
            {% for kc, p in knowledge.items() %}
                <li><strong>{{ kc }}</strong>: {{ '%.3f'|format(p) }}</li>
            {% else %}
                <li>还没有知识点数据，做完第一题就会生成～</li>
            {% endfor %}
            </ul>
            <p style="color: #666; font-size: 0.9rem;">
                已做 {{ total_answered }} 题 / 总 {{ total_questions }} 题 ·
                正确率 {{ (correct_count / total_answered * 100) | round(1) if total_answered > 0 else 0 }}%
            </p>
        </div>
    {% else %}
        <div style="text-align: center; padding: 40px; background: #d1ecf1; border-radius: 8px;">
            <h3>恭喜！你已经完成了当前题库的所有题目！</h3>
            <p style="font-size: 1.2rem; margin: 20px 0;">
                共完成 <strong>{{ total_questions }}</strong> 题 ·
                正确率 <strong>{{ (correct_count / total_answered * 100) | round(1) if total_answered > 0 else 0 }}%</strong>
            </p>
            <div style="margin-top: 30px; display: flex; gap: 20px; justify-content: center;">
                <a href="/restart" style="background: #28a745; color: white; padding: 10px 20px;
                                     text-decoration: none; border-radius: 4px;">
                    再来一遍（保留掌握度）
                </a>
                <a href="/reset" style="background: #6c757d; color: white; padding: 10px 20px;
                                   text-decoration: none; border-radius: 4px;">
                    完全重置（清空所有进度）
                </a>
            </div>
            <p style="margin-top: 20px; color: #666; font-size: 0.9rem;">
                保留掌握度：你学会的知识点不会丢失，可以更高效地复习。
            </p>
        </div>
    {% endif %}

    <p style="margin-top: 30px;"><a href="/reset">重置我的进度</a></p>
    <script>
        document.addEventListener("DOMContentLoaded", function() {
            renderMathInElement(document.body, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '\\(', right: '\\)', display: false},
                    {left: '$', right: '$', display: false}
                ],
                throwOnError: false
            });
        });
    </script>
</body>
</html>
'''


def get_current_user() -> BKTUser:
    """
    Get or create current user from session.

    Returns:
        BKTUser instance
    """
    user_id = session.get('user_id')
    if not user_id:
        user_id = f"user_{datetime.now().timestamp()}"
        session['user_id'] = user_id
    return BKTUser.load_from_file(user_id, engine.default_mastery)


@app.route('/select_subject', methods=['POST'])
def select_subject():
    """Switch to a different subject question bank."""
    global current_subject, questions
    subject = request.form.get('subject', '高等数学')
    if subject in SUBJECT_FILES:
        current_subject = subject
        questions = load_questions(subject)
        flash(f"已切换到《{subject}》题库", "correct")
    else:
        flash("科目不存在", "wrong")
    return redirect(url_for('index'))


@app.route('/')
def index():
    """Main page showing current question and user progress."""
    user = get_current_user()

    current_qids = {q['id'] for q in questions}
    available_qids = current_qids - user.answered_questions
    question = recommend_question(user, questions, available_qids)

    subject_answered = user.answered_questions & current_qids
    total_answered = len(subject_answered)
    subject_correct_in_round = user.correct_in_round & current_qids
    correct_count = len(subject_correct_in_round)
    total_questions = len(questions)

    if question is None:
        if total_answered < total_questions:
            flash("剩余题目对应的知识点已熟练掌握，如需复习请切换科目或重置进度。", "correct")

    display_id = user.user_id
    if display_id.startswith('user_'):
        short_id = display_id.split('_')[1][:6] if '_' in display_id else display_id[:6]
        display_id = f"访客{short_id}"

    return render_template_string(
        INDEX_HTML,
        question=question,
        knowledge=user.knowledge_state,
        total_answered=total_answered,
        correct_count=correct_count,
        total_questions=total_questions,
        user_id=display_id,
        current_subject=current_subject
    )


@app.route('/answer', methods=['POST'])
def answer():
    """Process user answer submission."""
    user = get_current_user()
    qid = request.form.get('qid', '')
    user_answer = request.form.get('answer', '').strip()

    question = next((q for q in questions if q.get('id') == qid), None)
    if not question:
        flash("题目不存在，请重试", "wrong")
        return redirect(url_for('index'))

    is_correct = check_answer(question, user_answer)

    if is_correct:
        flash("回答正确！", "correct")
        user.correct_in_round.add(qid)
    else:
        flash(f"回答错误。正确答案：{question.get('answer', '')}", "wrong")

    user.history.append({
        "qid": qid,
        "user_answer": user_answer,
        "correct": is_correct,
        "timestamp": datetime.now().isoformat()
    })

    for kc in question.get('knowledge_tags', ['default']):
        old_p = user.knowledge_state.get(kc, engine.default_mastery)
        new_p = engine.update_mastery(old_p, is_correct)
        user.knowledge_state[kc] = new_p

    user.answered_questions.add(qid)
    user.save_to_file()
    user.record_interaction(qid, is_correct)

    return redirect(url_for('index'))


@app.route('/reset')
def reset():
    """Completely reset user progress."""
    user_id = session.get('user_id')
    if user_id:
        file_path = os.path.join('data', f"user_{user_id}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
        session.clear()
        flash("已完全重置进度，所有数据已清空。", "correct")
    return redirect(url_for('index'))


@app.route('/restart')
def restart():
    """Reset question progress while keeping knowledge mastery."""
    user = get_current_user()
    user.answered_questions = set()
    user.correct_in_round = set()
    user.save_to_file()
    flash("已重置题目进度，你可以重新挑战所有题目，已掌握的知识点仍然保留。", "correct")
    return redirect(url_for('index'))


@app.route('/git_pull')
def git_pull():
    """
    Hidden deployment route to trigger git pull.

    Security: Requires DEPLOY_KEY in query parameter.
    Use: /git_pull?key=<DEPLOY_KEY>

    Returns:
        JSON response with status and output
    """
    provided_key = request.args.get('key', '')

    if not deploy_key:
        return Response('{"status": "error", "message": "DEPLOY_KEY not configured"}',
                   mimetype='application/json', status=500)

    if not hmac.compare_digest(provided_key, deploy_key):
        return Response('{"status": "error", "message": "Invalid deploy key"}',
                   mimetype='application/json', status=403)

    try:
        result = subprocess.run(
            ['git', 'pull'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            return Response(
                f'{{"status": "success", "message": "Git pull completed", "output": {json.dumps(result.stdout)}}}',
                mimetype='application/json'
            )
        else:
            return Response(
                f'{{"status": "error", "message": "Git pull failed", "output": {json.dumps(result.stderr)}}}',
                mimetype='application/json',
                status=500
            )
    except subprocess.TimeoutExpired:
        return Response('{"status": "error", "message": "Operation timed out"}',
                   mimetype='application/json', status=500)
    except Exception as e:
        return Response(f'{{"status": "error", "message": "{str(e)}"}}',
                   mimetype='application/json', status=500)


if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
