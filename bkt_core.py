import json
import random
import os
import sqlite3
from datetime import datetime
from typing import Dict, List
from sympy import sympify, SympifyError

DB_PATH = 'data.db'

# ========== 1. 核心数据结构 ==========
class BKTUser:
    def __init__(self, user_id: str, default_mastery: float = 0.3):
        self.user_id = user_id
        self.default_mastery = default_mastery
        self.knowledge_state: Dict[str, float] = {}
        self.answered_questions: set = set()
        self.correct_in_round: set = set()        # 本轮答对过的题（去重）
        self.history: List[Dict] = []
        
    def record_interaction(self, question_id, is_correct, timestamp=None):
        """记录答题（自动使用 self.user_id）"""
        import sqlite3
        from datetime import datetime
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        conn = sqlite3.connect('data.db')  # 确保路径正确
        c = conn.cursor()
        c.execute(
            'INSERT INTO interactions (user_id, question_id, is_correct, timestamp) VALUES (?, ?, ?, ?)',
            (self.user_id, question_id, 1 if is_correct else 0, timestamp)
        )
        conn.commit()
        conn.close()

    def save_to_file(self, data_dir="data"):
        """将用户数据保存到JSON文件"""
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        file_path = os.path.join(data_dir, f"user_{self.user_id}.json")
        data = {
            "user_id": self.user_id,
            "knowledge_state": self.knowledge_state,
            "answered_questions": list(self.answered_questions),
            "correct_in_round": list(self.correct_in_round),
            "history": self.history
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 用户进度已保存至 {file_path}")

    @classmethod
    def load_from_file(cls, user_id: str, default_mastery=0.3, data_dir="data"):
        """从文件加载用户，若无则返回新用户"""
        file_path = os.path.join(data_dir, f"user_{user_id}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            user = cls(user_id, default_mastery)
            user.knowledge_state = data.get("knowledge_state", {})
            user.answered_questions = set(data.get("answered_questions", []))
            user.history = data.get("history", [])
            user.correct_in_round = set(data.get("correct_in_round", []))
            # print(f"📂 已加载用户 {user_id} 的进度")
            return user
        else:
            print(f"🆕 新用户 {user_id}，从默认状态开始")
            return cls(user_id, default_mastery)

class SimpleBKTEngine:
    def __init__(self, default_mastery=0.3, learn_rate=0.3, slip_rate=0.1, guess_rate=0.2):
        self.default_mastery = default_mastery
        self.learn_rate = learn_rate
        self.slip_rate = slip_rate
        self.guess_rate = guess_rate

    def update_mastery(self, current_p: float, is_correct: bool) -> float:
        if is_correct:
            numerator = current_p * (1 - self.slip_rate)
            denominator = numerator + (1 - current_p) * self.guess_rate
            new_p = numerator / denominator
        else:
            numerator = current_p * self.slip_rate
            denominator = numerator + (1 - current_p) * (1 - self.guess_rate)
            new_p = numerator / denominator
        new_p = new_p + (1 - new_p) * self.learn_rate
        return min(new_p, 0.99)

# ========== 2. 题库加载 ==========
def load_questions_from_json(file_path: str) -> List[Dict]:
    with open(file_path, 'r', encoding='utf-8') as f:
        questions = json.load(f)
    print(f"已从 {file_path} 加载 {len(questions)} 道题。")
    return questions

QUESTIONS = load_questions_from_json('questions.json')

# ========== 3. 推荐逻辑 ==========
def recommend_question(user: BKTUser, all_questions: List[Dict], available_qids: set = None) -> Dict:
    """
    推荐题目函数

    Args:
        user: 用户对象
        all_questions: 所有题目列表
        available_qids: 可答题目的 ID 集合（可选）。如果提供，只从这个集合中推荐。
                        用于多科目场景，确保只推荐当前科目未做过的题目。

    Returns:
        推荐的题目字典，如果没有可用题目则返回 None
    """
    candidate_questions = []
    for q in all_questions:
        # 如果提供了 available_qids，则只考虑在可用集合中的题目
        if available_qids is not None and q['id'] not in available_qids:
            continue

        # 过滤已做过的题目（使用全局 answered_questions）
        if q['id'] in user.answered_questions:
            continue

        # 计算该题涉及知识点的平均掌握度
        relevant_knowledge = q.get('knowledge_tags', [])
        if not relevant_knowledge:
            avg_mastery = user.knowledge_state.get('default', user.default_mastery)
        else:
            mastery_sum = 0
            for kc in relevant_knowledge:
                if kc not in user.knowledge_state:
                    user.knowledge_state[kc] = user.default_mastery
                mastery_sum += user.knowledge_state[kc]
            avg_mastery = mastery_sum / len(relevant_knowledge)

        # 🚫 掌握度高于 0.95 的题目不推送（太熟了）
        if avg_mastery > 0.95:
            continue

        candidate_questions.append((avg_mastery, q))

    if not candidate_questions:
        return None

    # 按掌握度升序排序
    candidate_questions.sort(key=lambda x: x[0])

    # 找出最低掌握度的具体数值
    lowest_mastery = candidate_questions[0][0]

    # 收集所有掌握度 ≤ lowest_mastery + 0.05 的题目（相近区间）
    threshold = lowest_mastery + 0.05
    best_questions = [q for m, q in candidate_questions if m <= threshold]

    # 从最佳候选题中随机选一道
    return random.choice(best_questions)

# ========== 4. 判题函数 ==========
def check_answer(question: Dict, user_answer: str) -> bool:
    """使用 SymPy 进行符号等价性判断，同时保留数值和字符串比较"""
    answer_type = question.get('answer_type', 'string')
    correct_answer = question.get('answer', '').strip()
    user_answer = user_answer.strip()

    # 数值型：转为浮点数比较
    if answer_type == 'numeric':
        try:
            return abs(float(user_answer) - float(correct_answer)) < 1e-6
        except ValueError:
            return False

    # 公式型：使用 SymPy 判断等价
    elif answer_type == 'formula':
        try:
            # 将用户答案和正确答案解析为 SymPy 表达式
            expr_user = sympify(user_answer)
            expr_correct = sympify(correct_answer)
            # 判断是否等价（化简后相等）
            return expr_user.equals(expr_correct)
        except (SympifyError, TypeError, AttributeError):
            # 如果解析失败，降级为宽松的字符串比较
            # 去除空格、将 ^ 统一为 **、将 ² 替换为 ^2 等
            def normalize(s):
                s = s.replace(' ', '').replace('^', '**').replace('²', '**2').replace('x²', 'x**2')
                return s
            return normalize(user_answer) == normalize(correct_answer)

    # 字符串型：精确比较
    else:
        return user_answer == correct_answer

# ========== 5. 主交互循环 ==========
def main_simulation():
    print("\n===== 智能刷题系统（命令行交互版）=====")
    engine = SimpleBKTEngine()
    user_id = input("请输入用户名（直接回车默认为 test_user_1）: ").strip()
    if not user_id:
        user_id = "test_user_1"
    user = BKTUser.load_from_file(user_id, default_mastery=engine.default_mastery)

    round_num = 1
    while True:
        print(f"\n--- 第 {round_num} 题 ---")
        question = recommend_question(user, QUESTIONS)
        if question is None:
            print("🎉 恭喜！所有题目已掌握或已做完！")
            break

        # 显示题目信息
        print(f"\n📘 [{question['subject']}] {question['chapter']}")
        print(f"题目：{question['question_text']}")
        print(f"知识点：{', '.join(question.get('knowledge_tags', ['无']))}")
        print(f"难度：{question.get('difficulty', '未知')}")

        # 获取用户输入
        user_input = input("你的答案：").strip()
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("👋 已退出。")
            break

        # 判题
        is_correct = check_answer(question, user_input)
        if is_correct:
            print("✅ 回答正确！")
        else:
            print(f"❌ 回答错误。正确答案：{question['answer']}")

        # 记录答题历史
        user.history.append({
            "qid": question['id'],
            "user_answer": user_input,
            "correct": is_correct,
            "timestamp": datetime.now().isoformat()
        })

        # 更新知识状态
        relevant_kc = question.get('knowledge_tags', ['default'])
        for kc in relevant_kc:
            old_p = user.knowledge_state.get(kc, engine.default_mastery)
            new_p = engine.update_mastery(old_p, is_correct)
            user.knowledge_state[kc] = new_p
            print(f"  知识点「{kc}」掌握度：{old_p:.3f} → {new_p:.3f}")

        # 记录已做
        user.answered_questions.add(question['id'])
        round_num += 1
        user.save_to_file()

    # 最终状态总结
    print("\n===== 学习结束 =====")
    print("当前知识掌握状态：")
    for kc, p in sorted(user.knowledge_state.items(), key=lambda x: x[1]):
        print(f"  {kc}: {p:.3f}")