"""
数据模型 - 题目模型
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Question:
    """题目模型"""
    id: str
    type: str  # fill_in, multiple_choice, essay
    subject: str
    chapter: str
    knowledge_tags: List[str] = field(default_factory=list)
    difficulty: float = 0.5  # 0-1
    question_text: str = ""
    options: List[str] = field(default_factory=list)  # 选择题选项
    correct_option: Optional[int] = None  # 选择题正确答案索引
    answer: str = ""  # 填空题答案
    answer_type: str = "string"  # numeric, formula, string
    solution: str = ""  # 解答过程

    @classmethod
    def from_dict(cls, data: Dict) -> 'Question':
        """从字典创建题目"""
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "fill_in"),
            subject=data.get("subject", ""),
            chapter=data.get("chapter", ""),
            knowledge_tags=data.get("knowledge_tags", []),
            difficulty=data.get("difficulty", 0.5),
            question_text=data.get("question_text", ""),
            options=data.get("options", []),
            correct_option=data.get("correct_option"),
            answer=data.get("answer", ""),
            answer_type=data.get("answer_type", "string"),
            solution=data.get("solution", "")
        )

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type,
            "subject": self.subject,
            "chapter": self.chapter,
            "knowledge_tags": self.knowledge_tags,
            "difficulty": self.difficulty,
            "question_text": self.question_text,
            "options": self.options,
            "correct_option": self.correct_option,
            "answer": self.answer,
            "answer_type": self.answer_type,
            "solution": self.solution
        }


@dataclass
class QuestionCollection:
    """题目集合 - 内存缓存"""
    subject: str
    questions: List[Question] = field(default_factory=list)
    _index_by_id: Dict[str, Question] = field(default_factory=dict)
    _index_by_chapter: Dict[str, List[Question]] = field(default_factory=dict)
    _index_by_tag: Dict[str, List[Question]] = field(default_factory=dict)

    def __post_init__(self):
        self._build_index()

    def _build_index(self):
        """构建索引"""
        for q in self.questions:
            self._index_by_id[q.id] = q
            # 按章节索引
            if q.chapter:
                if q.chapter not in self._index_by_chapter:
                    self._index_by_chapter[q.chapter] = []
                self._index_by_chapter[q.chapter].append(q)
            # 按知识点索引
            for tag in q.knowledge_tags:
                if tag not in self._index_by_tag:
                    self._index_by_tag[tag] = []
                self._index_by_tag[tag].append(q)

    def get_by_id(self, qid: str) -> Optional[Question]:
        """根据ID获取题目"""
        return self._index_by_id.get(qid)

    def get_by_chapter(self, chapter: str) -> List[Question]:
        """根据章节获取题目"""
        return self._index_by_chapter.get(chapter, [])

    def get_by_tag(self, tag: str) -> List[Question]:
        """根据知识点获取题目"""
        return self._index_by_tag.get(tag, [])

    def get_unanswered(self, answered: set) -> List[Question]:
        """获取未答题"""
        return [q for q in self.questions if q.id not in answered]

    def get_by_type(self, qtype: str) -> List[Question]:
        """根据类型获取题目"""
        return [q for q in self.questions if q.type == qtype]
