"""
数据模型 - 用户模型
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime


@dataclass
class AnswerHistory:
    """答题历史记录"""
    qid: str
    user_answer: str
    correct: bool
    timestamp: str
    # AI训练数据
    time_spent: Optional[float] = None  # 答题耗时(秒)
    question_difficulty: float = 0.5
    question_type: str = "fill_in"
    knowledge_tags: List[str] = field(default_factory=list)
    subject: str = ""
    chapter: str = ""
    # 复习相关
    review_count: int = 0
    last_reviewed: Optional[str] = None
    next_review: Optional[str] = None
    reviewed: bool = False

    def to_dict(self) -> dict:
        return {
            "qid": self.qid,
            "user_answer": self.user_answer,
            "correct": self.correct,
            "timestamp": self.timestamp,
            "time_spent": self.time_spent,
            "question_difficulty": self.question_difficulty,
            "question_type": self.question_type,
            "knowledge_tags": self.knowledge_tags,
            "subject": self.subject,
            "chapter": self.chapter,
            "review_count": self.review_count,
            "last_reviewed": self.last_reviewed,
            "next_review": self.next_review,
            "reviewed": self.reviewed
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'AnswerHistory':
        return cls(
            qid=data.get("qid", ""),
            user_answer=data.get("user_answer", ""),
            correct=data.get("correct", False),
            timestamp=data.get("timestamp", ""),
            time_spent=data.get("time_spent"),
            question_difficulty=data.get("question_difficulty", 0.5),
            question_type=data.get("question_type", "fill_in"),
            knowledge_tags=data.get("knowledge_tags", []),
            subject=data.get("subject", ""),
            chapter=data.get("chapter", ""),
            review_count=data.get("review_count", 0),
            last_reviewed=data.get("last_reviewed"),
            next_review=data.get("next_review"),
            reviewed=data.get("reviewed", False)
        )


@dataclass
class User:
    """用户模型"""
    user_id: str
    username: str
    password_hash: str = ""
    created_at: str = ""

    # 知识状态: {知识点: 掌握度}
    knowledge_state: Dict[str, float] = field(default_factory=dict)

    # 已答题集合
    answered_questions: Set[str] = field(default_factory=set)

    # 当轮正确题
    correct_in_round: Set[str] = field(default_factory=set)

    # 答题历史
    history: List[AnswerHistory] = field(default_factory=list)

    # 收藏
    favorites: List[str] = field(default_factory=list)
    favorite_notes: Dict[str, str] = field(default_factory=dict)

    # 每日统计: {日期: {answered, correct}}
    daily_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # 总体统计
    total_stats: Dict[str, any] = field(default_factory=dict)

    # Flask-Login 兼容
    is_authenticated: bool = True
    is_active: bool = True
    is_anonymous: bool = False

    def get_id(self) -> str:
        return self.user_id

    def to_dict(self) -> dict:
        """转换为字典用于持久化"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
            "knowledge_state": self.knowledge_state,
            "answered_questions": list(self.answered_questions),
            "correct_in_round": list(self.correct_in_round),
            "history": [h.to_dict() for h in self.history],
            "favorites": self.favorites,
            "favorite_notes": self.favorite_notes,
            "daily_stats": self.daily_stats,
            "total_stats": self.total_stats
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """从字典创建用户"""
        user = cls(
            user_id=data.get("user_id", ""),
            username=data.get("username", ""),
            password_hash=data.get("password_hash", ""),
            created_at=data.get("created_at", ""),
            knowledge_state=data.get("knowledge_state", {}),
            answered_questions=set(data.get("answered_questions", [])),
            correct_in_round=set(data.get("correct_in_round", [])),
            favorites=data.get("favorites", []),
            favorite_notes=data.get("favorite_notes", {}),
            daily_stats=data.get("daily_stats", {}),
            total_stats=data.get("total_stats", {})
        )
        # 历史记录
        history_list = data.get("history", [])
        user.history = [AnswerHistory.from_dict(h) for h in history_list]
        return user


@dataclass
class UserState:
    """用户状态 - 用于推荐引擎"""
    knowledge_state: Dict[str, float]
    answered_questions: Set[str]
    history: List[AnswerHistory]
    favorites: List[str]

    def to_dict(self) -> dict:
        return {
            "knowledge_state": self.knowledge_state,
            "answered_questions": self.answered_questions,
            "history": [h.to_dict() for h in self.history],
            "favorites": self.favorites
        }

    @classmethod
    def from_user(cls, user: User) -> 'UserState':
        return cls(
            knowledge_state=user.knowledge_state,
            answered_questions=user.answered_questions,
            history=user.history,
            favorites=user.favorites
        )
