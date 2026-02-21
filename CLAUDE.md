# 智能考研数学刷题系统

## 技术栈
- **后端**: Python + Flask
- **前端**: Flask 模板 + KaTeX (LaTeX渲染) + MathLive (公式输入) + Chart.js (统计图表)
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **部署**: PythonAnywhere + GitHub Actions
- **用户认证**: Flask-Login + Bcrypt

## 项目结构
```
next-problem/
├── app.py              # Flask 主应用 (路由、视图、模板)
├── bkt_core.py         # BKT算法核心模块 (用户状态、推荐、判题)
├── db.py               # 数据库抽象层
├── questions/          # 题库目录
│   ├── math1.json     # 高等数学 (260题)
│   ├── linalg.json    # 线性代数 (76题)
│   └── prob.json      # 概率论 (64题)
├── data/              # 用户进度JSON文件
│   ├── users_index.json  # 用户索引
│   └── user_*.json    # 用户数据文件
├── data.db            # SQLite 数据库
├── .env               # 环境变量
└── venv/              # Python虚拟环境
```

## 常用命令
```bash
# 激活虚拟环境
cd /home/dsyfb_437/next-problem
source venv/bin/activate

# 本地运行
python app.py

# 测试
python -c "from app import app; print(app.url_map)"
```

## 题库格式
填空题:
```json
{
  "id": "m1_001",
  "type": "fill_in",
  "subject": "高等数学",
  "chapter": "极限",
  "knowledge_tags": ["极限计算"],
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

### answer_type 类型说明
- `numeric`: 浮点数比较 (误差1e-6)
- `formula`: SymPy 符号等价判断 (支持LaTeX和数学表达式)
- `string`: 精确匹配 (文本答案)
- `multiple_choice`: 选项索引比较

## 核心功能

### 用户认证
- `/login` - 登录页面 (用户名 + 密码)
- `/register` - 注册页面
- `/logout` - 退出登录

### 学习功能
- `/` - 首页，显示当前题目和进度
- `/answer` - 处理答题提交
- `/select_subject` - 切换科目

### 错题本
- `/review_wrong` - 复习答错的题目
- `/answer_review` - 错题答题提交

### 艾宾浩斯复习
- `/review_due` - 复习到期需要复习的题目
- `/answer_due` - 复习答题提交

### 收藏功能
- `/favorites` - 收藏列表页面
- `/favorite/add/<qid>` - 添加收藏
- `/favorite/remove/<qid>` - 取消收藏
- `/favorite/toggle/<qid>` - 切换收藏状态

### 学习统计
- `/stats` - 学习统计页面

### 其他
- `/reset` - 完全重置进度
- `/restart` - 重置题目进度（保留知识点掌握度）

## 核心模块

### app.py
- `load_questions(subject)`: 加载题库
- `load_users_index()`: 加载用户索引
- 用户认证路由: `/login`, `/register`, `/logout`
- 错题复习路由: `/review_wrong`, `/answer_review`
- 艾宾浩斯复习路由: `/review_due`, `/answer_due`
- 收藏功能路由: `/favorites`, `/favorite/toggle/<qid>`
- 统计页面: `/stats`

### bkt_core.py
- `BKTUser`: 用户知识状态管理
  - `knowledge_state`: 知识点掌握度
  - `answered_questions`: 已答题集
  - `history`: 答题历史
  - `username`, `password_hash`: 用户账号信息
  - `favorites`, `favorite_notes`: 收藏数据
  - `daily_stats`, `total_stats`: 学习统计
  - `set_password()`, `check_password()`: 密码管理
- 收藏功能: `add_favorite()`, `remove_favorite()`, `is_favorite()`, `get_favorite_questions()`
- 统计功能: `record_daily_stats()`, `update_total_stats()`, `get_daily_stats()`, `get_total_stats()`
- `SimpleBKTEngine`: BKT算法引擎
  - `update_mastery()`: 更新知识点掌握度
- `recommend_question()`: 基于掌握度推荐题目
- `check_answer()`: 判题逻辑
- `calculate_next_review_interval()`: 艾宾浩斯复习间隔
- `get_wrong_questions()`, `get_due_questions()`: 获取复习题目

### db.py
- `init_db()`: 初始化数据库表
- `record_interaction()`: 记录答题交互
- `get_user_interactions()`: 获取用户交互历史

## 数据结构

### 用户数据 (data/user_*.json)
```json
{
  "user_id": "user_xxx",
  "username": "zhangsan",
  "password_hash": "$2b$12$...",
  "created_at": "2024-01-01T00:00:00",
  "knowledge_state": {"极限": 0.8, "导数": 0.6},
  "answered_questions": ["m1_001", "m1_002"],
  "favorites": ["m1_005", "m1_010"],
  "favorite_notes": {"m1_005": "经典题型"},
  "daily_stats": {
    "2024-01-15": {"answered": 20, "correct": 15}
  },
  "total_stats": {
    "total_answered": 500,
    "total_correct": 400,
    "streak_days": 5,
    "last_active_date": "2024-01-15"
  },
  "history": [
    {
      "qid": "m1_001",
      "user_answer": "2",
      "correct": true,
      "timestamp": "2024-01-01T10:00:00",
      "review_count": 1,
      "next_review": "2024-01-04T10:00:00"
    }
  ]
}
```

### 用户索引 (data/users_index.json)
```json
{
  "users": [
    {"username": "zhangsan", "user_id": "user_xxx"}
  ]
}
```

## 代码规范
- 使用 f-string
- 4空格缩进
- 类型注解 (Type Hints)
- 中文注释

## 注意事项
1. LaTeX 在 JSON 中需双反斜杠: `\\frac`
2. 避免控制字符: `\f`, `\t`, `\r` 等
3. 部署用 GitHub Actions，自动 push 到 PythonAnywhere
4. 密码使用 bcrypt 哈希存储

## 部署
1. `git push` 触发 GitHub Actions
2. PythonAnywhere 自动 pull 并重启

## 外部资源
- KaTeX: https://cdn.jsdelivr.net/npm/katex@0.16.10
- MathLive: https://cdn.jsdelivr.net/npm/mathlive@0.100.0
- Chart.js: https://cdn.jsdelivr.net/npm/chart.js
