"""
题目仓库 - 题库数据访问层
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from models.question import Question, QuestionCollection


class QuestionRepository:
    """题目数据仓库"""

    def __init__(self, question_dir: str = "questions"):
        self.question_dir = Path(question_dir)
        # 内存缓存
        self._cache: Dict[str, QuestionCollection] = {}

    def load(self, subject: str, filename: str) -> QuestionCollection:
        """加载题库到内存"""
        cache_key = f"{subject}:{filename}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        file_path = self.question_dir / filename
        if not file_path.exists():
            return QuestionCollection(subject=subject, questions=[])

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 修复双反斜杠问题
        data = self._fix_latex(data)

        questions = [Question.from_dict(q) for q in data]
        collection = QuestionCollection(subject=subject, questions=questions)

        self._cache[cache_key] = collection
        return collection

    def _fix_latex(self, data: List[Dict]) -> List[Dict]:
        """修复LaTeX双反斜杠问题"""
        for q in data:
            for field in ["question_text", "answer", "solution"]:
                if field in q and q[field]:
                    while "\\\\" in q[field]:
                        q[field] = q[field].replace("\\\\", "\\")
        return data

    def get_by_subject(self, subject: str, subject_files: Dict) -> QuestionCollection:
        """根据科目加载题库"""
        filename = subject_files.get(subject)
        if not filename:
            return QuestionCollection(subject=subject, questions=[])
        return self.load(subject, filename)

    def get_question(self, qid: str, collections: List[QuestionCollection]) -> Optional[Question]:
        """根据ID获取题目"""
        for coll in collections:
            q = coll.get_by_id(qid)
            if q:
                return q
        return None

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()


# 全局实例
_question_repo: Optional[QuestionRepository] = None


def get_question_repo() -> QuestionRepository:
    """获取题目仓库单例"""
    global _question_repo
    if _question_repo is None:
        from config import QUESTION_DIR
        _question_repo = QuestionRepository(str(QUESTION_DIR))
    return _question_repo
