import csv
import json
import sys

def csv_to_json(csv_file, json_file):
    items = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 字段映射（按你的 CSV 列名调整）
            item = {
                "id": row["id"],
                "subject": row["subject"],
                "chapter": row["chapter"],
                "knowledge_tags": row["knowledge_tags"].split('|'),  # 用 | 分隔多个标签
                "difficulty": float(row["difficulty"]),
                "question_text": row["question_text"],
                "answer": row["answer"],
                "answer_type": row["answer_type"]
            }
            items.append(item)
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"转换完成，共 {len(items)} 道题，已保存至 {json_file}")

if __name__ == '__main__':
    if len(sys.argv) > 2:
        csv_to_json(sys.argv[1], sys.argv[2])
    else:
        print("用法: python csv_to_json.py 输入.csv 输出.json")