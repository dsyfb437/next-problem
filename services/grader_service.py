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
        - true_false: 判断题 (是/否, 对/错, True/False)
        - numeric: 浮点数比较
        - formula: SymPy符号等价
        - string: 精确匹配
        """
        question_type = question.get("type", "fill_in")

        # 选择题
        if question_type == "multiple_choice":
            return self._check_multiple_choice(question, user_answer)

        # 判断题
        if question_type == "true_false":
            return self._check_true_false(question, user_answer)

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

    def _check_true_false(self, question: Dict, user_answer: str) -> bool:
        """检查判断题"""
        correct = str(question.get("answer", "")).strip().lower()
        user = user_answer.strip().lower()

        # 正确答案映射
        true_values = {"是", "对", "正确", "true", "t", "1", "yes", "y"}
        false_values = {"否", "错", "错误", "false", "f", "0", "no", "n"}

        # 检查用户答案是否有效
        user_is_true = None
        if user in true_values:
            user_is_true = True
        elif user in false_values:
            user_is_true = False

        if user_is_true is None:
            return False

        # 检查正确答案
        if correct in true_values:
            correct_is_true = True
        elif correct in false_values:
            correct_is_true = False
        else:
            # 如果answer字段不是标准值，默认当作False
            correct_is_true = False

        return user_is_true == correct_is_true

    def _check_fill_in(self, question: Dict, user_answer: str) -> bool:
        """检查填空题"""
        answer_type = question.get("answer_type", "string")
        correct_answer = question.get("answer", "").strip()
        user_answer = user_answer.strip()

        if not user_answer:
            return False

        # 支持多答案：用 || 或 ; 分隔多个正确答案
        # 例如: "1;2" 表示答案是1或2都对
        if "||" in correct_answer:
            answers = correct_answer.split("||")
        elif ";" in correct_answer:
            answers = correct_answer.split(";")
        else:
            answers = [correct_answer]

        # 尝试匹配任意一个正确答案
        for ans in answers:
            ans = ans.strip()
            if answer_type == "numeric":
                if self._check_numeric(ans, user_answer):
                    return True
            elif answer_type == "formula":
                if self._check_formula(ans, user_answer):
                    return True
            else:
                if user_answer.lower() == ans.lower():
                    return True

        return False

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

        # 分数（\frac 和 \dfrac 等效）
        s = re.sub(r"\\dfrac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))", s)
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
