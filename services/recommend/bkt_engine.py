"""
BKT推荐引擎实现
"""
import math
import random
from datetime import datetime
from typing import Dict, List, Optional, Set
from services.recommend.base import RecommendEngine

# 遗忘曲线参数
FORGETTING_CURVE_TAU = 7  # 时间常数（天），控制遗忘速度


def apply_forgetting_curve(mastery: float, last_reviewed: str = None, tau: float = FORGETTING_CURVE_TAU) -> float:
    """根据时间衰减掌握度"""
    if not last_reviewed:
        return mastery

    try:
        last_dt = datetime.fromisoformat(last_reviewed)
        days_elapsed = (datetime.now() - last_dt).total_seconds() / 86400
        # 遗忘曲线: mastery * e^(-t/tau)
        decayed = mastery * math.exp(-days_elapsed / tau)
        return max(decayed, 0.1)  # 最低不低于 0.1
    except (ValueError, TypeError):
        return mastery


def predict_mastery_curve(mastery: float, last_reviewed: str, days: List[float] = None,
                           tau: float = FORGETTING_CURVE_TAU) -> tuple:
    """
    预测知识点遗忘曲线

    Args:
        mastery: 当前掌握度
        last_reviewed: 上次复习时间 (ISO格式)
        days: 要预测的天数列表，默认 [0, 1, 2, 4, 7, 14, 30]
        tau: 遗忘曲线时间常数

    Returns:
        (labels, values): 日期标签列表和对应的预测掌握度
    """
    if days is None:
        days = [0, 1, 2, 4, 7, 14, 30]

    try:
        last_dt = datetime.fromisoformat(last_reviewed)
    except (ValueError, TypeError):
        last_dt = datetime.now()

    labels = []
    values = []
    for d in days:
        future_dt = last_dt + timedelta(days=d)
        days_elapsed = (future_dt - last_dt).total_seconds() / 86400
        decayed = mastery * math.exp(-days_elapsed / tau)
        decayed = max(decayed, 0.1)

        if d == 0:
            labels.append("现在")
        elif d == 1:
            labels.append("1天后")
        else:
            labels.append(f"{d}天后")
        values.append(round(decayed * 100, 1))

    return labels, values


from datetime import timedelta


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

    def _get_effective_mastery(self, tag_mastery: float, last_reviewed: str = None) -> float:
        """获取考虑遗忘曲线的有效掌握度"""
        return apply_forgetting_curve(tag_mastery, last_reviewed)

    def recommend(self, user_state: Dict, questions: List[Dict],
                  available_qids: Optional[Set[str]] = None,
                  cram_rounds: int = 0) -> Optional[Dict]:
        """
        基于BKT算法推荐题目

        Args:
            user_state: 用户状态字典
            questions: 可用题目列表
            available_qids: 可用题目ID集合
            cram_rounds: 考前突击模式轮数（0=正常模式，2-3=突击模式）
        """
        knowledge_state = user_state.get("knowledge_state", {})
        answered_questions = set(user_state.get("answered_questions", []))
        # 获取知识点最近复习时间
        last_reviewed = user_state.get("last_reviewed", {})

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

            # 计算知识点平均掌握度（考虑遗忘曲线）
            knowledge_tags = question.get("knowledge_tags", [])
            if not knowledge_tags:
                tag_last_reviewed = last_reviewed.get("default")
                avg_mastery = self._get_effective_mastery(
                    knowledge_state.get("default", self.default_mastery),
                    tag_last_reviewed
                )
            else:
                effective_masteries = []
                now = datetime.now().isoformat()
                for tag in knowledge_tags:
                    is_new_tag = tag not in knowledge_state
                    if is_new_tag:
                        knowledge_state[tag] = self.default_mastery
                        # 新知识点冷启动：立即设置last_reviewed为当前时间
                        last_reviewed[tag] = now
                    tag_last_reviewed = last_reviewed.get(tag)
                    effective = self._get_effective_mastery(knowledge_state[tag], tag_last_reviewed)
                    effective_masteries.append(effective)
                avg_mastery = sum(effective_masteries) / len(effective_masteries)

            # 跳过掌握度高的题目（正常模式）
            # 考前突击模式允许推荐更多题目
            mastery_threshold = 0.95 if cram_rounds == 0 else 0.99
            if avg_mastery > mastery_threshold:
                continue

            # 获取题目难度
            difficulty = question.get("difficulty", 0.5)

            # 计算难度差距（用于同掌握度时 tie-breaking）
            mastery_gap = abs(avg_mastery - difficulty)

            # 评分：(1 - mastery, mastery_gap)
            # - 优先低掌握度
            # - 同掌握度时，优先难度接近的题目
            score = (1 - avg_mastery, mastery_gap)

            candidates.append((score, avg_mastery, difficulty, question))

        if not candidates:
            return None

        # 按评分升序排序（低分优先）
        candidates.sort(key=lambda x: x[0])

        # 从最佳评分附近选择
        # 考前突击模式选择更集中（更专注于最低分）
        threshold_offset = 0.02 if cram_rounds == 0 else 0.005
        lowest_mastery = candidates[0][1]
        threshold = lowest_mastery + threshold_offset
        best_questions = [q for s, m, d, q in candidates if m <= threshold]

        return random.choice(best_questions)

    def update(self, user_state: Dict, question: Dict, is_correct: bool,
               **extra_data) -> Dict:
        """根据答题结果更新知识点掌握度"""
        knowledge_state = user_state.get("knowledge_state", {})
        last_reviewed = user_state.get("last_reviewed", {})
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
        now = datetime.now().isoformat()
        for tag in knowledge_tags:
            knowledge_state[tag] = new_p
            last_reviewed[tag] = now

        user_state["knowledge_state"] = knowledge_state
        user_state["last_reviewed"] = last_reviewed
        return user_state
