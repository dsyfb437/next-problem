"""
推荐引擎抽象基类
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set, Any


class RecommendEngine(ABC):
    """
    推荐引擎抽象基类

    所有推荐算法需实现此接口，便于后期替换为深度学习模型。
    """

    @abstractmethod
    def recommend(self, user_state: Dict, questions: List[Dict],
                  available_qids: Optional[Set[str]] = None) -> Optional[Dict]:
        """
        推荐一道题目给用户

        Args:
            user_state: 用户状态字典
            questions: 可用题目列表
            available_qids: 可用题目ID集合

        Returns:
            推荐题目或None
        """
        pass

    @abstractmethod
    def update(self, user_state: Dict, question: Dict, is_correct: bool,
               **extra_data) -> Dict:
        """
        根据答题结果更新用户状态

        Args:
            user_state: 用户状态字典（会被直接修改）
            question: 被回答的题目
            is_correct: 是否回答正确
            **extra_data: 额外数据

        Returns:
            更新后的用户状态
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取引擎名称"""
        pass
