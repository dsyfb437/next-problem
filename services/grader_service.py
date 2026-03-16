"""
判题服务 - 答案检查
"""
from sympy import sympify, SympifyError, simplify
from typing import Dict


class GraderService:
    """判题服务"""

    def check(self, question: Dict, user_answer: str) -> bool:
        """
        检查用户答案是否正确

        支持:
        - multiple_choice: 选项索引比较
        - numeric: 浮点数比较
        - formula: SymPy符号等价
        - string: 精确匹配
        """
        question_type = question.get("type", "fill_in")

        # 选择题
        if question_type == "multiple_choice":
            return self._check_multiple_choice(question, user_answer)

        # 填空题
        return self._check_fill_in(question, user_answer)

    def _check_multiple_choice(self, question: Dict, user_answer: str) -> bool:
        """检查选择题"""
        try:
            user_option = int(user_answer)
            correct_option = question.get("correct_option", -1)
            return user_option == correct_option
        except (ValueError, TypeError):
            return False

    def _check_fill_in(self, question: Dict, user_answer: str) -> bool:
        """检查填空题"""
        answer_type = question.get("answer_type", "string")
        correct_answer = question.get("answer", "").strip()
        user_answer = user_answer.strip()

        if not user_answer:
            return False

        if answer_type == "numeric":
            return self._check_numeric(correct_answer, user_answer)
        elif answer_type == "formula":
            return self._check_formula(correct_answer, user_answer)
        else:
            return user_answer.lower() == correct_answer.lower()

    def _check_numeric(self, correct: str, user_answer: str) -> bool:
        """检查数值答案"""
        if correct in ["e", "pi", "i"]:
            return user_answer.lower() == correct.lower()
        if correct == "-":
            return user_answer == "-" or user_answer == "-0"
        try:
            return abs(float(user_answer) - float(correct)) < 1e-6
        except ValueError:
            return False

    def _check_formula(self, correct: str, user_answer: str) -> bool:
        """检查公式答案"""
        # 直接比较
        try:
            expr_user = sympify(user_answer)
            expr_correct = sympify(correct)
            if expr_user.equals(expr_correct):
                return True
        except (SympifyError, ValueError, TypeError):
            pass

        # 转换为SymPy后比较
        try:
            user_sympy = self._latex_to_sympy(user_answer)
            correct_sympy = self._latex_to_sympy(correct)

            expr_user = sympify(user_sympy)
            expr_correct = sympify(correct_sympy)

            if expr_user.equals(expr_correct):
                return True

            diff = expr_user - expr_correct
            if simplify(diff) == 0:
                return True
        except (SympifyError, ValueError, TypeError, AttributeError):
            pass

        # 字符串标准化比较
        return self._normalize(user_answer) == self._normalize(correct)

    def _latex_to_sympy(self, latex_str: str) -> str:
        """LaTeX转SymPy格式"""
        import re
        s = latex_str.strip()

        # 修复转义
        for old, new in [("\f", "\\f"), ("\t", "\\t"), ("\r", "\\r")]:
            s = s.replace(old, new)

        # 移除LaTeX命令
        s = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", s)
        s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)

        # 分数
        s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))", s)

        # 根号
        s = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", s)

        # 幂
        s = re.sub(r"\^\{([^}]*)\}", r"**(\1)", s)
        s = re.sub(r"\^(\d)", r"**\1", s)

        # 清理
        s = s.replace("{", "(").replace("}", ")")
        s = s.replace(" ", "")

        return s

    def _normalize(self, s: str) -> str:
        """标准化字符串"""
        s = s.strip().replace(" ", "").replace("\\", "")
        s = s.replace("{", "").replace("}", "")
        s = s.replace("^", "**")
        return s.lower()


# 全局实例
_grader_service: GraderService = None


def get_grader() -> GraderService:
    """获取判题服务"""
    global _grader_service
    if _grader_service is None:
        _grader_service = GraderService()
    return _grader_service
