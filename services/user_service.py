"""
用户服务 - 用户相关业务逻辑
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from models.user import User
from repositories import UserRepository
import config


class UserService:
    """用户服务"""

    def __init__(self, user_repo: UserRepository = None):
        self.user_repo = user_repo or UserRepository(config.DATA_DIR)

    def register(self, username: str, password: str, bcrypt) -> User:
        """注册新用户"""
        # 检查用户名是否已存在
        existing = self.user_repo.get_by_username(username)
        if existing:
            raise ValueError(f"用户名 {username} 已存在")

        # 生成用户ID
        user_id = f"user_{uuid.uuid4().hex[:16]}"

        # 创建用户
        from flask_bcrypt import Bcrypt
        bcrypt_instance = bcrypt or Bcrypt()
        password_hash = bcrypt_instance.generate_password_hash(password).decode("utf-8")

        return self.user_repo.create_user(username, password_hash, user_id)

    def login(self, username: str, password: str, bcrypt) -> Optional[User]:
        """用户登录"""
        user_info = self.user_repo.get_by_username(username)
        if not user_info:
            return None

        user = self.user_repo.load(user_info["user_id"])
        if not user:
            return None

        if not user.check_password(password, bcrypt):
            return None

        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        return self.user_repo.load(user_id)

    def save_user(self, user: User):
        """保存用户"""
        self.user_repo.save(user)

    def update_knowledge_state(self, user: User, knowledge_tags: list, is_correct: bool):
        """更新知识点掌握度"""
        from services.recommend import get_current_engine

        engine = get_current_engine()
        user_state = {
            "knowledge_state": user.knowledge_state,
            "answered_questions": user.answered_questions
        }

        # 构建题目信息
        question = {"knowledge_tags": knowledge_tags}

        # 更新状态
        engine.update(user_state, question, is_correct)
        user.knowledge_state = user_state["knowledge_state"]

    def record_answer(self, user: User, qid: str, is_correct: bool,
                     time_spent: Optional[float] = None,
                     question_info: dict = None):
        """记录答题结果"""
        from config import REVIEW_INTERVALS, calculate_next_review_interval

        # 构建历史记录
        history_entry = {
            "qid": qid,
            "user_answer": "",  # 由调用方填写
            "correct": is_correct,
            "timestamp": datetime.now().isoformat(),
            "time_spent": time_spent,
        }

        # 添加题目信息
        if question_info:
            history_entry["question_difficulty"] = question_info.get("difficulty", 0.5)
            history_entry["question_type"] = question_info.get("type", "fill_in")
            history_entry["knowledge_tags"] = question_info.get("knowledge_tags", [])
            history_entry["subject"] = question_info.get("subject", "")
            history_entry["chapter"] = question_info.get("chapter", "")

        # 艾宾浩斯复习
        if is_correct:
            history_entry["review_count"] = 0
            history_entry["last_reviewed"] = datetime.now().isoformat()
            interval = calculate_next_review_interval(0)
            history_entry["next_review"] = (datetime.now() + timedelta(days=interval)).isoformat()

        user.history.append(history_entry)
        user.answered_questions.add(qid)

        # 记录统计
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in user.daily_stats:
            user.daily_stats[today] = {"answered": 0, "correct": 0}
        user.daily_stats[today]["answered"] += 1
        if is_correct:
            user.daily_stats[today]["correct"] += 1

        # 更新总体统计
        user.total_stats["total_answered"] = len(user.answered_questions)
        user.total_stats["total_correct"] = sum(1 for h in user.history if h.get("correct", False))
        user.total_stats["last_active_date"] = today


def calculate_next_review_interval(review_count: int) -> int:
    """计算复习间隔"""
    from config import REVIEW_INTERVALS
    if review_count < len(REVIEW_INTERVALS):
        return REVIEW_INTERVALS[review_count]
    return REVIEW_INTERVALS[-1]
