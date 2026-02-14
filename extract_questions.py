#!/usr/bin/env python3
"""
从 Math-master TeX 文件中提取例题 - 保留原始LaTeX格式
"""
import re
import json
from pathlib import Path

def extract_questions_from_tex(tex_path):
    """从单个 TeX 文件中提取例题，保留原始LaTeX"""
    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()

    questions = []

    # 使用 split 分割
    parts = content.split(r'\textbf{例题：}')

    for p in parts[1:]:
        # 找到下一个分隔符
        end_idx = p.find(r'\textbf{')
        if end_idx == -1:
            end_idx = p.find(r'\section{')
        if end_idx == -1:
            end_idx = p.find(r'\subsection{')
        if end_idx == -1:
            end_idx = p.find(r'\item ')
        if end_idx == -1:
            end_idx = len(p)

        question_text = p[:end_idx].strip()

        # 检查是否有"解："来分离题目和答案
        if '解：' in question_text:
            q_parts = question_text.split('解：')
            q_text = q_parts[0].strip()
            solution = '解：'.join(q_parts[1:]).strip()

            # 提取最终答案（从解答中找）
            answer = ''
            if '∴' in solution or '因此' in solution or '所以' in solution or '=' in solution:
                # 找最后的结果
                for end_marker in ['∴', '因此', '所以', '得']:
                    if end_marker in solution:
                        idx = solution.rfind(end_marker)
                        answer = solution[idx+len(end_marker):].strip()
                        # 清理答案
                        answer = re.sub(r'^[,，:：\.。].*', '', answer)
                        answer = answer[:100]  # 截取
                        break
            if not answer:
                # 尝试找等式
                eq_match = re.search(r'=[\s]*[\$\d\w\(\)\[\]\+\-\*/]+', solution)
                if eq_match:
                    answer = eq_match.group(0).strip()
        else:
            q_text = question_text
            solution = ''
            answer = ''

        # 保留原始LaTeX，不做转换
        # 只做最小清理
        q_text = clean_latex_minimal(q_text)

        if q_text and len(q_text) > 5:
            questions.append({
                'question': q_text,
                'solution': solution[:1000] if solution else '',
                'answer': answer,
            })

    return questions

def clean_latex_minimal(text):
    """最小化清理，保留LaTeX"""
    if not text:
        return ""

    # 只清理会导致JSON问题的字符
    # 保留大部分LaTeX命令
    text = text.replace('\\', '\\\\')  # escape backslash
    text = text.replace('\t', ' ')  # tabs to spaces
    text = re.sub(r'\s+', ' ', text)  # multiple spaces

    return text.strip()

def get_chapter_from_content(tex_path, content):
    """从TeX文件内容中提取章节标题"""
    # 尝试找\section或\subsection
    patterns = [
        (r'\\section\{([^}]+)\}', 1),
        (r'\\subsection\{([^}]+)\}', 2),
    ]

    for pattern, level in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)

    # 如果找不到，用文件名
    return get_chapter_from_path(tex_path)

def get_chapter_from_path(tex_path):
    """从文件路径推断章节"""
    filename = Path(tex_path).stem
    chapter_map = {
        'limit': '极限',
        'function': '函数',
        'differentiation-of-functions-of-single-variable': '导数与微分',
        'integal-of-functions-of-single-variable': '不定积分与定积分',
        'vector-algebra-and-space-analytic-geometry': '向量与空间解析几何',
        'differential-calculus-of-multivariate-functions': '多元函数微分学',
        'integral-calculus-of-multivariate-functions': '多元函数积分学',
        'infinite-series': '无穷级数',
        'differential-equation': '微分方程',
        'determinant': '行列式',
        'matrix': '矩阵',
        'vector': '向量',
        'linear-equations-system': '线性方程组',
        'similar': '相似矩阵',
        'quadratic-form': '二次型',
        'random-events-and-probability': '随机事件与概率',
        'random-variables-and-distribution': '随机变量与分布',
        'digital-features': '数字特征',
        'law-of-large-numbers-and-central-limit-theorem': '大数定律与中心极限定理',
        'mathematical-statistics': '数理统计',
        'perpare': '预备知识',
    }

    for k, v in chapter_map.items():
        if k in filename.lower():
            return v

    return filename

def get_subject_from_path(tex_path):
    """从文件路径推断学科"""
    path = str(tex_path)
    if 'advanced-math' in path:
        return '高等数学'
    elif 'linear-algebra' in path:
        return '线性代数'
    elif 'probability' in path:
        return '概率论'
    return '未知'

def main():
    base_dir = Path('Math-master')
    all_questions = []
    question_id = 1

    # 只处理 exercise 文件
    for tex_file in base_dir.rglob('*.tex'):
        if 'exercise' not in str(tex_file):
            continue

        print(f"处理: {tex_file.relative_to(base_dir)}")

        # 读取文件内容获取章节
        with open(tex_file, 'r', encoding='utf-8') as f:
            content = f.read()

        questions = extract_questions_from_tex(tex_file)

        subject = get_subject_from_path(tex_file)
        chapter = get_chapter_from_path(tex_file)

        print(f"  找到 {len(questions)} 道题")

        for q in questions:
            all_questions.append({
                'id': f'e{question_id:04d}',
                'subject': subject,
                'chapter': chapter,
                'question_text': q['question'],
                'answer': q['answer'],
                'answer_type': 'numeric',  # 默认
                'knowledge_tags': [chapter],  # 知识点就是章节
                'difficulty': 0.5,
                'solution': q['solution'],
            })
            question_id += 1

    print(f"\n共提取 {len(all_questions)} 道例题")

    # 保存
    output_file = 'extracted_questions.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)

    print(f"已保存到 {output_file}")

    # 按学科统计
    subjects = {}
    for q in all_questions:
        s = q['subject']
        subjects[s] = subjects.get(s, 0) + 1

    print("\n按学科统计:")
    for s, count in sorted(subjects.items()):
        print(f"  {s}: {count}题")

    # 打印示例
    print("\n示例题目 (保留LaTeX):")
    for q in all_questions[:5]:
        print(f"\n{q['id']}. [{q['subject']}] {q['chapter']}")
        print(f"   题目: {q['question_text'][:100]}")
        if q['answer']:
            print(f"   答案: {q['answer']}")

if __name__ == '__main__':
    main()
