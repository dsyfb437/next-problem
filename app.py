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
from datetime import datetime, timedelta
from typing import Dict, List
import hmac
import hashlib

from flask import Flask, request, render_template_string, session, redirect, url_for, flash, Response, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

from bkt_core import BKTUser, SimpleBKTEngine, recommend_question, check_answer
from db import init_db

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration from environment
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
deploy_key = os.environ.get('DEPLOY_KEY', '')

# Initialize Flask-Login and Bcrypt
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'
bcrypt = Bcrypt(app)


@login_manager.user_loader
def load_user(user_id: str) -> BKTUser:
    """Flask-Login user loader"""
    return BKTUser.load_from_file(user_id, engine.default_mastery)

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
    import os
    # Try multiple paths for compatibility
    possible_paths = [
        os.path.join('questions', SUBJECT_FILES.get(subject, 'math1.json')),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'questions', SUBJECT_FILES.get(subject, 'math1.json')),
    ]
    filename = None
    for fp in possible_paths:
        if os.path.exists(fp):
            filename = fp
            break
    if filename is None:
        filename = possible_paths[0]
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


# ==================== 用户账号相关函数 ====================

def load_users_index() -> Dict:
    """加载用户索引"""
    path = os.path.join('data', 'users_index.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"users": []}


def save_users_index(data: Dict) -> None:
    """保存用户索引"""
    os.makedirs('data', exist_ok=True)
    path = os.path.join('data', 'users_index.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def username_exists(username: str) -> bool:
    """检查用户名是否已存在"""
    idx = load_users_index()
    return any(u.get('username') == username for u in idx['users'])


def get_user_by_username(username: str) -> Dict:
    """根据用户名获取用户信息"""
    idx = load_users_index()
    return next((u for u in idx['users'] if u.get('username') == username), None)


# ==================== 登录注册模板 ====================

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>登录 - 智能刷题</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               max-width: 400px; margin: 60px auto; padding: 20px; }
        h2 { text-align: center; color: #333; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="password"] {
            width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px;
            box-sizing: border-box; font-size: 16px;
        }
        button[type="submit"] {
            width: 100%; padding: 12px; background: #007bff; color: white;
            border: none; border-radius: 4px; font-size: 16px; cursor: pointer;
        }
        button[type="submit"]:hover { background: #0056b3; }
        .link { text-align: center; margin-top: 20px; }
        .link a { color: #007bff; }
        .feedback { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
        .correct { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .wrong { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <h2>登录</h2>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="feedback {{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    <form method="post" action="/login_username">
        <div class="form-group">
            <label for="username">用户名</label>
            <input type="text" name="username" id="username" required>
        </div>
        <div class="form-group">
            <label for="password">密码</label>
            <input type="password" name="password" id="password" required>
        </div>
        <button type="submit">登录</button>
    </form>

    <div class="link">
        还没有账号？<a href="/register">去注册</a>
    </div>
</body>
</html>
'''

REGISTER_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>注册 - 智能刷题</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               max-width: 400px; margin: 60px auto; padding: 20px; }
        h2 { text-align: center; color: #333; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="password"] {
            width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px;
            box-sizing: border-box; font-size: 16px;
        }
        button[type="submit"] {
            width: 100%; padding: 12px; background: #28a745; color: white;
            border: none; border-radius: 4px; font-size: 16px; cursor: pointer;
        }
        button[type="submit"]:hover { background: #218838; }
        .merge-option {
            background: #e9ecef; padding: 15px; border-radius: 6px; margin-bottom: 20px;
        }
        .merge-option label { font-weight: normal; cursor: pointer; }
        .link { text-align: center; margin-top: 20px; }
        .link a { color: #007bff; }
        .feedback { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
        .correct { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .wrong { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <h2>注册新账号</h2>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="feedback {{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    <form method="post" action="/register">
        <div class="form-group">
            <label for="username">用户名</label>
            <input type="text" name="username" id="username" required minlength="2">
        </div>
        <div class="form-group">
            <label for="password">密码</label>
            <input type="password" name="password" id="password" required minlength="6">
        </div>
        <div class="form-group">
            <label for="confirm_password">确认密码</label>
            <input type="password" name="confirm_password" id="confirm_password" required>
        </div>

        <div class="merge-option">
            <label>
                <input type="checkbox" name="merge_progress" value="yes">
                合并当前进度（保留匿名状态的答题记录）
            </label>
            <p style="font-size: 0.85rem; color: #666; margin-top: 5px;">
                取消勾选则从头开始学习
            </p>
        </div>

        <button type="submit">注册</button>
    </form>

    <div class="link">
        已有账号？<a href="/login">去登录</a>
    </div>

    <script>
        document.querySelector('form').addEventListener('submit', function(e) {
            const p1 = document.getElementById('password').value;
            const p2 = document.getElementById('confirm_password').value;
            if (p1 !== p2) {
                e.preventDefault();
                alert('两次密码输入不一致');
            }
        });
    </script>
</body>
</html>
'''

# ==================== 登录注册路由 ====================


@app.route('/login')
def login_page():
    """登录页面"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template_string(LOGIN_HTML)


@app.route('/register')
def register_page():
    """注册页面"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template_string(REGISTER_HTML)


@app.route('/login_username', methods=['POST'])
def login_username():
    """用户名密码登录"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    # 查找用户
    user_info = get_user_by_username(username)
    if not user_info:
        flash("用户名不存在", "wrong")
        return redirect(url_for('login_page'))

    user = BKTUser.load_from_file(user_info['user_id'], engine.default_mastery)
    if not user.check_password(password, bcrypt):
        flash("密码错误", "wrong")
        return redirect(url_for('login_page'))

    # 登录用户
    login_user(user)
    session['user_id'] = user.user_id
    flash(f"欢迎回来，{user.username}！", "correct")
    return redirect(url_for('index'))


@app.route('/logout')
@login_required
def logout():
    """登出"""
    logout_user()
    session.clear()
    flash("已退出登录", "correct")
    return redirect(url_for('index'))


@app.route('/register', methods=['POST'])
def register():
    """注册新用户"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    merge_progress = request.form.get('merge_progress', 'no') == 'yes'

    # 验证
    if not username:
        flash("用户名不能为空", "wrong")
        return redirect(url_for('register_page'))

    if len(username) < 3:
        flash("用户名至少3位", "wrong")
        return redirect(url_for('register_page'))

    if len(username) > 20:
        flash("用户名最多20位", "wrong")
        return redirect(url_for('register_page'))

    if username_exists(username):
        flash("用户名已存在", "wrong")
        return redirect(url_for('register_page'))

    if len(password) < 6:
        flash("密码至少6位", "wrong")
        return redirect(url_for('register_page'))

    # 创建用户
    import uuid
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    user = BKTUser(user_id)
    user.username = username
    user.set_password(password, bcrypt)
    user.created_at = datetime.now().isoformat()

    # 合并匿名进度（如果选择）
    anonymous_user_id = session.get('user_id')
    if merge_progress and anonymous_user_id:
        anon_user = BKTUser.load_from_file(anonymous_user_id, engine.default_mastery)
        # 合并数据
        user.knowledge_state = anon_user.knowledge_state
        user.answered_questions = anon_user.answered_questions
        user.history = anon_user.history
        user.correct_in_round = anon_user.correct_in_round

    user.save_to_file()

    # 更新索引
    idx = load_users_index()
    idx['users'].append({"username": username, "user_id": user_id})
    save_users_index(idx)

    # 自动登录
    login_user(user)
    session['user_id'] = user.user_id

    flash(f"注册成功！欢迎 {username}！", "correct")
    return redirect(url_for('index'))


# HTML template
INDEX_HTML = r'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能刷题·考研数学</title>
    <!-- KaTeX for LaTeX rendering -->
    <link rel="stylesheet" href="https://cdn.staticfile.org/KaTeX/0.16.10/katex.min.css"
          integrity="sha384-wcIxkf4k558AjM3Yz3BBFQUbk/zgIYC2R0QpeeYb+TwlBVMrlgLqwRjRtGZiK7ww"
          crossorigin="anonymous">
    <script defer src="https://cdn.staticfile.org/KaTeX/0.16.10/katex.min.js"
            integrity="sha384-hIoBPJpTUs74ddyc4bFZSM1TVlQDA60VBbJS0oA934VSz82sBx1X7kSx2ATBDIyd"
            crossorigin="anonymous"></script>
    <script defer src="https://cdn.staticfile.org/KaTeX/0.16.10/contrib/auto-render.min.js"
            integrity="sha384-43gviWU0YVjaDtb/GhzOouOXtZMP/7XUzwPTstBeZFe/+rCMvRwr4yROQP43s0Xk"
            crossorigin="anonymous"></script>
    <!-- MathLive for formula input -->
    <script defer src="https://unpkg.com/mathlive@0.100.0/dist/mathlive.js"></script>
    <style>
        :root {
            --primary: #3b82f6;
            --primary-dark: #1d4ed8;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --info: #06b6d4;
            --bg: #f1f5f9;
            --card: #ffffff;
            --text: #1e293b;
            --text-light: #64748b;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
            --shadow-hover: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
            --radius: 16px;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: var(--bg); color: var(--text); min-height: 100vh; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .feedback { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
        .correct { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .wrong { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .katex { font-size: 1.2em; }
        /* 顶部导航 */
        .navbar {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            border-radius: var(--radius); padding: 20px 24px; color: white; margin-bottom: 24px;
            box-shadow: var(--shadow);
        }
        .navbar h1 { font-size: 1.5rem; font-weight: 600; margin-bottom: 8px; }
        .navbar .user-info { display: flex; align-items: center; gap: 16px; font-size: 0.9rem; opacity: 0.9; }
        .navbar .user-info a { color: white; text-decoration: underline; opacity: 0.85; }
        /* 题库切换 */
        .subject-selector {
            background: var(--card); border-radius: var(--radius); padding: 16px 20px; margin-bottom: 20px;
            box-shadow: var(--shadow); display: flex; align-items: center; gap: 12px;
        }
        .subject-selector label { font-weight: 500; color: var(--text-light); }
        .subject-selector select {
            flex: 1; max-width: 200px; padding: 10px 16px; border: 2px solid #e2e8f0;
            border-radius: 10px; font-size: 1rem; background: white; cursor: pointer; transition: border-color 0.2s;
        }
        .subject-selector select:hover, .subject-selector select:focus { border-color: var(--primary); outline: none; }
        /* 题目卡片 */
        .question-card {
            background: var(--card); border-radius: var(--radius); overflow: hidden;
            box-shadow: var(--shadow); margin-bottom: 20px; transition: box-shadow 0.3s;
        }
        .question-card:hover { box-shadow: var(--shadow-hover); }
        .question-header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            padding: 16px 24px; color: white; display: flex; justify-content: space-between; align-items: center;
        }
        .question-header .meta { display: flex; align-items: center; gap: 12px; }
        .question-header .subject-tag { background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; }
        .question-header .difficulty { font-size: 0.9rem; opacity: 0.9; }
        .question-header .fav-btn {
            background: rgba(255,255,255,0.2); border: none; color: white; padding: 8px 16px;
            border-radius: 20px; cursor: pointer; font-size: 1rem; transition: all 0.2s;
        }
        .question-header .fav-btn:hover { background: rgba(255,255,255,0.3); transform: scale(1.05); }
        .question-header .fav-btn.active { background: var(--warning); }
        .question-body { padding: 24px; }
        .question-text { font-size: 1.25rem; line-height: 1.8; margin-bottom: 20px; }
        .question-text .katex { font-size: 1.4rem; }
        /* 答题区域 */
        .answer-section { background: #f8fafc; border-radius: 12px; padding: 20px; margin-top: 20px; }
        .answer-section h4 { margin-bottom: 12px; color: var(--text-light); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.5px; }
        /* 选择题选项 */
        .option-list { display: flex; flex-direction: column; gap: 10px; }
        .option-item {
            display: flex; align-items: center; padding: 14px 18px; background: white;
            border: 2px solid #e2e8f0; border-radius: 12px; cursor: pointer; transition: all 0.2s;
        }
        .option-item:hover { border-color: var(--primary); background: #f0f7ff; transform: translateX(4px); }
        .option-item input { margin-right: 14px; width: 18px; height: 18px; accent-color: var(--primary); }
        .option-text { flex: 1; font-size: 1rem; }
        /* 公式输入 */
        .formula-input-wrapper { background: white; border: 2px solid #e2e8f0; border-radius: 12px; padding: 16px; }
        .formula-input-wrapper math-field { width: 100%; font-size: 1.2rem; padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; }
        .formula-input-wrapper math-field:focus-within { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }
        .input-preview { margin-top: 12px; padding: 10px; background: #f8fafc; border-radius: 8px; font-size: 0.9rem; color: var(--text-light); }
        .input-hint { font-size: 0.85rem; color: var(--text-light); margin-top: 4px; }
        /* 提交按钮 */
        .submit-btn {
            margin-top: 20px; padding: 14px 32px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white; border: none; border-radius: 12px; font-size: 1.1rem; font-weight: 600;
            cursor: pointer; transition: all 0.3s; box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3);
        }
        .submit-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 12px rgba(59, 130, 246, 0.4); }
        .submit-btn:active { transform: translateY(0); }
        /* 统计信息区域 */
        .stats-section { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
        .stat-card { background: var(--card); border-radius: var(--radius); padding: 20px; text-align: center; box-shadow: var(--shadow); transition: transform 0.2s; }
        .stat-card:hover { transform: translateY(-4px); }
        .stat-card .icon { font-size: 2rem; margin-bottom: 8px; }
        .stat-card .value { font-size: 1.75rem; font-weight: 700; margin-bottom: 4px; }
        .stat-card .label { font-size: 0.85rem; color: var(--text-light); }
        .stat-card.blue { border-top: 4px solid var(--primary); }
        .stat-card.blue .value { color: var(--primary); }
        .stat-card.green { border-top: 4px solid var(--success); }
        .stat-card.green .value { color: var(--success); }
        .stat-card.red { border-top: 4px solid var(--danger); }
        .stat-card.red .value { color: var(--danger); }
        .stat-card.yellow { border-top: 4px solid var(--warning); }
        .stat-card.yellow .value { color: var(--warning); }
        /* 知识点 */
        .knowledge-section { background: var(--card); border-radius: var(--radius); padding: 24px; box-shadow: var(--shadow); margin-bottom: 20px; }
        .knowledge-section h3 { margin-bottom: 16px; font-size: 1.1rem; color: var(--text); }
        .knowledge-list { display: flex; flex-direction: column; gap: 12px; }
        .knowledge-item { display: flex; align-items: center; gap: 12px; }
        .knowledge-item .name { min-width: 80px; font-weight: 500; font-size: 0.95rem; }
        .knowledge-item .bar { flex: 1; height: 12px; background: #e2e8f0; border-radius: 6px; overflow: hidden; }
        .knowledge-item .bar-fill { height: 100%; border-radius: 6px; transition: width 0.5s ease; }
        .knowledge-item .bar-fill.low { background: var(--danger); }
        .knowledge-item .bar-fill.medium { background: var(--warning); }
        .knowledge-item .bar-fill.high { background: var(--success); }
        .knowledge-item .value { min-width: 45px; text-align: right; font-size: 0.9rem; color: var(--text-light); font-weight: 600; }
        /* 快捷入口 */
        .quick-links { background: var(--card); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); display: flex; gap: 20px; flex-wrap: wrap; justify-content: space-evenly; }
        .quick-link { display: flex; align-items: center; gap: 8px; padding: 16px 32px; background: #f8fafc; border-radius: 10px; text-decoration: none; color: var(--text); font-weight: 500; font-size: 1rem; transition: all 0.2s; }
        .quick-link:hover { background: #e2e8f0; transform: translateY(-2px); }
        .quick-link.warning { color: var(--danger); }
        .quick-link.warning:hover { background: #fef2f2; }
        .quick-link.info { color: var(--info); }
        .quick-link.info:hover { background: #f0f9ff; }
        /* 虚拟键盘 */
        .ML__keyboard { z-index: 1000 !important; }
        /* 完成页面 */
        .complete-card { text-align: center; padding: 40px; background: var(--card); border-radius: var(--radius); box-shadow: var(--shadow); }
        .complete-card h3 { font-size: 1.5rem; margin-bottom: 20px; }
        .complete-card p { font-size: 1.2rem; margin: 20px 0; }
        .complete-card .btn-group { margin-top: 30px; display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }
        .complete-card .btn-group a { padding: 14px 28px; text-decoration: none; border-radius: 10px; font-weight: 600; transition: all 0.2s; }
        .complete-card .btn-green { background: var(--success); color: white; }
        .complete-card .btn-green:hover { background: #059669; transform: translateY(-2px); }
        .complete-card .btn-gray { background: var(--text-light); color: white; }
        .complete-card .btn-gray:hover { background: #475569; transform: translateY(-2px); }
        .complete-card .tip { margin-top: 20px; color: var(--text-light); font-size: 0.9rem; }
        /* 响应式 */
        @media (max-width: 600px) {
            .stats-section { grid-template-columns: repeat(2, 1fr); }
            .question-header { flex-direction: column; gap: 12px; text-align: center; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 顶部导航 -->
        <nav class="navbar">
            <h1>🎓 考研数学·智能刷题</h1>
            <div class="user-info">
                {% if logged_in and username %}
                    <span>欢迎，{{ username }}</span>
                    <a href="/logout">退出</a>
                {% else %}
                    <span>欢迎回来，{{ user_id }}</span>
                    <a href="/login">登录</a> / <a href="/register">注册</a>
                {% endif %}
            </div>
        </nav>

        <!-- 题库切换 -->
        <div class="subject-selector">
            <label>当前题库：</label>
            <form method="post" action="/select_subject" style="flex:1;">
                <select name="subject" id="subject" onchange="this.form.submit()">
                    <option value="高等数学" {% if current_subject == '高等数学' %}selected{% endif %}>高等数学</option>
                    <option value="线性代数" {% if current_subject == '线性代数' %}selected{% endif %}>线性代数</option>
                    <option value="概率论" {% if current_subject == '概率论' %}selected{% endif %}>概率论</option>
                </select>
            </form>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="feedback {{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

    {% if question %}
        <!-- 题目卡片 -->
        <div class="question-card">
            <div class="question-header">
                <div class="meta">
                    <span class="subject-tag">{{ question.subject }}</span>
                    <span>{{ question.chapter }}</span>
                    <span class="difficulty">难度 {{ question.difficulty }}</span>
                </div>
                <button type="button" onclick="toggleFavorite('{{ question.id }}', event)" id="fav-btn" class="fav-btn {% if is_favorite %}active{% endif %}">
                    {% if is_favorite %}★ 已收藏{% else %}☆ 收藏{% endif %}
                </button>
            </div>
            <div class="question-body">
                <p class="question-text">{{ question.question_text | safe }}</p>

                <form method="post" action="/answer" id="answerForm">
                    <input type="hidden" name="qid" value="{{ question.id }}">
                    <div class="answer-section">
                        <h4>请输入答案</h4>
                        {% if question.type == 'multiple_choice' %}
                            <div class="option-list">
                                {% for option in question.options %}
                                <label class="option-item">
                                    <input type="radio" name="answer" value="{{ loop.index0 }}">
                                    <span class="option-text">{{ option | safe }}</span>
                                </label>
                                {% endfor %}
                            </div>
                        {% elif question.type == 'essay' %}
                            <div style="border: 1px solid var(--warning); border-radius: 8px; padding: 16px; background: #fffbeb;">
                                <p style="color: #92400e; margin: 0;">
                                    <strong>⚠️ 此题为证明题/简答题</strong><br>
                                    请在纸上写出解答过程，查看正确答案对照批改。
                                </p>
                            </div>
                            <input type="hidden" name="answer" value="essay_skip">
                        {% else %}
                            <div class="formula-input-wrapper">
                                <math-field id="formulaInput" virtual-keyboard-mode="onfocus"></math-field>
                                <input type="hidden" name="answer" id="formulaAnswer">
                                <p class="input-preview">预览：<span id="formulaPreview"></span></p>
                                <p class="input-hint">💡 点击输入框使用虚拟键盘，或直接输入 LaTeX 语法如 \frac{1}{2}, \sqrt{x}</p>
                            </div>
                        {% endif %}
                        <button type="submit" class="submit-btn">提交</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- 统计卡片 -->
        <div class="stats-section">
            <div class="stat-card blue">
                <div class="icon">📚</div>
                <div class="value">{{ total_answered }}</div>
                <div class="label">已做题数</div>
            </div>
            <div class="stat-card green">
                <div class="icon">✅</div>
                <div class="value">{{ (correct_count / total_answered * 100) | round(1) if total_answered > 0 else 0 }}%</div>
                <div class="label">正确率</div>
            </div>
            <div class="stat-card red">
                <div class="icon">❌</div>
                <div class="value">{{ wrong_count }}</div>
                <div class="label">错题数</div>
            </div>
            <div class="stat-card yellow">
                <div class="icon">⭐</div>
                <div class="value"><span id="fav-count">{{ favorites_count }}</span></div>
                <div class="label">收藏数</div>
            </div>
        </div>

        <!-- 快捷入口 -->
        <div class="quick-links">
            {% if wrong_count > 0 %}
            <a href="/review_wrong" class="quick-link warning">❌ 复习错题</a>
            {% endif %}
            {% if due_count > 0 %}
            <a href="/review_due" class="quick-link info">📅 今日复习</a>
            {% endif %}
            <a href="/favorites" class="quick-link">⭐ 查看收藏</a>
            <a href="/stats" class="quick-link">📈 学习统计</a>
        </div>
    {% else %}
        <div class="complete-card">
            <h3>🎉 恭喜！你已经完成了当前题库的所有题目！</h3>
            <p>共完成 <strong>{{ total_questions }}</strong> 题 · 正确率 <strong>{{ (correct_count / total_answered * 100) | round(1) if total_answered > 0 else 0 }}%</strong></p>
            <div class="btn-group">
                <a href="/restart" class="btn-green">再来一遍（保留掌握度）</a>
                <a href="/reset" class="btn-gray" onclick="return confirm('确定要完全重置吗？所有做题记录、错题、收藏等数据都将被清空，且无法恢复！')">完全重置（清空所有进度）</a>
            </div>
            <p class="tip">保留掌握度：你学会的知识点不会丢失，可以更高效地复习。</p>
        </div>
    {% endif %}
    </div>

    <p style="margin-top: 30px;"><a href="/reset" onclick="return confirm('确定要完全重置吗？所有做题记录、错题、收藏等数据都将被清空，且无法恢复！')">重置我的进度</a></p>
    <script>
        // Toggle favorite without page refresh
        function toggleFavorite(qid, event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            fetch('/favorite/toggle/' + qid)
                .then(response => response.json())
                .then(data => {
                    const btn = document.getElementById('fav-btn');
                    const countEl = document.getElementById('fav-count');
                    let currentCount = parseInt(countEl.textContent);

                    if (data.action === 'added') {
                        btn.innerHTML = '★ 已收藏';
                        btn.classList.add('active');
                        countEl.textContent = currentCount + 1;
                    } else {
                        btn.innerHTML = '☆ 收藏';
                        btn.classList.remove('active');
                        countEl.textContent = currentCount - 1;
                    }
                })
                .catch(err => console.error('Error:', err));
        }

        // Wait for MathLive to load
        function initMathLive() {
            // Render KaTeX
            if (typeof renderMathInElement !== 'undefined') {
                console.log("KaTeX render start"), renderMathInElement(document.body, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '\\(', right: '\\)', display: false},
                        {left: '$', right: '$', display: false}
                    ],
                    throwOnError: false
                });
            }

            // Wait for math-field and set up preview
            function setupMathField() {
                const mf = document.getElementById('formulaInput');
                const preview = document.getElementById('formulaPreview');
                const hiddenInput = document.getElementById('formulaAnswer');

                if (mf && preview && hiddenInput) {
                    // Update preview and hidden input when input changes
                    mf.addEventListener('input', function(evt) {
                        const latex = mf.value;
                        // Update hidden input for form submission
                        hiddenInput.value = latex;
                        // Update preview
                        if (latex) {
                            try {
                                preview.innerHTML = '$$' + latex + '$$';
                                renderMathInElement(preview, {
                                    delimiters: [
                                        {left: '$$', right: '$$', display: true}
                                    ],
                                    throwOnError: false
                                });
                            } catch(e) {
                                preview.textContent = latex;
                            }
                        } else {
                            preview.textContent = '(无)';
                        }
                    });

                    // Initial preview
                    const initialLatex = mf.value;
                    hiddenInput.value = initialLatex;
                    if (initialLatex) {
                        preview.innerHTML = '$$' + initialLatex + '$$';
                        renderMathInElement(preview, {
                            delimiters: [{left: '$$', right: '$$', display: true}],
                            throwOnError: false
                        });
                    }
                    console.log('MathLive initialized successfully');
                } else {
                    setTimeout(setupMathField, 200);
                }
            }
            setupMathField();

            // Handle form submission - ensure hidden input has the value
            const form = document.getElementById('answerForm');
            if (form) {
                form.addEventListener('submit', function() {
                    const mf = document.getElementById('formulaInput');
                    const hiddenInput = document.getElementById('formulaAnswer');
                    if (mf && hiddenInput) {
                        hiddenInput.value = mf.value;
                        console.log('Submitting answer:', hiddenInput.value);
                    }
                });
            }
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initMathLive);
        } else {
            initMathLive();
        }
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

    # Shuffle options for multiple choice questions
    if question and question.get('type') == 'multiple_choice':
        import random
        options = question.get('options', [])
        correct_idx = question.get('correct_option', 0)
        # Create list of (index, option) pairs
        indexed_options = list(enumerate(options))
        # Shuffle
        random.shuffle(indexed_options)
        # Find new correct index
        new_correct = None
        shuffled_options = []
        for new_idx, (old_idx, opt) in enumerate(indexed_options):
            shuffled_options.append(opt)
            if old_idx == correct_idx:
                new_correct = new_idx
        question['options'] = shuffled_options
        question['correct_option'] = new_correct

    subject_answered = user.answered_questions & current_qids
    total_answered = len(subject_answered)
    subject_correct_in_round = user.correct_in_round & current_qids
    correct_count = len(subject_correct_in_round)
    total_questions = len(questions)
    wrong_count = user.get_wrong_count(questions)
    due_count = user.get_due_count(questions)
    favorites_count = user.get_favorite_count()

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
        is_favorite=user.is_favorite(question['id']) if question else False,
        knowledge=user.knowledge_state,
        total_answered=total_answered,
        correct_count=correct_count,
        total_questions=total_questions,
        wrong_count=wrong_count,
        due_count=due_count,
        favorites_count=favorites_count,
        user_id=display_id,
        current_subject=current_subject,
        logged_in=current_user.is_authenticated,
        username=current_user.username if current_user.is_authenticated else None
    )


@app.route('/answer', methods=['POST'])
def answer():
    """Process user answer submission."""
    user = get_current_user()
    qid = request.form.get('qid', '')
    user_answer = request.form.get('answer', '').strip()

    print(f"[DEBUG] qid={qid}, user_answer={repr(user_answer)}")

    question = next((q for q in questions if q.get('id') == qid), None)
    if not question:
        flash("题目不存在，请重试", "wrong")
        return redirect(url_for('index'))

    print(f"[DEBUG] question_answer={repr(question.get('answer'))}, type={question.get('answer_type')}")

    is_correct = check_answer(question, user_answer)
    print(f"[DEBUG] is_correct={is_correct}")

    if is_correct:
        flash("回答正确！", "correct")
        user.correct_in_round.add(qid)
    else:
        flash(f"回答错误。正确答案：{question.get('answer', '')}", "wrong")

    # 记录答题历史
    history_entry = {
        "qid": qid,
        "user_answer": user_answer,
        "correct": is_correct,
        "timestamp": datetime.now().isoformat()
    }

    # 如果答对了，初始化艾宾浩斯复习时间
    if is_correct:
        from bkt_core import calculate_next_review_interval
        history_entry['review_count'] = 0
        history_entry['last_reviewed'] = datetime.now().isoformat()
        interval = calculate_next_review_interval(0)
        history_entry['next_review'] = (datetime.now() + timedelta(days=interval)).isoformat()

    user.history.append(history_entry)

    for kc in question.get('knowledge_tags', ['default']):
        old_p = user.knowledge_state.get(kc, engine.default_mastery)
        new_p = engine.update_mastery(old_p, is_correct)
        user.knowledge_state[kc] = new_p

    user.answered_questions.add(qid)

    # 记录学习统计
    today = datetime.now().strftime('%Y-%m-%d')
    user.record_daily_stats(today, 1, 1 if is_correct else 0)
    user.update_total_stats()

    user.save_to_file()
    user.record_interaction(qid, is_correct)

    return redirect(url_for('index'))


# 错题复习页面模板
REVIEW_WRONG_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>错题复习 - 智能刷题</title>
    <link rel="stylesheet" href="https://cdn.staticfile.org/KaTeX/0.16.10/katex.min.css"
          integrity="sha384-wcIxkf4k558AjM3Yz3BBFQUbk/zgIYC2R0QpeeYb+TwlBVMrlgLqwRjRtGZiK7ww"
          crossorigin="anonymous">
    <script defer src="https://cdn.staticfile.org/KaTeX/0.16.10/katex.min.js"
            integrity="sha384-hIoBPJpTUs74ddyc4bFZSM1TVlQDA60VBbJS0oA934VSz82sBx1X7kSx2ATBDIyd"
            crossorigin="anonymous"></script>
    <script defer src="https://cdn.staticfile.org/KaTeX/0.16.10/contrib/auto-render.min.js"
            integrity="sha384-43gviWU0YVjaDtb/GhzOouOXtZMP/7XUzwPTstBeZFe/+rCMvRwr4yROQP43s0Xk"
            crossorigin="anonymous"></script>
    <script defer src="https://unpkg.com/mathlive@0.100.0/dist/mathlive.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
        .question-card { background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .question-card h3 { margin-top: 0; color: #333; }
        .question-text { font-size: 1.1rem; margin: 15px 0; }
        .chapter { color: #6c757d; font-size: 0.9rem; }
        .difficulty { color: #007bff; }
        .answer-form { margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; }
        .feedback { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
        .correct { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .wrong { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        button[type="submit"] { padding: 8px 20px;
                               background: #007bff; color: white; border: none;
                               border-radius: 4px; cursor: pointer; font-size: 1rem; }
        button[type="submit"]:hover { background: #0056b3; }
        .back-link { display: inline-block; margin-bottom: 20px; color: #007bff; }
        math-field.math-field-input {
            font-size: 1.2rem;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            min-width: 300px;
            margin-right: 10px;
            display: inline-block;
            vertical-align: middle;
        }
        .input-hint {
            font-size: 0.85rem;
            color: #6c757d;
            margin-top: 4px;
        }
    </style>
</head>
<body>
    <a href="/" class="back-link">← 返回主页</a>
    <h2>错题复习 - {{ current_subject }}</h2>
    <p>共 <strong style="color: #dc3545;">{{ questions|length }}</strong> 道错题需要复习</p>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="feedback {{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    {% if current_question %}
        <div class="question-card">
            <h3>第 {{ loop_index }} 题</h3>
            <p class="chapter">{{ current_question.chapter }} · 难度 {{ current_question.difficulty }}</p>
            <p class="question-text">{{ current_question.question_text | safe }}</p>

            <form method="post" action="/answer_review" style="margin-top: 20px;" id="answerForm">
                <input type="hidden" name="qid" value="{{ current_question.id }}">
                {% if current_question.type == 'multiple_choice' %}
                    <div style="margin: 15px 0;">
                        {% for option in current_question.options %}
                        <label style="display: block; padding: 10px 15px; margin: 8px 0;
                                     border: 1px solid #ddd; border-radius: 6px; cursor: pointer;
                                     transition: all 0.2s; background: white;"
                               onmouseover="this.style.borderColor='#007bff';this.style.background='#f0f7ff';"
                               onmouseout="this.style.borderColor='#ddd';this.style.background='white';">
                            <input type="radio" name="answer" value="{{ loop.index0 }}" style="margin-right: 10px;">
                            <span style="vertical-align: middle;">{{ option | safe }}</span>
                        </label>
                        {% endfor %}
                    </div>
                {% else %}
                    <div style="border: 1px solid #ddd; border-radius: 4px; padding: 10px; background: white;">
                        <math-field id="formulaInput"
                                   virtual-keyboard-mode="onfocus"
                                   class="math-field-input"></math-field>
                        <input type="hidden" name="answer" id="formulaAnswer">
                        <p class="input-hint">预览：<span id="formulaPreview"></span></p>
                    </div>
                {% endif %}
                <button type="submit" style="margin-top: 15px;">提交答案</button>
            </form>
        </div>

        <div style="margin-top: 20px; color: #6c757d;">
            剩余错题: {{ remaining }} 道
        </div>
    {% else %}
        <div style="text-align: center; padding: 40px; background: #d4edda; border-radius: 8px;">
            <h3>🎉 恭喜！错题已经全部复习完毕！</h3>
            <p>你已掌握所有错题对应的知识点</p>
            <a href="/" style="display: inline-block; margin-top: 20px; padding: 10px 20px;
                              background: #28a745; color: white; text-decoration: none; border-radius: 4px;">
                返回主页
            </a>
        </div>
    {% endif %}

    <script>
        function initMathLive() {
            if (typeof renderMathInElement !== 'undefined') {
                console.log("KaTeX render start"), renderMathInElement(document.body, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '\\(', right: '\\)', display: false},
                        {left: '$', right: '$', display: false}
                    ],
                    throwOnError: false
                });
            }

            function setupMathField() {
                const mf = document.getElementById('formulaInput');
                const preview = document.getElementById('formulaPreview');
                const hiddenInput = document.getElementById('formulaAnswer');

                if (mf && preview && hiddenInput) {
                    mf.addEventListener('input', function(evt) {
                        const latex = mf.value;
                        hiddenInput.value = latex;
                        if (latex) {
                            try {
                                preview.innerHTML = '$$' + latex + '$$';
                                renderMathInElement(preview, {
                                    delimiters: [{left: '$$', right: '$$', display: true}],
                                    throwOnError: false
                                });
                            } catch(e) {
                                preview.textContent = latex;
                            }
                        } else {
                            preview.textContent = '(无)';
                        }
                    });

                    const initialLatex = mf.value;
                    hiddenInput.value = initialLatex;
                    if (initialLatex) {
                        preview.innerHTML = '$$' + initialLatex + '$$';
                        renderMathInElement(preview, {
                            delimiters: [{left: '$$', right: '$$', display: true}],
                            throwOnError: false
                        });
                    }
                } else {
                    setTimeout(setupMathField, 200);
                }
            }
            setupMathField();

            const form = document.getElementById('answerForm');
            if (form) {
                form.addEventListener('submit', function() {
                    const mf = document.getElementById('formulaInput');
                    const hiddenInput = document.getElementById('formulaAnswer');
                    if (mf && hiddenInput) {
                        hiddenInput.value = mf.value;
                    }
                });
            }
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initMathLive);
        } else {
            initMathLive();
        }
    </script>
</body>
</html>
'''


@app.route('/review_wrong')
def review_wrong():
    """错题复习页面 - 显示错题列表供用户选择"""
    user = get_current_user()
    wrong_questions = user.get_wrong_questions(questions)

    if not wrong_questions:
        flash("恭喜！当前科目没有错题需要复习", "correct")
        return redirect(url_for('index'))

    # 获取当前要复习的题目（从session中获取选择）
    selected_qid = session.get('review_qid')
    if selected_qid:
        current_question = next((q for q in wrong_questions if q['id'] == selected_qid), None)
    else:
        current_question = wrong_questions[0] if wrong_questions else None

    if current_question:
        # 记录当前正在复习的题目ID
        session['review_qid'] = current_question['id']
        # 打乱选择题选项
        if current_question.get('type') == 'multiple_choice':
            import random
            options = current_question.get('options', [])
            correct_idx = current_question.get('correct_option', 0)
            indexed_options = list(enumerate(options))
            random.shuffle(indexed_options)
            new_correct = None
            shuffled_options = []
            for new_idx, (old_idx, opt) in enumerate(indexed_options):
                shuffled_options.append(opt)
                if old_idx == correct_idx:
                    new_correct = new_idx
            current_question['options'] = shuffled_options
            current_question['correct_option'] = new_correct

        loop_index = wrong_questions.index(current_question) + 1
    else:
        loop_index = 1

    remaining = len(wrong_questions)

    return render_template_string(
        REVIEW_WRONG_HTML,
        questions=wrong_questions,
        current_question=current_question,
        current_subject=current_subject,
        loop_index=loop_index,
        remaining=remaining
    )


@app.route('/answer_review', methods=['POST'])
def answer_review():
    """错题复习答题提交 - 答对后从错题列表中移除"""
    user = get_current_user()
    qid = request.form.get('qid', '')
    user_answer = request.form.get('answer', '').strip()

    question = next((q for q in questions if q.get('id') == qid), None)
    if not question:
        flash("题目不存在", "wrong")
        return redirect(url_for('review_wrong'))

    is_correct = check_answer(question, user_answer)

    if is_correct:
        # 答对了，标记为已复习
        user.mark_reviewed(qid)
        flash("回答正确！该题已从错题本中移除", "correct")
        # 清除当前复习的题目ID
        session.pop('review_qid', None)
        # 保存用户数据
        user.save_to_file()
    else:
        flash(f"回答错误。正确答案：{question.get('answer', '')}", "wrong")
        # 继续复习这道题

    # 刷新错题列表，检查是否还有剩余
    wrong_questions = user.get_wrong_questions(questions)
    if not wrong_questions:
        # 全部复习完毕
        return redirect(url_for('index'))

    # 继续复习下一题或当前题
    return redirect(url_for('review_wrong'))


# 艾宾浩斯复习页面模板
REVIEW_DUE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>艾宾浩斯复习 - 智能刷题</title>
    <link rel="stylesheet" href="https://cdn.staticfile.org/KaTeX/0.16.10/katex.min.css"
          integrity="sha384-wcIxkf4k558AjM3Yz3BBFQUbk/zgIYC2R0QpeeYb+TwlBVMrlgLqwRjRtGZiK7ww"
          crossorigin="anonymous">
    <script defer src="https://cdn.staticfile.org/KaTeX/0.16.10/katex.min.js"
            integrity="sha384-hIoBPJpTUs74ddyc4bFZSM1TVlQDA60VBbJS0oA934VSz82sBx1X7kSx2ATBDIyd"
            crossorigin="anonymous"></script>
    <script defer src="https://cdn.staticfile.org/KaTeX/0.16.10/contrib/auto-render.min.js"
            integrity="sha384-43gviWU0YVjaDtb/GhzOouOXtZMP/7XUzwPTstBeZFe/+rCMvRwr4yROQP43s0Xk"
            crossorigin="anonymous"></script>
    <script defer src="https://unpkg.com/mathlive@0.100.0/dist/mathlive.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
        .question-card { background: #fff3cd; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .question-card h3 { margin-top: 0; color: #333; }
        .question-text { font-size: 1.1rem; margin: 15px 0; }
        .chapter { color: #6c757d; font-size: 0.9rem; }
        .difficulty { color: #007bff; }
        .progress-info { background: #e9ecef; padding: 15px; border-radius: 6px; margin-top: 15px; }
        .progress-info p { margin: 5px 0; }
        .feedback { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
        .correct { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .wrong { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        button[type="submit"] { padding: 8px 20px;
                               background: #ffc107; color: #212529; border: none;
                               border-radius: 4px; cursor: pointer; font-size: 1rem; }
        button[type="submit"]:hover { background: #e0a800; }
        .back-link { display: inline-block; margin-bottom: 20px; color: #007bff; }
        math-field.math-field-input {
            font-size: 1.2rem;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            min-width: 300px;
            margin-right: 10px;
            display: inline-block;
            vertical-align: middle;
        }
        .input-hint {
            font-size: 0.85rem;
            color: #6c757d;
            margin-top: 4px;
        }
    </style>
</head>
<body>
    <a href="/" class="back-link">← 返回主页</a>
    <h2>📅 艾宾浩斯复习 - {{ current_subject }}</h2>
    <p>今日需要复习 <strong style="color: #ffc107;">{{ questions|length }}</strong> 道题目</p>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="feedback {{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    {% if current_question %}
        <div class="question-card">
            <h3>第 {{ loop_index }} 题</h3>
            <p class="chapter">{{ current_question.chapter }} · 难度 {{ current_question.difficulty }}</p>
            <p class="question-text">{{ current_question.question_text | safe }}</p>

            <div class="progress-info">
                <p>📈 复习进度: 第 <strong>{{ review_count }}</strong> 次 / 共 5 次</p>
                <p>⏰ 下次复习: <strong>{{ next_interval }}</strong> 天后</p>
            </div>

            <form method="post" action="/answer_due" style="margin-top: 20px;" id="answerForm">
                <input type="hidden" name="qid" value="{{ current_question.id }}">
                {% if current_question.type == 'multiple_choice' %}
                    <div style="margin: 15px 0;">
                        {% for option in current_question.options %}
                        <label style="display: block; padding: 10px 15px; margin: 8px 0;
                                     border: 1px solid #ddd; border-radius: 6px; cursor: pointer;
                                     transition: all 0.2s; background: white;"
                               onmouseover="this.style.borderColor='#ffc107';this.style.background='#fff8e6';"
                               onmouseout="this.style.borderColor='#ddd';this.style.background='white';">
                            <input type="radio" name="answer" value="{{ loop.index0 }}" style="margin-right: 10px;">
                            <span style="vertical-align: middle;">{{ option | safe }}</span>
                        </label>
                        {% endfor %}
                    </div>
                {% else %}
                    <div style="border: 1px solid #ddd; border-radius: 4px; padding: 10px; background: white;">
                        <math-field id="formulaInput"
                                   virtual-keyboard-mode="onfocus"
                                   class="math-field-input"></math-field>
                        <input type="hidden" name="answer" id="formulaAnswer">
                        <p class="input-hint">预览：<span id="formulaPreview"></span></p>
                    </div>
                {% endif %}
                <button type="submit" style="margin-top: 15px;">提交答案</button>
            </form>
        </div>

        <div style="margin-top: 20px; color: #6c757d;">
            剩余复习: {{ remaining }} 道
        </div>
    {% else %}
        <div style="text-align: center; padding: 40px; background: #d4edda; border-radius: 8px;">
            <h3>🎉 今日复习任务已完成！</h3>
            <p>记得明天再来复习，巩固记忆效果更好～</p>
            <a href="/" style="display: inline-block; margin-top: 20px; padding: 10px 20px;
                              background: #28a745; color: white; text-decoration: none; border-radius: 4px;">
                返回主页
            </a>
        </div>
    {% endif %}

    <script>
        function initMathLive() {
            if (typeof renderMathInElement !== 'undefined') {
                console.log("KaTeX render start"), renderMathInElement(document.body, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '\\(', right: '\\)', display: false},
                        {left: '$', right: '$', display: false}
                    ],
                    throwOnError: false
                });
            }

            function setupMathField() {
                const mf = document.getElementById('formulaInput');
                const preview = document.getElementById('formulaPreview');
                const hiddenInput = document.getElementById('formulaAnswer');

                if (mf && preview && hiddenInput) {
                    mf.addEventListener('input', function(evt) {
                        const latex = mf.value;
                        hiddenInput.value = latex;
                        if (latex) {
                            try {
                                preview.innerHTML = '$$' + latex + '$$';
                                renderMathInElement(preview, {
                                    delimiters: [{left: '$$', right: '$$', display: true}],
                                    throwOnError: false
                                });
                            } catch(e) {
                                preview.textContent = latex;
                            }
                        } else {
                            preview.textContent = '(无)';
                        }
                    });

                    const initialLatex = mf.value;
                    hiddenInput.value = initialLatex;
                    if (initialLatex) {
                        preview.innerHTML = '$$' + initialLatex + '$$';
                        renderMathInElement(preview, {
                            delimiters: [{left: '$$', right: '$$', display: true}],
                            throwOnError: false
                        });
                    }
                } else {
                    setTimeout(setupMathField, 200);
                }
            }
            setupMathField();

            const form = document.getElementById('answerForm');
            if (form) {
                form.addEventListener('submit', function() {
                    const mf = document.getElementById('formulaInput');
                    const hiddenInput = document.getElementById('formulaAnswer');
                    if (mf && hiddenInput) {
                        hiddenInput.value = mf.value;
                    }
                });
            }
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initMathLive);
        } else {
            initMathLive();
        }
    </script>
</body>
</html>
'''


@app.route('/review_due')
def review_due():
    """艾宾浩斯复习页面 - 显示到期需要复习的题目"""
    user = get_current_user()
    due_questions = user.get_due_questions(questions)

    if not due_questions:
        flash("暂无需要复习的题目，继续保持！", "correct")
        return redirect(url_for('index'))

    # 获取当前要复习的题目
    selected_qid = session.get('due_qid')
    if selected_qid:
        current_question = next((q for q in due_questions if q['id'] == selected_qid), None)
    else:
        current_question = due_questions[0] if due_questions else None

    if current_question:
        session['due_qid'] = current_question['id']

        # 获取复习进度
        progress = user.get_review_progress(current_question['id'])
        review_count = progress['review_count'] if progress else 0

        # 计算下次复习间隔
        from bkt_core import calculate_next_review_interval
        next_interval = calculate_next_review_interval(review_count)

        # 打乱选择题选项
        if current_question.get('type') == 'multiple_choice':
            import random
            options = current_question.get('options', [])
            correct_idx = current_question.get('correct_option', 0)
            indexed_options = list(enumerate(options))
            random.shuffle(indexed_options)
            new_correct = None
            shuffled_options = []
            for new_idx, (old_idx, opt) in enumerate(indexed_options):
                shuffled_options.append(opt)
                if old_idx == correct_idx:
                    new_correct = new_idx
            current_question['options'] = shuffled_options
            current_question['correct_option'] = new_correct

        loop_index = due_questions.index(current_question) + 1
    else:
        review_count = 0
        next_interval = 1
        loop_index = 1

    remaining = len(due_questions)

    return render_template_string(
        REVIEW_DUE_HTML,
        questions=due_questions,
        current_question=current_question,
        current_subject=current_subject,
        review_count=review_count,
        next_interval=next_interval,
        loop_index=loop_index,
        remaining=remaining
    )


@app.route('/answer_due', methods=['POST'])
def answer_due():
    """艾宾浩斯复习答题提交"""
    user = get_current_user()
    qid = request.form.get('qid', '')
    user_answer = request.form.get('answer', '').strip()

    question = next((q for q in questions if q.get('id') == qid), None)
    if not question:
        flash("题目不存在", "wrong")
        return redirect(url_for('review_due'))

    is_correct = check_answer(question, user_answer)

    if is_correct:
        user.update_review_status(qid, True)
        flash("回答正确！记忆加深，下次复习时间已更新", "correct")
        session.pop('due_qid', None)
    else:
        user.update_review_status(qid, False)
        flash(f"回答错误。正确答案：{question.get('answer', '')}，复习周期已重置", "wrong")

    user.save_to_file()

    # 检查是否还有到期题目
    due_questions = user.get_due_questions(questions)
    if not due_questions:
        return redirect(url_for('index'))

    return redirect(url_for('review_due'))


# ==================== 收藏功能 ====================

FAVORITES_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>收藏题目 - 智能刷题</title>
    <link rel="stylesheet" href="https://cdn.staticfile.org/KaTeX/0.16.10/katex.min.css">
    <script defer src="https://cdn.staticfile.org/KaTeX/0.16.10/katex.min.js"></script>
    <script defer src="https://cdn.staticfile.org/KaTeX/0.16.10/contrib/auto-render.min.js"></script>
    <!-- v3 - cache test -->
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               max-width: 800px; margin: 40px auto; padding: 20px; }
        h2 { margin-bottom: 20px; }
        .favorite-item {
            background: #f8f9fa; padding: 15px; margin-bottom: 15px;
            border-radius: 8px; border-left: 4px solid #ffc107;
        }
        .favorite-item h3 { margin: 0 0 10px 0; font-size: 1rem; }
        .favorite-item .note { color: #666; font-size: 0.9rem; margin-bottom: 10px; }
        .favorite-item .actions a {
            padding: 5px 15px; margin-right: 10px; text-decoration: none;
            border-radius: 4px; font-size: 0.9rem;
        }
        .btn-do { background: #007bff; color: white; }
        .btn-remove { background: #dc3545; color: white; }
        .back-link { display: inline-block; margin-bottom: 20px; color: #007bff; }
        .empty { text-align: center; padding: 40px; color: #666; }
    </style>
</head>
<body>
    <a href="/" class="back-link">← 返回主页</a>
    <h2>⭐ 我的收藏</h2>

    {% if favorites %}
        {% for fav in favorites %}
        <div class="favorite-item">
            <h3>{{ fav.chapter }} · 难度 {{ fav.difficulty }}</h3>
            <p>{{ fav.question_text | safe }}</p>
            {% if fav.note %}
            <p class="note">📝 {{ fav.note }}</p>
            {% endif %}
            <div class="actions">
                <a href="/practice/{{ fav.id }}" class="btn-do">开始做题</a>
                <a href="/favorite/remove/{{ fav.id }}" class="btn-remove">取消收藏</a>
            </div>
        </div>
        {% endfor %}
    {% else %}
        <div class="empty">
            <p>还没有收藏任何题目</p>
            <p>做题时点击收藏按钮即可收藏</p>
        </div>
    {% endif %}

    <script>
        function initMath() {
            console.log('KaTeX init start');
            if (typeof renderMathInElement !== 'undefined') {
                console.log('renderMathInElement found, rendering...');
                try {
                    console.log("KaTeX render start"), renderMathInElement(document.body, {
                        delimiters: [
                            {left: '$$', right: '$$', display: true},
                            {left: '\\(', right: '\\)', display: false},
                            {left: '$', right: '$', display: false}
                        ],
                        throwOnError: false
                    });
                    console.log('KaTeX render done');
                } catch(e) {
                    console.error('KaTeX error:', e);
                }
            } else {
                console.error('renderMathInElement NOT found!');
            }
        }
        document.addEventListener('DOMContentLoaded', initMath);
        initMath();
    </script>
</body>
</html>
'''


@app.route('/favorites')
def favorites():
    """收藏列表页面"""
    user = get_current_user()
    fav_questions = user.get_favorite_questions(questions)

    # 添加备注信息
    favorites_with_notes = []
    for q in fav_questions:
        q_copy = q.copy()
        q_copy['note'] = user.get_favorite_note(q['id'])
        favorites_with_notes.append(q_copy)

    return render_template_string(
        FAVORITES_HTML,
        favorites=favorites_with_notes
    )


@app.route('/favorite/add/<qid>')
def favorite_add(qid: str):
    """添加收藏"""
    user = get_current_user()
    user.add_favorite(qid)
    user.save_to_file()
    flash("已收藏", "correct")
    return redirect(url_for('index'))


@app.route('/favorite/remove/<qid>')
def favorite_remove(qid: str):
    """取消收藏"""
    user = get_current_user()
    user.remove_favorite(qid)
    user.save_to_file()
    flash("已取消收藏", "correct")
    return redirect(url_for('favorites'))


@app.route('/favorite/toggle/<qid>')
def favorite_toggle(qid: str):
    """切换收藏状态（AJAX接口）"""
    user = get_current_user()
    if user.is_favorite(qid):
        user.remove_favorite(qid)
        user.save_to_file()
        return jsonify({'action': 'removed', 'status': 'ok'})
    else:
        user.add_favorite(qid)
        user.save_to_file()
        return jsonify({'action': 'added', 'status': 'ok'})


# ==================== 学习统计 ====================

STATS_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>学习统计 - 智能刷题</title>
    <script src="https://unpkg.com/chart.js@4.4.1/dist/chart.umd.js"></script>
    <style>
        :root {
            --primary: #3b82f6;
            --primary-dark: #1d4ed8;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --bg: #f1f5f9;
            --card: #ffffff;
            --text: #1e293b;
            --text-light: #64748b;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            --radius: 16px;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: var(--bg); color: var(--text); min-height: 100vh; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .back-link { display: inline-block; margin-bottom: 20px; color: var(--primary); text-decoration: none; font-weight: 500; }
        .back-link:hover { color: var(--primary-dark); }
        h2 { margin-bottom: 20px; font-size: 1.5rem; }
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 24px; }
        .stat-card {
            background: var(--card); padding: 24px; border-radius: var(--radius); text-align: center;
            box-shadow: var(--shadow); border-top: 4px solid var(--primary);
        }
        .stat-card .number { font-size: 2rem; font-weight: 700; color: var(--primary); }
        .stat-card .label { color: var(--text-light); margin-top: 8px; font-size: 0.9rem; }
        .streak-card { background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%); color: white; border-top: none; }
        .streak-card .number { color: white; }
        .streak-card .label { color: rgba(255,255,255,0.8); }
        .chart-container { background: var(--card); padding: 24px; border-radius: var(--radius); margin-bottom: 24px; box-shadow: var(--shadow); }
        .chart-container h3 { margin-bottom: 16px; font-size: 1.1rem; }
        .knowledge-section { background: var(--card); border-radius: var(--radius); padding: 24px; box-shadow: var(--shadow); }
        .knowledge-section h3 { margin-bottom: 20px; font-size: 1.1rem; }
        .knowledge-list { display: flex; flex-direction: column; gap: 16px; }
        .knowledge-item { display: flex; align-items: center; gap: 12px; }
        .knowledge-item .name { min-width: 80px; font-weight: 500; font-size: 0.95rem; }
        .knowledge-item .bar { flex: 1; height: 14px; background: #e2e8f0; border-radius: 7px; overflow: hidden; }
        .knowledge-item .bar-fill { height: 100%; border-radius: 7px; transition: width 0.5s ease; }
        .knowledge-item .bar-fill.low { background: var(--danger); }
        .knowledge-item .bar-fill.medium { background: var(--warning); }
        .knowledge-item .bar-fill.high { background: var(--success); }
        .knowledge-item .value { min-width: 50px; text-align: right; font-size: 0.9rem; color: var(--text-light); font-weight: 600; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← 返回主页</a>
        <h2>📊 学习统计</h2>

    <div class="stats-grid">
        <div class="stat-card streak-card">
            <div class="number">{{ total_stats.streak_days }}</div>
            <div class="label">连续学习天数</div>
        </div>
        <div class="stat-card">
            <div class="number">{{ total_stats.total_answered }}</div>
            <div class="label">累计做题数</div>
        </div>
        <div class="stat-card">
            <div class="number">{{ total_stats.total_correct }}</div>
            <div class="label">答对题目数</div>
        </div>
        <div class="stat-card">
            <div class="number">{{ correct_rate }}%</div>
            <div class="label">总正确率</div>
        </div>
    </div>

    {% if daily_stats %}
    <div class="chart-container">
        <h3>近7天正确率趋势</h3>
        <canvas id="trendChart" height="100"></canvas>
    </div>
    {% endif %}

    {% if knowledge %}
    <div class="knowledge-section">
        <h3>📊 知识点掌握度</h3>
        <div class="knowledge-list">
            {% for kc, p in knowledge.items() %}
            <div class="knowledge-item">
                <span class="name">{{ kc }}</span>
                <div class="bar">
                    <div class="bar-fill {% if p < 0.4 %}low{% elif p < 0.7 %}medium{% else %}high{% endif %}" style="width: {{ p * 100 }}%;"></div>
                </div>
                <span class="value">{{ '%.0f'|format(p * 100) }}%</span>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    <script>
        const dailyStats = {{ daily_stats_json | safe }};
        const labels = dailyStats.map(d => d.date.slice(5));
        const rates = dailyStats.map(d => d.rate);

        new Chart(document.getElementById('trendChart'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: '正确率 (%)',
                    data: rates,
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true, max: 100 }
                }
            }
        });
    </script>
    </div>
</body>
</html>
'''


@app.route('/stats')
def stats():
    """学习统计页面"""
    user = get_current_user()
    daily_stats = user.get_daily_stats(7)
    total_stats = user.get_total_stats()

    # 计算总正确率
    if total_stats['total_answered'] > 0:
        correct_rate = round(total_stats['total_correct'] / total_stats['total_answered'] * 100, 1)
    else:
        correct_rate = 0

    return render_template_string(
        STATS_HTML,
        daily_stats=daily_stats,
        daily_stats_json=json.dumps(daily_stats),
        total_stats=total_stats,
        correct_rate=correct_rate,
        knowledge=user.knowledge_state
    )


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
    # 清除错题的"已复习"标记，允许重新复习
    for h in user.history:
        h.pop('reviewed', None)
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
