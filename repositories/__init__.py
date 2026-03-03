"""
数据访问层
"""
from repositories.user_repo import UserRepository
from repositories.question_repo import QuestionRepository, get_question_repo

__all__ = [
    "UserRepository",
    "QuestionRepository",
    "get_question_repo"
]
