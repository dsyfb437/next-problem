import os
import json
import sqlite3
from datetime import datetime

DB_PATH = 'data.db'
DATA_DIR = 'data'

def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    for filename in os.listdir(DATA_DIR):
        if not filename.startswith('user_') or not filename.endswith('.json'):
            continue
        
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        user_id = data.get('user_id')
        history = data.get('history', [])
        
        for record in history:
            c.execute(
                'INSERT OR IGNORE INTO interactions (user_id, question_id, is_correct, timestamp) VALUES (?, ?, ?, ?)',
                (
                    user_id,
                    record['qid'],
                    1 if record['correct'] else 0,
                    record.get('timestamp', datetime.now().isoformat())
                )
            )
        print(f"✅ 已迁移用户 {user_id}，共 {len(history)} 条记录")
    
    conn.commit()
    conn.close()
    print("🎉 所有历史数据迁移完成")

if __name__ == '__main__':
    migrate()