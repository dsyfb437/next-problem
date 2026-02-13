from flask import Flask, request, render_template_string, session, redirect, url_for, flash
import json
import os
from datetime import datetime
from bkt_core import BKTUser, SimpleBKTEngine, recommend_question, check_answer

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # 必须设置，用于 session 和 flash

engine = SimpleBKTEngine()

# ---------- 增强版 HTML 模板 ----------
INDEX_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>📘 智能刷题·考研数学</title>
    <!-- KaTeX 核心 CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css" integrity="sha384-wcIxkf4k558AjM3Yz3BBFQUbk/zgIYC2R0QpeeYb+TwlBVMrlgLqwRjRtGZiK7ww" crossorigin="anonymous">
    <!-- KaTeX 核心 JS -->
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.js" integrity="sha384-hIoBPJpTUs74ddyc4bFZSM1TVlQDA60VBbJS0oA934VSz82sBx1X7kSx2ATBDIyd" crossorigin="anonymous"></script>
    <!-- 自动渲染扩展（识别 \(...\) 和 $$...$$） -->
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/contrib/auto-render.min.js" integrity="sha384-43gviWU0YVjaDtb/GhzOouOXtZMP/7XUzwPTstBeZFe/+rCMvRwr4yROQP43s0Xk" crossorigin="anonymous"></script>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
        .feedback { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
        .correct { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .wrong { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .progress { background: #e9ecef; padding: 15px; border-radius: 6px; }
        .katex { font-size: 1.2em; }
    </style>
</head>
<body>
    <h2>📘 考研数学·智能推送</h2>
    <p style="color: #6c757d;">👋 欢迎回来，{{ user_id }}！</p>
    
<!-- 科目切换表单 -->
<form method="post" action="/select_subject" style="margin-bottom: 20px;">
    <label for="subject">📖 当前题库：</label>
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
            <p><strong>【{{ question.subject }}】{{ question.chapter }}</strong>  · 难度 {{ question.difficulty }}</p>
            <p style="font-size: 1.2rem;">{{ question.question_text | safe }}</p>
            
            <form method="post" action="/answer" style="margin-top: 20px;">
                <input type="hidden" name="qid" value="{{ question.id }}">
                <input type="text" name="answer" placeholder="输入你的答案" 
                       style="width: 70%; padding: 8px; font-size: 1rem;" autofocus>
                <button type="submit" style="padding: 8px 20px; font-size: 1rem;">提交</button>
            </form>
        </div>
        
        <div class="progress">
            <h4>🧠 当前知识点掌握度</h4>
            <ul>
            {% for kc, p in knowledge.items() %}
                <li><strong>{{ kc }}</strong>: {{ '%.3f'|format(p) }}</li>
            {% else %}
                <li>还没有知识点数据，做完第一题就会生成～</li>
            {% endfor %}
            </ul>
            <p style="color: #666; font-size: 0.9rem;">
                📊 已做 {{ total_answered }} 题 / 总 {{ total_questions }} 题 · 
                正确率 {{ (correct_count / total_answered * 100) | round(1) if total_answered > 0 else 0 }}%
            </p>
        </div>
    {% else %}
    <div style="text-align: center; padding: 40px; background: #d1ecf1; border-radius: 8px;">
        <h3>🎉 恭喜！你已经完成了当前题库的所有题目！</h3>
        <p style="font-size: 1.2rem; margin: 20px 0;">
            共完成 <strong>{{ total_questions }}</strong> 题 · 
            正确率 <strong>{{ (correct_count / total_answered * 100) | round(1) if total_answered > 0 else 0 }}%</strong>
        </p>
        <div style="margin-top: 30px; display: flex; gap: 20px; justify-content: center;">
            <a href="/restart" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
                🔄 再来一遍（保留掌握度）
            </a>
            <a href="/reset" style="background: #6c757d; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
                🗑️ 完全重置（清空所有进度）
            </a>
        </div>
        <p style="margin-top: 20px; color: #666; font-size: 0.9rem;">
            💡 保留掌握度：你学会的知识点不会丢失，可以更高效地复习。
        </p>
    </div>
{% endif %}
    
    <p style="margin-top: 30px;"><a href="/reset">🗑️ 重置我的进度</a></p>
    <script>
    // 页面加载完成后，自动渲染所有 LaTeX 代码
    document.addEventListener("DOMContentLoaded", function() {
        renderMathInElement(document.body, {
            // 自定义定界符，默认已经支持 \(...\) 和 $$...$$
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '\\(', right: '\\)', display: false},
                {left: '$', right: '$', display: false}  // 可选，如果你习惯单美元符号
            ],
            throwOnError: false
        });
    });
</script>
</body>
</html>
'''

def get_current_user():
    """获取当前 session 对应的用户对象（从 JSON 加载）"""
    user_id = session.get('user_id')
    if not user_id:
        user_id = f"user_{datetime.now().timestamp()}"
        session['user_id'] = user_id
    return BKTUser.load_from_file(user_id, engine.default_mastery)

# ---------- 多题库配置 ----------
SUBJECT_FILES = {
    '高等数学': 'math1.json',
    '线性代数': 'linalg.json',
    '概率论': 'prob.json'
}

def load_questions(subject):
    """根据科目名加载对应的题库文件"""
    filename = SUBJECT_FILES.get(subject, 'math1.json')  # 默认高数
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 如果文件不存在，返回空列表并打印警告
        print(f"⚠️ 题库文件 {filename} 未找到，返回空题库")
        return []

# 当前激活的题库（默认高数）
CURRENT_SUBJECT = '高等数学'
QUESTIONS = load_questions(CURRENT_SUBJECT)
# ---------------------------------

@app.route('/select_subject', methods=['POST'])
def select_subject():
    """切换当前科目"""
    global CURRENT_SUBJECT, QUESTIONS
    subject = request.form.get('subject', '高等数学')
    if subject in SUBJECT_FILES:
        CURRENT_SUBJECT = subject
        QUESTIONS = load_questions(subject)
        flash(f"📚 已切换到《{subject}》题库", "correct")
    else:
        flash("❌ 科目不存在", "wrong")
    return redirect(url_for('index'))

@app.route('/')
def index():
    user = get_current_user()

    # 计算当前科目未做过的题目集合
    current_qids = {q['id'] for q in QUESTIONS}
    # 当前科目未做过的题 = 当前科目所有题 - 用户已做过的题（全局）
    available_qids = current_qids - user.answered_questions

    question = recommend_question(user, QUESTIONS, available_qids)

    # ----- 当前科目·本轮统计数据（正确率基于本轮）-----
    current_qids = {q['id'] for q in QUESTIONS}

    # 本轮已做的题目（去重）
    subject_answered = user.answered_questions & current_qids
    total_answered = len(subject_answered)

    # 本轮答对过的题目（去重）
    subject_correct_in_round = user.correct_in_round & current_qids
    correct_count = len(subject_correct_in_round)

    # 当前科目总题数
    total_questions = len(QUESTIONS)
    # ------------------------------------------------
    
    if question is None:
        # 判断是因为全部做完了，还是因为掌握度都太高
        if total_answered >= total_questions:
            # 所有题都做过
            pass  # 走原来的完成页面逻辑
        else:
            # 还有没做过的题，但掌握度都太高了
            flash("🎯 剩余题目对应的知识点已熟练掌握，如需复习请切换科目或重置进度。", "correct")
            question = None  # 仍然显示完成页，但给出提示

    display_id = user.user_id
    if display_id.startswith('user_'):
    # 提取时间戳的后几位，或直接简化
        short_id = display_id.split('_')[1][:6] if '_' in display_id else display_id[:6]
        display_id = f"访客{short_id}"

    return render_template_string(
        INDEX_HTML,
        question=question,
        knowledge=user.knowledge_state,
        total_answered=total_answered,      # 统一用这个变量名
        correct_count=correct_count,
        total_questions=total_questions,
        user_id=display_id,                # 用于显示欢迎信息
        current_subject=CURRENT_SUBJECT
    )

@app.route('/answer', methods=['POST'])
def answer():
    user = get_current_user()
    qid = request.form['qid']
    user_answer = request.form['answer'].strip()
    
    # 查找题目
    question = next((q for q in QUESTIONS if q['id'] == qid), None)
    if not question:
        flash("题目不存在，请重试", "wrong")
        return redirect(url_for('index'))
    
    # 判题
    is_correct = check_answer(question, user_answer)
    
    # ----- 实时反馈（用 flash 消息）-----
    if is_correct:
        flash(f"✅ 回答正确！", "correct")
        user.correct_in_round.add(qid)   # 答对过的题，加入本轮正确集合
    else:
        flash(f"❌ 回答错误。正确答案：{question['answer']}", "wrong")
    # ---------------------------------
    
    # 记录答题历史
    user.history.append({
        "qid": qid,
        "user_answer": user_answer,
        "correct": is_correct,
        "timestamp": datetime.now().isoformat()
    })
    
    # 更新知识点掌握度
    for kc in question.get('knowledge_tags', ['default']):
        old_p = user.knowledge_state.get(kc, engine.default_mastery)
        new_p = engine.update_mastery(old_p, is_correct)
        user.knowledge_state[kc] = new_p
    
    # 标记题目已做
    user.answered_questions.add(qid)
    
    # ----- 保存进度到 JSON 文件（核心！）-----
    user.save_to_file()
    # ----- 同时写入 SQLite -----
    user.record_interaction(qid, is_correct, datetime.now().isoformat())
    # ----------------------------------------
    
    return redirect(url_for('index'))

@app.route('/reset')
def reset():
    user_id = session.get('user_id')
    if user_id:
        file_path = os.path.join('data', f"user_{user_id}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
        session.clear()
        flash("🗑️ 已完全重置进度，所有数据已清空。", "correct")
    return redirect(url_for('index'))

@app.route('/restart')
def restart():
    user = get_current_user()
    user.answered_questions = set()
    user.correct_in_round = set()      # 清空本轮答对记录
    user.save_to_file()
    flash("🔄 已重置题目进度，你可以重新挑战所有题目，已掌握的知识点仍然保留。", "correct")
    return redirect(url_for('index'))

if __name__ == '__main__':
    # 确保 data 文件夹存在
    os.makedirs('data', exist_ok=True)
    app.run(debug=True)