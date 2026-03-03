"""
BKT推荐引擎实现
"""
import random
from typing import Dict, List, Optional, Set
from services.recommend.base import RecommendEngine


class BKTRecommendEngine(RecommendEngine):
    """基于贝叶斯知识追踪(BKT)的推荐引擎"""

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
        knowledge_state = user_state.get("knowledge_state", {})
        answered_questions = set(user_state.get("answered_questions", []))

        candidates = []

        for question in questions:
            qid = question.get("id")
            qtype = question.get("type")

            # 跳过证明题
            if qtype == "essay":
                continue

            # 跳过不在可用集合的题目
            if available_qids is not None and qid not in available_qids:
                continue

            # 跳过已答题
            if qid in answered_questions:
                continue

            # 计算知识点平均掌握度
            knowledge_tags = question.get("knowledge_tags", [])
            if not knowledge_tags:
                avg_mastery = knowledge_state.get("default", self.default_mastery)
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
        knowledge_state = user_state.get("knowledge_state", {})
        knowledge_tags = question.get("knowledge_tags", [])

        if not knowledge_tags:
            knowledge_tags = ["default"]

        current_p = knowledge_state.get("default", self.default_mastery)

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

        user_state["knowledge_state"] = knowledge_state
        return user_state
