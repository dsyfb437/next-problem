"""
Bayesian Knowledge Tracing (BKT) core module for the intelligent question system.

Provides user state management, BKT algorithm, question recommendation, and answer checking.
"""

import json
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional

# 艾宾浩斯复习间隔（天）
REVIEW_INTERVALS = [1, 3, 7, 14, 30]


def calculate_next_review_interval(review_count: int) -> int:
    """
    根据复习次数计算下次复习间隔。

    Args:
        review_count: 当前复习次数（0表示首次答对）

    Returns:
        下次复习的间隔天数
    """
    if review_count < len(REVIEW_INTERVALS):
        return REVIEW_INTERVALS[review_count]
    return REVIEW_INTERVALS[-1]  # 最长30天
from sympy import sympify, SympifyError, simplify

# Import database functions
from db import record_interaction


class BKTUser:
    """Represents a user with knowledge state and question history."""

    # For Flask-Login
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def __init__(self, user_id: str, default_mastery: float = 0.3):
        self.user_id = user_id
        self.default_mastery = default_mastery
        self.knowledge_state: Dict[str, float] = {}
        self.answered_questions: Set[str] = set()
        self.correct_in_round: Set[str] = set()
        self.history: List[Dict] = []
        # 用户账号字段
        self.username: Optional[str] = None
        self.password_hash: Optional[str] = None
        self.created_at: Optional[str] = None

    def get_id(self) -> str:
        """Flask-Login required method"""
        return self.user_id

    def set_password(self, password: str, bcrypt) -> None:
        """设置密码"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str, bcrypt) -> bool:
        """验证密码"""
        if not self.password_hash:
            return False
        return bcrypt.check_password_hash(self.password_hash, password)

    def record_interaction(self, question_id: str, is_correct: bool,
                          timestamp: Optional[str] = None) -> bool:
        """
        Record a question interaction to the database.

        Args:
            question_id: ID of the question answered
            is_correct: Whether the answer was correct
            timestamp: ISO format timestamp (uses current time if None)

        Returns:
            True if successful, False otherwise
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        return record_interaction(self.user_id, question_id, is_correct, timestamp)

    def get_wrong_questions(self, subject_questions: List[Dict]) -> List[Dict]:
        """
        获取当前科目的错题列表（排除已复习的）。

        Args:
            subject_questions: 当前科目的题目列表

        Returns:
            错题列表（包含完整题目信息）
        """
        # 筛选未答对 且 未被标记为"已复习"的题目
        wrong_qids = {
            h['qid'] for h in self.history
            if not h.get('correct', False) and not h.get('reviewed', False)
        }
        subject_qids = {q['id'] for q in subject_questions}
        wrong_in_subject = wrong_qids & subject_qids
        return [q for q in subject_questions if q['id'] in wrong_in_subject]

    def get_wrong_count(self, subject_questions: List[Dict]) -> int:
        """
        获取当前科目错题数量。

        Args:
            subject_questions: 当前科目的题目列表

        Returns:
            错题数量
        """
        return len(self.get_wrong_questions(subject_questions))

    def mark_reviewed(self, qid: str) -> None:
        """
        标记错题为已复习（答对了就不再显示在错题列表中）。

        Args:
            qid: 题目ID
        """
        for h in self.history:
            if h['qid'] == qid and not h.get('correct', False):
                h['reviewed'] = True
                break

    def get_due_questions(self, subject_questions: List[Dict]) -> List[Dict]:
        """
        获取到期需要复习的题目（仅针对答对的题目）。

        Args:
            subject_questions: 当前科目的题目列表

        Returns:
            到期需要复习的题目列表
        """
        now = datetime.now()
        due_qids = set()

        for h in self.history:
            if h.get('correct') and h.get('next_review'):
                try:
                    next_review = datetime.fromisoformat(h['next_review'])
                    if next_review <= now:
                        due_qids.add(h['qid'])
                except (ValueError, TypeError):
                    continue

        subject_qids = {q['id'] for q in subject_questions}
        due_in_subject = due_qids & subject_qids
        return [q for q in subject_questions if q['id'] in due_in_subject]

    def get_due_count(self, subject_questions: List[Dict]) -> int:
        """
        获取到期复习题目数量。

        Args:
            subject_questions: 当前科目的题目列表

        Returns:
            到期复习题目数量
        """
        return len(self.get_due_questions(subject_questions))

    def get_review_progress(self, qid: str) -> Optional[Dict]:
        """
        获取某道题的复习进度。

        Args:
            qid: 题目ID

        Returns:
            复习进度字典，包含 review_count, next_review, last_reviewed
        """
        for h in self.history:
            if h['qid'] == qid and h.get('correct'):
                return {
                    'review_count': h.get('review_count', 0),
                    'next_review': h.get('next_review'),
                    'last_reviewed': h.get('last_reviewed')
                }
        return None

    def update_review_status(self, qid: str, is_correct: bool) -> None:
        """
        更新复习状态。

        Args:
            qid: 题目ID
            is_correct: 本次答题是否正确
        """
        # 找到该题答对的记录
        for h in self.history:
            if h['qid'] == qid and h.get('correct'):
                if is_correct:
                    # 答对了，推进复习周期
                    review_count = h.get('review_count', 0) + 1
                    h['review_count'] = review_count
                    h['last_reviewed'] = datetime.now().isoformat()

                    interval = calculate_next_review_interval(review_count)
                    h['next_review'] = (datetime.now() + timedelta(days=interval)).isoformat()
                else:
                    # 答错了，重置复习周期
                    h['review_count'] = 0
                    h['next_review'] = datetime.now().isoformat()
                break

    # ==================== 收藏功能 ====================

    def add_favorite(self, qid: str) -> None:
        """添加收藏"""
        if not hasattr(self, 'favorites'):
            self.favorites = []
        if qid not in self.favorites:
            self.favorites.append(qid)

    def remove_favorite(self, qid: str) -> None:
        """取消收藏"""
        if hasattr(self, 'favorites') and qid in self.favorites:
            self.favorites.remove(qid)

    def is_favorite(self, qid: str) -> bool:
        """检查是否已收藏"""
        return hasattr(self, 'favorites') and qid in self.favorites

    def get_favorite_count(self) -> int:
        """获取收藏数量"""
        return len(self.favorites) if hasattr(self, 'favorites') else 0

    def get_favorite_questions(self, all_questions: List[Dict]) -> List[Dict]:
        """获取收藏的题目列表"""
        if not hasattr(self, 'favorites'):
            return []
        return [q for q in all_questions if q['id'] in self.favorites]

    def set_favorite_note(self, qid: str, note: str) -> None:
        """设置收藏备注"""
        if not hasattr(self, 'favorite_notes'):
            self.favorite_notes = {}
        self.favorite_notes[qid] = note

    def get_favorite_note(self, qid: str) -> str:
        """获取收藏备注"""
        if not hasattr(self, 'favorite_notes'):
            return ""
        return self.favorite_notes.get(qid, "")

    # ==================== 学习统计 ====================

    def record_daily_stats(self, date: str, answered: int, correct: int) -> None:
        """记录每日统计"""
        if not hasattr(self, 'daily_stats'):
            self.daily_stats = {}
        if date not in self.daily_stats:
            self.daily_stats[date] = {"answered": 0, "correct": 0}
        self.daily_stats[date]["answered"] += answered
        self.daily_stats[date]["correct"] += correct

    def update_total_stats(self) -> None:
        """更新总体统计"""
        if not hasattr(self, 'total_stats'):
            self.total_stats = {
                "total_answered": 0,
                "total_correct": 0,
                "streak_days": 0,
                "last_active_date": None
            }

        # 计算累计
        self.total_stats["total_answered"] = len(self.answered_questions)
        correct_in_history = sum(1 for h in self.history if h.get('correct'))
        self.total_stats["total_correct"] = correct_in_history

        # 更新连续学习天数
        today = datetime.now().strftime('%Y-%m-%d')
        last_date = self.total_stats.get('last_active_date')

        if last_date:
            last_dt = datetime.strptime(last_date, '%Y-%m-%d')
            today_dt = datetime.strptime(today, '%Y-%m-%d')
            diff = (today_dt - last_dt).days

            if diff == 1:
                # 昨天有学习，连续天数+1
                self.total_stats["streak_days"] += 1
            elif diff > 1:
                # 中断，重新计算
                self.total_stats["streak_days"] = 1
        else:
            self.total_stats["streak_days"] = 1

        self.total_stats["last_active_date"] = today

    def get_daily_stats(self, days: int = 7) -> List[Dict]:
        """获取近N天每日统计"""
        if not hasattr(self, 'daily_stats'):
            return []

        result = []
        today = datetime.now()
        for i in range(days):
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            stats = self.daily_stats.get(date, {"answered": 0, "correct": 0})
            result.append({
                "date": date,
                "answered": stats["answered"],
                "correct": stats["correct"],
                "rate": round(stats["correct"] / stats["answered"] * 100, 1) if stats["answered"] > 0 else 0
            })
        return result

    def get_total_stats(self) -> Dict:
        """获取总体统计"""
        default_stats = {
            "total_answered": 0,
            "total_correct": 0,
            "streak_days": 0,
            "last_active_date": None
        }
        if not hasattr(self, 'total_stats') or not self.total_stats:
            return default_stats
        return self.total_stats

    def save_to_file(self, data_dir: str = "data") -> None:
        """
        Save user state to JSON file.

        Args:
            data_dir: Directory to save user data files
        """
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, f"user_{self.user_id}.json")

        data = {
            "user_id": self.user_id,
            "username": self.username,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
            "knowledge_state": self.knowledge_state,
            "answered_questions": list(self.answered_questions),
            "correct_in_round": list(self.correct_in_round),
            "history": self.history,
            "favorites": getattr(self, 'favorites', []),
            "favorite_notes": getattr(self, 'favorite_notes', {}),
            "daily_stats": getattr(self, 'daily_stats', {}),
            "total_stats": getattr(self, 'total_stats', {})
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_file(cls, user_id: str, default_mastery: float = 0.3,
                       data_dir: str = "data") -> 'BKTUser':
        """
        Load user from JSON file or create new user if not exists.

        Args:
            user_id: User identifier
            default_mastery: Default mastery value for new users
            data_dir: Directory containing user data files

        Returns:
            BKTUser instance
        """
        file_path = os.path.join(data_dir, f"user_{user_id}.json")

        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            user = cls(user_id, default_mastery)
            user.username = data.get("username")
            user.password_hash = data.get("password_hash")
            user.created_at = data.get("created_at")
            user.knowledge_state = data.get("knowledge_state", {})
            user.answered_questions = set(data.get("answered_questions", []))
            user.history = data.get("history", [])
            user.correct_in_round = set(data.get("correct_in_round", []))
            user.favorites = data.get("favorites", [])
            user.favorite_notes = data.get("favorite_notes", {})
            user.daily_stats = data.get("daily_stats", {})
            user.total_stats = data.get("total_stats", {})
            return user

        return cls(user_id, default_mastery)


class SimpleBKTEngine:
    """Simple Bayesian Knowledge Tracing engine for mastery updates."""

    def __init__(self, default_mastery: float = 0.3, learn_rate: float = 0.3,
                 slip_rate: float = 0.1, guess_rate: float = 0.2):
        self.default_mastery = default_mastery
        self.learn_rate = learn_rate
        self.slip_rate = slip_rate
        self.guess_rate = guess_rate

    def update_mastery(self, current_p: float, is_correct: bool) -> float:
        """
        Update knowledge mastery based on answer correctness using BKT formula.

        Args:
            current_p: Current mastery probability
            is_correct: Whether the last answer was correct

        Returns:
            Updated mastery probability
        """
        if is_correct:
            numerator = current_p * (1 - self.slip_rate)
            denominator = numerator + (1 - current_p) * self.guess_rate
        else:
            numerator = current_p * self.slip_rate
            denominator = numerator + (1 - current_p) * (1 - self.guess_rate)

        new_p = numerator / denominator if denominator > 0 else current_p
        new_p = new_p + (1 - new_p) * self.learn_rate
        return min(new_p, 0.99)


def recommend_question(user: BKTUser, all_questions: List[Dict],
                      available_qids: Optional[Set[str]] = None) -> Optional[Dict]:
    """
    Recommend a question based on user's knowledge state.

    Prioritizes questions from the least mastered knowledge components.
    Filters out questions with mastery > 0.95.

    Args:
        user: User object with knowledge state
        all_questions: All available questions
        available_qids: Set of question IDs to consider (for subject filtering)

    Returns:
        Recommended question dict or None if no suitable question available
    """
    candidates = []

    for question in all_questions:
        qid = question.get('id')
        qtype = question.get('type')

        # Skip essay/proof questions (not auto-gradable)
        if qtype == 'essay':
            continue

        # Skip if not in available set
        if available_qids is not None and qid not in available_qids:
            continue

        # Skip already answered questions
        if qid in user.answered_questions:
            continue

        # Calculate average mastery for question's knowledge tags
        knowledge_tags = question.get('knowledge_tags', [])
        if not knowledge_tags:
            avg_mastery = user.knowledge_state.get('default', user.default_mastery)
        else:
            mastery_sum = 0.0
            for tag in knowledge_tags:
                if tag not in user.knowledge_state:
                    user.knowledge_state[tag] = user.default_mastery
                mastery_sum += user.knowledge_state[tag]
            avg_mastery = mastery_sum / len(knowledge_tags)

        # Skip questions with high mastery
        if avg_mastery > 0.95:
            continue

        candidates.append((avg_mastery, question))

    if not candidates:
        return None

    # Sort by mastery (ascending)
    candidates.sort(key=lambda x: x[0])

    # Select from questions near the lowest mastery
    lowest_mastery = candidates[0][0]
    threshold = lowest_mastery + 0.05
    best_questions = [q for m, q in candidates if m <= threshold]

    return random.choice(best_questions)


def latex_to_sympy(latex_str: str) -> str:
    """
    Convert LaTeX string to SymPy-compatible format.

    Handles common LaTeX patterns:
    - \\frac{a}{b} -> a/b
    - \\sqrt{x} -> sqrt(x)
    - \\sin, \\cos, \\tan -> sin, cos, tan
    - \\ln, \\log -> ln, log
    - x^2 -> x**2
    - Variables and numbers

    Args:
        latex_str: LaTeX string from MathLive input

    Returns:
        SymPy-compatible string
    """
    import re

    s = latex_str.strip()
    BS = chr(92)  # single backslash

    # Fix common escape issues from Python string handling
    # \f -> \\f (form feed), \t -> \\t (tab), etc.
    # This fixes issues where \frac becomes \x0crac
    fix_map = {
        '\f': '\\f',  # form feed
        '\t': '\\t',  # tab
        '\r': '\\r',  # carriage return
        '\n': '\\n',  # newline
    }
    for old, new in fix_map.items():
        s = s.replace(old, new)

    # Remove common LaTeX commands that MathLive might include
    s = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\text\{([^}]*)\}', r'\1', s)

    # Handle fractions: \frac{num}{den} -> (num)/(den)
    s = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r'((\1)/(\2))', s)

    # Handle square roots
    s = re.sub(r'\\sqrt\{([^{}]*)\}', r'sqrt(\1)', s)
    s = re.sub(r'\\sqrt\[([^{}]*)\]\{([^{}]*)\}', r'((\2)**(1/(\1)))', s)

    # Handle powers: x^{n} -> x**n
    s = re.sub(r'\^\{([^}]*)\}', r'**(\1)', s)
    s = re.sub(r'\^(\d)', r'**\1', s)

    # Handle Greek letters - use string replace
    s = s.replace(BS + 'alpha', 'alpha')
    s = s.replace(BS + 'beta', 'beta')
    s = s.replace(BS + 'gamma', 'gamma')
    s = s.replace(BS + 'delta', 'delta')
    s = s.replace(BS + 'epsilon', 'epsilon')
    s = s.replace(BS + 'theta', 'theta')
    s = s.replace(BS + 'lambda', 'lambda')
    s = s.replace(BS + 'mu', 'mu')
    s = s.replace(BS + 'pi', 'pi')
    s = s.replace(BS + 'sigma', 'sigma')
    s = s.replace(BS + 'tau', 'tau')
    s = s.replace(BS + 'phi', 'phi')
    s = s.replace(BS + 'omega', 'omega')

    # Handle functions with braces: \sin{...} -> sin(...)
    s = s.replace(BS + 'sin{', 'sin(')
    s = s.replace(BS + 'cos{', 'cos(')
    s = s.replace(BS + 'tan{', 'tan(')
    s = s.replace(BS + 'cot{', 'cot(')
    s = s.replace(BS + 'sec{', 'sec(')
    s = s.replace(BS + 'csc{', 'csc(')
    s = s.replace(BS + 'arcsin{', 'arcsin(')
    s = s.replace(BS + 'arccos{', 'arccos(')
    s = s.replace(BS + 'arctan{', 'arctan(')
    s = s.replace(BS + 'ln{', 'ln(')
    s = s.replace(BS + 'log{', 'log(')
    s = s.replace(BS + 'exp{', 'exp(')
    s = s.replace(BS + 'sqrt{', 'sqrt(')
    s = s.replace(BS + 'abs{', 'Abs(')
    
    # Handle \dfrac -> \frac
    s = s.replace(BS + 'dfrac{', BS + 'frac{')
    s = s.replace(BS + 'frac{', 'frac(')
    
    # Handle \cap, \cup, \in, \subset, \forall, \exists
    s = s.replace(BS + 'cap', 'and')
    s = s.replace(BS + 'cup', 'or')
    s = s.replace(BS + 'in', 'in')
    s = s.replace(BS + 'subset', 'subset')
    s = s.replace(BS + 'subseteq', 'subseteq')
    s = s.replace(BS + 'forall', 'forall')
    s = s.replace(BS + 'exists', 'exists')
    
    # Handle operators: \times, \div, \pm, \mp
    s = s.replace(BS + 'times', '*')
    s = s.replace(BS + 'div', '/')
    s = s.replace(BS + 'pm', '+')
    s = s.replace(BS + 'mp', '-')
    
    # Handle \mathrm, \mathbf, \mathcal
    s = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\mathbf\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\mathcal\{([^}]*)\}', r'\1', s)

    # Handle functions without braces: \sin x -> sin(x)
    def replace_func_followed_by_letter(s, func):
        """Replace \funcX with func(X) where X is a letter or digit"""
        pattern = BS + func
        result = ''
        i = 0
        while i < len(s):
            idx = s.find(pattern, i)
            if idx == -1:
                result += s[i:]
                break
            result += s[i:idx]
            next_idx = idx + len(pattern)
            if next_idx < len(s):
                next_char = s[next_idx]
                if next_char.isalpha() or next_char.isdigit():
                    result += func + '(' + next_char + ')'
                    i = next_idx + 1
                else:
                    result += func
                    i = next_idx
            else:
                result += func
                i = next_idx
        return result

    for func in ['sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'arcsin', 'arccos', 'arctan', 'ln', 'log', 'exp']:
        s = replace_func_followed_by_letter(s, func)

    # Handle implicit multiplication: 2x -> 2*x
    s = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', s)
    s = re.sub(r'([a-zA-Z])(\d)', r'\1*\2', s)

    # Handle absolute value: |x| -> Abs(x)
    s = re.sub(r'\|([^|]+)\|', r'Abs(\1)', s)

    # Clean up remaining braces
    s = s.replace('{', '(').replace('}', ')')

    # Handle implicit multiplication with parentheses: (x)(y) -> (x)*(y)
    s = re.sub(r'\)\(', r')*(', s)

    # Handle edge cases: remove extra spaces
    s = s.replace(' ', '')

    return s


def check_answer(question: Dict, user_answer: str) -> bool:
    """
    Check if user answer is correct.

    Supports:
    - Multiple choice: compares option index
    - Numeric comparison
    - Formula equivalence (using SymPy)
    - Exact string match

    Args:
        question: Question dictionary with answer info
        user_answer: User's answer string (may be LaTeX for formula type, or option index for multiple choice)

    Returns:
        True if answer is correct, False otherwise
    """
    # Check for multiple choice questions first
    question_type = question.get('type', 'fill_in')

    if question_type == 'multiple_choice':
        # Multiple choice: compare option indices
        try:
            user_option = int(user_answer)
            correct_option = question.get('correct_option', -1)
            return user_option == correct_option
        except (ValueError, TypeError):
            return False

    # Original logic for fill-in questions
    answer_type = question.get('answer_type', 'string')
    correct_answer = question.get('answer', '').strip()
    user_answer = user_answer.strip()

    if not user_answer:
        return False

    if answer_type == 'numeric':
        # Handle special cases
        if correct_answer in ['e', 'pi', 'i']:
            return user_answer.lower() == correct_answer.lower()
        if correct_answer == '-':
            return user_answer == '-' or user_answer == '-0'
        try:
            return abs(float(user_answer) - float(correct_answer)) < 1e-6
        except ValueError:
            return False

    elif answer_type == 'formula':
        # Debug: log user input
        print(f"[DEBUG] correct_answer={repr(correct_answer)}")
        print(f"[DEBUG] user_answer={repr(user_answer)}")

        # First try direct SymPy comparison (in case answer is already in SymPy format)
        try:
            expr_user = sympify(user_answer)
            expr_correct = sympify(correct_answer)
            if expr_user.equals(expr_correct):
                print("[DEBUG] Direct SymPy match!")
                return True
        except (SympifyError, TypeError, AttributeError, Exception) as e:
            print(f"[DEBUG] Direct SymPy failed: {e}")

        # Try converting LaTeX to SymPy format
        try:
            user_sympy = latex_to_sympy(user_answer)
            correct_sympy = latex_to_sympy(correct_answer)
            print(f"[DEBUG] user_sympy={user_sympy}")
            print(f"[DEBUG] correct_sympy={correct_sympy}")

            expr_user = sympify(user_sympy)
            expr_correct = sympify(correct_sympy)

            # Check symbolic equality
            if expr_user.equals(expr_correct):
                print("[DEBUG] LaTeX SymPy match!")
                return True

            # Check if difference simplifies to zero
            diff = expr_user - expr_correct
            if simplify(diff) == 0:
                print("[DEBUG] Simplified to zero!")
                return True

        except (SympifyError, TypeError, AttributeError, Exception) as e:
            print(f"[DEBUG] LaTeX conversion failed: {e}")

        # Final fallback: normalized string comparison
        def normalize(s: str) -> str:
            s = s.strip()
            s = s.replace(' ', '')
            s = s.replace('\\', '')
            s = s.replace('{', '').replace('}', '')
            s = s.replace('^', '**')
            s = s.replace('²', '**2')
            s = s.replace('×', '*')
            s = s.replace('÷', '/')
            return s.lower()

        return normalize(user_answer) == normalize(correct_answer)

    else:
        # String type - exact match (case-insensitive for convenience)
        return user_answer.lower() == correct_answer.lower()
