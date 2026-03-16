"""
配置模块 - 集中管理应用配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 基础路径
BASE_DIR = Path(__file__).parent

# 加载 .env 文件（指定完整路径）
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
QUESTION_DIR = BASE_DIR / "questions"

# Flask配置
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("错误: SECRET_KEY 环境变量未设置！请复制 .env.example 为 .env 并配置")

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# 数据库配置
DATABASE_PATH = DATA_DIR / "app.db"

# 题库配置
SUBJECT_FILES = {
    "高等数学": "math1.json",
    "线性代数": "linalg.json",
    "概率论": "prob.json",
}

PROOF_SUBJECT_FILES = {
    "高等数学": "math_proof.json",
    "线性代数": "linalg_proof.json",
    "概率论": "prob_proof.json",
}

# BKT算法默认参数
BKT_DEFAULT_MASTERY = 0.3
BKT_LEARN_RATE = 0.3
BKT_SLIP_RATE = 0.1
BKT_GUESS_RATE = 0.2

# 艾宾浩斯复习间隔(天)
REVIEW_INTERVALS = [1, 3, 7, 14, 30]

# 分页配置
QUESTIONS_PER_PAGE = 20
