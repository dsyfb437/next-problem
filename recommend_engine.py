"""
推荐引擎抽象层 (Recommendation Engine Abstraction)

提供可插拔的推荐引擎接口，当前默认使用BKT算法，
便于后期替换为深度学习模型。

设计原则:
1. 抽象接口定义推荐引擎的核心方法
2. BKT作为默认实现，保持向后兼容
3. 数据结构预留深度学习所需特征
"""

import random
from abc import ABC, abstractmethod
from datetime import datetime
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
            user_state: 用户状态字典，包含知识状态、历史记录等
            questions: 可用题目列表
            available_qids: 可用题目ID集合（用于科目筛选）

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
            **extra_data: 额外数据（如答题时间、尝试次数等）

        Returns:
            更新后的用户状态
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        获取引擎名称

        Returns:
            引擎名称字符串
        """
        pass


class BKTRecommendEngine(RecommendEngine):
    """
    基于贝叶斯知识追踪(BKT)的推荐引擎

    默认推荐算法，通过追踪知识点掌握度来推荐题目。
    """

    def __init__(self, default_mastery: float = 0.3,
                 learn_rate: float = 0.3, slip_rate: float = 0.1,
                 guess_rate: float = 0.2):
        self.default_mastery = default_mastery
        self.learn_rate = learn_rate
        self.slip_rate = slip_rate
        self.guess_rate = guess_rate

    def get_name(self) -> str:
        return "BKT"

    def recommend(self, user_state: Dict, questions: List[Dict],
                  available_qids: Optional[Set[str]] = None) -> Optional[Dict]:
        """基于BKT算法推荐题目"""
        knowledge_state = user_state.get('knowledge_state', {})
        answered_questions = set(user_state.get('answered_questions', []))

        candidates = []

        for question in questions:
            qid = question.get('id')
            qtype = question.get('type')

            # 跳过证明题
            if qtype == 'essay':
                continue

            # 跳过不在可用集合的题目
            if available_qids is not None and qid not in available_qids:
                continue

            # 跳过已答题
            if qid in answered_questions:
                continue

            # 计算知识点平均掌握度
            knowledge_tags = question.get('knowledge_tags', [])
            if not knowledge_tags:
                avg_mastery = knowledge_state.get('default', self.default_mastery)
            else:
                mastery_sum = 0.0
                for tag in knowledge_tags:
                    if tag not in knowledge_state:
                        knowledge_state[tag] = self.default_mastery
                    mastery_sum += knowledge_state[tag]
                avg_mastery = mastery_sum / len(knowledge_tags)

            # 跳过掌握度高的题目
            if avg_mastery > 0.95:
                continue

            candidates.append((avg_mastery, question))

        if not candidates:
            return None

        # 按掌握度升序排序
        candidates.sort(key=lambda x: x[0])

        # 从最低掌握度附近选择
        lowest_mastery = candidates[0][0]
        threshold = lowest_mastery + 0.05
        best_questions = [q for m, q in candidates if m <= threshold]

        return random.choice(best_questions)

    def update(self, user_state: Dict, question: Dict, is_correct: bool,
               **extra_data) -> Dict:
        """根据答题结果更新知识点掌握度"""
        knowledge_state = user_state.get('knowledge_state', {})
        knowledge_tags = question.get('knowledge_tags', [])

        if not knowledge_tags:
            knowledge_tags = ['default']

        current_p = knowledge_state.get('default', self.default_mastery)

        # BKT公式更新掌握度
        if is_correct:
            numerator = current_p * (1 - self.slip_rate)
            denominator = numerator + (1 - current_p) * self.guess_rate
        else:
            numerator = current_p * self.slip_rate
            denominator = numerator + (1 - current_p) * (1 - self.guess_rate)

        new_p = numerator / denominator if denominator > 0 else current_p
        new_p = new_p + (1 - new_p) * self.learn_rate
        new_p = min(new_p, 0.99)

        # 更新各知识点掌握度
        for tag in knowledge_tags:
            knowledge_state[tag] = new_p

        user_state['knowledge_state'] = knowledge_state
        return user_state


# 引擎注册表
_ENGINE_REGISTRY: Dict[str, RecommendEngine] = {
    'bkt': BKTRecommendEngine()
}

_current_engine_name = 'bkt'


def get_engine(name: str = 'bkt') -> RecommendEngine:
    """
    获取指定名称的推荐引擎

    Args:
        name: 引擎名称，默认'bkt'

    Returns:
        推荐引擎实例
    """
    return _ENGINE_REGISTRY.get(name, _ENGINE_REGISTRY['bkt'])


def register_engine(name: str, engine: RecommendEngine) -> None:
    """
    注册新的推荐引擎

    Args:
        name: 引擎名称
        engine: 推荐引擎实例
    """
    _ENGINE_REGISTRY[name] = engine


def set_engine(name: str) -> bool:
    """
    设置当前使用的推荐引擎

    Args:
        name: 引擎名称

    Returns:
        是否设置成功
    """
    global _current_engine_name
    if name in _ENGINE_REGISTRY:
        _current_engine_name = name
        return True
    return False


def get_current_engine() -> RecommendEngine:
    """获取当前使用的推荐引擎"""
    return _ENGINE_REGISTRY[_current_engine_name]
