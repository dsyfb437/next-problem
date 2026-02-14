"""
Bayesian Knowledge Tracing (BKT) core module for the intelligent question system.

Provides user state management, BKT algorithm, question recommendation, and answer checking.
"""

import json
import os
import random
from datetime import datetime
from typing import Dict, List, Set, Optional
from sympy import sympify, SympifyError, simplify

# Import database functions
from db import record_interaction


class BKTUser:
    """Represents a user with knowledge state and question history."""

    def __init__(self, user_id: str, default_mastery: float = 0.3):
        self.user_id = user_id
        self.default_mastery = default_mastery
        self.knowledge_state: Dict[str, float] = {}
        self.answered_questions: Set[str] = set()
        self.correct_in_round: Set[str] = set()
        self.history: List[Dict] = []

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
            "knowledge_state": self.knowledge_state,
            "answered_questions": list(self.answered_questions),
            "correct_in_round": list(self.correct_in_round),
            "history": self.history
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
            user.knowledge_state = data.get("knowledge_state", {})
            user.answered_questions = set(data.get("answered_questions", []))
            user.history = data.get("history", [])
            user.correct_in_round = set(data.get("correct_in_round", []))
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

    # Handle square roots: \sqrt{x} -> sqrt(x), \sqrt{2} -> sqrt(2)
    s = re.sub(r'\\sqrt\{([^{}]*)\}', r'sqrt(\1)', s)

    # Handle nth roots: \sqrt[n]{x} -> x**(1/n)
    s = re.sub(r'\\sqrt\[([^{}]*)\]\{([^{}]*)\}', r'((\2)**(1/(\1)))', s)

    # Handle powers: x^{n} -> x**n
    s = re.sub(r'\^\{([^}]*)\}', r'**(\1)', s)
    s = re.sub(r'\^(\d)', r'**\1', s)

    # Handle implicit multiplication: 2x -> 2*x
    s = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', s)
    s = re.sub(r'([a-zA-Z])(\d)', r'\1*\2', s)

    # Handle Greek letters
    greek_map = {
        '\\alpha': 'alpha', '\\beta': 'beta', '\\gamma': 'gamma',
        '\\delta': 'delta', '\\epsilon': 'epsilon', '\\theta': 'theta',
        '\\lambda': 'lambda', '\\mu': 'mu', '\\pi': 'pi', '\\sigma': 'sigma',
        '\\tau': 'tau', '\\phi': 'phi', '\\omega': 'omega'
    }
    for greek, sympy_name in greek_map.items():
        s = s.replace(greek, sympy_name)

    # Handle functions: \sin, \cos, etc.
    functions = ['sin', 'cos', 'tan', 'log', 'ln', 'exp', 'sqrt', 'abs', 'max', 'min']
    for func in functions:
        s = s.replace('\\' + func, func)

    # Handle exp separately (both \exp and e^)
    s = s.replace('\\exp', 'exp')

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

    Supports numeric comparison, formula equivalence (using SymPy), and exact string match.
    For formula type, accepts LaTeX input from MathLive and converts to SymPy for comparison.

    Args:
        question: Question dictionary with answer info
        user_answer: User's answer string (may be LaTeX for formula type)

    Returns:
        True if answer is correct, False otherwise
    """
    answer_type = question.get('answer_type', 'string')
    correct_answer = question.get('answer', '').strip()
    user_answer = user_answer.strip()

    if not user_answer:
        return False

    if answer_type == 'numeric':
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
