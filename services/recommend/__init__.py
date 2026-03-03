"""
推荐引擎模块
"""
from services.recommend.base import RecommendEngine
from services.recommend.bkt_engine import BKTRecommendEngine

# 引擎注册表
_ENGINE_REGISTRY: Dict[str, RecommendEngine] = {}
_current_engine_name = "bkt"


def register_engine(name: str, engine: RecommendEngine) -> None:
    """注册推荐引擎"""
    _ENGINE_REGISTRY[name] = engine


def get_engine(name: str = "bkt") -> RecommendEngine:
    """获取指定名称的推荐引擎"""
    if name in _ENGINE_REGISTRY:
        return _ENGINE_REGISTRY[name]
    # 默认返回BKT
    if "bkt" not in _ENGINE_REGISTRY:
        _ENGINE_REGISTRY["bkt"] = BKTRecommendEngine()
    return _ENGINE_REGISTRY["bkt"]


def set_engine(name: str) -> bool:
    """设置当前使用的推荐引擎"""
    global _current_engine_name
    if name in _ENGINE_REGISTRY:
        _current_engine_name = name
        return True
    return False


def get_current_engine() -> RecommendEngine:
    """获取当前使用的推荐引擎"""
    return get_engine(_current_engine_name)


# 默认注册BKT引擎
register_engine("bkt", BKTRecommendEngine())

__all__ = [
    "RecommendEngine",
    "BKTRecommendEngine",
    "register_engine",
    "get_engine",
    "set_engine",
    "get_current_engine"
]
