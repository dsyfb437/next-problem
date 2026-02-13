import sqlite3
import json
import os

DB_PATH = 'data.db'  # 数据库文件路径

def init_db():
    """初始化数据库表结构（幂等，可重复执行）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # ---------- 1. 用户表 ----------
    # 存储用户的当前知识状态（JSON 格式），以及最新活跃时间
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            knowledge_state TEXT NOT NULL,   -- 知识点掌握度 JSON
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ---------- 2. 答题记录表（核心！DKT 数据源）----------
    c.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            is_correct INTEGER NOT NULL,     -- 0/1
            timestamp TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # 索引：按用户和时间排序是 DKT 序列生成的常用查询
    c.execute('CREATE INDEX IF NOT EXISTS idx_user_time ON interactions(user_id, timestamp)')
    
    # ---------- 3. 可选：题目静态信息表（可后期再填）----------
    # 如果未来要做题目推荐特征工程，可以缓存题目难度、知识点等
    # 但目前可以直接从 questions.json 读取，暂不建表
    
    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")

if __name__ == '__main__':
    init_db()