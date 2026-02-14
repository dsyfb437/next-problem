# 智能考研数学刷题系统

## 技术栈
- **后端**: Python + Flask
- **前端**: Flask 模板 + KaTeX (LaTeX渲染) + MathLive (公式输入)
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **部署**: PythonAnywhere + GitHub Actions

## 项目结构
```
next-problem/
├── app.py              # Flask 主应用
├── bkt_core.py         # BKT算法核心模块
├── db.py               # 数据库抽象层
├── math1.json          # 高等数学题库
├── linalg.json         # 线性代数题库
├── prob.json           # 概率论题库
├── data/               # 用户进度数据
└── .env                # 环境变量
```

## 常用命令
```bash
# 激活虚拟环境
source venv/bin/activate

# 本地运行
python app.py

# 测试
python -c "from app import app; ..."
```

## 题库格式
填空题:
```json
{
  "id": "m1_001",
  "type": "fill_in",
  "subject": "高等数学",
  "chapter": "极限",
  "knowledge_tags": ["极限"],
  "difficulty": 0.6,
  "question_text": "$$\\lim_{x \\to 0} \\frac{\\sin 2x}{x}$$",
  "answer": "2",
  "answer_type": "numeric"
}
```

选择题:
```json
{
  "id": "mc001",
  "type": "multiple_choice",
  "subject": "高等数学",
  "chapter": "极限",
  "question_text": "$x \\to 0$ 时，哪个不是无穷小？",
  "options": ["$x^2$", "$\\sin x$", "$\\frac{1}{x}$", "$\\tan x$"],
  "correct_option": 2
}
```

## 判题逻辑 (bkt_core.py)
- `numeric`: 浮点数比较 (误差1e-6)
- `formula`: SymPy 符号等价判断
- `string`: 精确匹配
- `multiple_choice`: 选项索引比较

## 代码规范
- 使用 f-string
- 4空格缩进
- 类型注解 (Type Hints)
- 中文注释

## 注意事项
1. LaTeX 在 JSON 中需双反斜杠: `\\frac`
2. 避免控制字符: `\f`, `\t`, `\r` 等
3. 部署用 GitHub Actions，自动 push 到 PythonAnywhere

## 部署
1. `git push` 触发 GitHub Actions
2. PythonAnywhere 自动 pull 并重启

## 外部资源
- KaTeX: https://cdn.jsdelivr.net/npm/katex@0.16.10
- MathLive: https://cdn.jsdelivr.net/npm/mathlive@0.100.0
