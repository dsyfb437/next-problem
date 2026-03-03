"""
控制器层
"""
from controllers.auth import create_auth_controller
from controllers.question import create_question_controller
from controllers.review import create_review_controller
from controllers.stats import create_stats_controller

__all__ = [
    "create_auth_controller",
    "create_question_controller",
    "create_review_controller",
    "create_stats_controller"
]
