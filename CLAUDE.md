# 智能考研数学刷题系统

## 技术栈
- **后端**: Python + Flask
- **前端**: Flask 模板 + KaTeX (LaTeX渲染)
- **数据存储**: JSON文件 (用户数据) + 内存缓存 (题库)
- **部署**: PythonAnywhere + GitHub Actions
- **用户认证**: Flask-Login + Bcrypt

## 项目结构 (分层架构)

```
next-problem/
├── app.py                      # 应用入口 (~50行)
├── config.py                   # 配置管理
│
├── controllers/               # 路由层 (HTTP请求处理)
│   ├── __init__.py
│   ├── auth.py              # 登录注册
│   ├── question.py          # 答题相关
│   ├── review.py            # 错题/艾宾浩斯/收藏
│   └── stats.py             # 统计
│
├── services/                  # 业务逻辑层
│   ├── __init__.py
│   ├── recommend/           # 推荐引擎 (可替换)
│   │   ├── __init__.py
│   │   ├── base.py         # 抽象基类 RecommendEngine
│   │   └── bkt_engine.py   # BKT算法实现
│   ├── user_service.py     # 用户业务逻辑
│   └── grader_service.py   # 判题服务
│
├── repositories/              # 数据访问层
│   ├── __init__.py
│   ├── user_repo.py        # 用户数据读写
│   └── question_repo.py   # 题库加载与缓存
│
├── models/                    # 数据模型 (dataclass)
│   ├── __init__.py
│   ├── user.py             # User, UserState, AnswerHistory
│   └── question.py         # Question, QuestionCollection
│
├── templates/                 # HTML模板 (Jinja2)
│   ├── base.html            # 基础模板
│   ├── login.html           # 登录
│   ├── register.html        # 注册
│   ├── index.html           # 首页/刷题
│   ├── review_wrong.html    # 错题复习
│   ├── review_due.html      # 艾宾浩斯复习
│   ├── favorites.html       # 收藏
│   └── stats.html           # 统计
│
├── questions/                 # 题库 (只读)
│   ├── math1.json          # 高等数学
│   ├── linalg.json         # 线性代数
│   ├── prob.json           # 概率论
│   ├── math_proof.json    # 高等数学证明题
│   ├── linalg_proof.json  # 线性代数证明题
│   └── prob_proof.json    # 概率论证明题
│
├── data/                      # 用户数据
│   ├── users_index.json    # 用户索引
│   └── user_*.json         # 用户进度数据
│
├── bkt_core.py               # 遗留: 旧版BKT逻辑 (逐步迁移)
├── db.py                     # 遗留: 数据库交互 (逐步迁移)
└── venv/                     # Python虚拟环境
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

## 架构分层

```
┌─────────────────────────────────────┐
│         Controllers (路由层)          │
│   auth.py, question.py, review.py   │
├─────────────────────────────────────┤
│         Services (业务逻辑层)         │
│  user_service, grader, recommend    │
├─────────────────────────────────────┤
│       Repositories (数据访问层)       │
│      user_repo, question_repo        │
├─────────────────────────────────────┤
│         Models (数据模型层)           │
│         User, Question               │
└─────────────────────────────────────┘
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

## 核心模块说明

### app.py
应用入口，负责初始化和注册蓝图。

```python
from controllers import create_auth_controller, create_question_controller, ...

app.register_blueprint(auth_bp)
app.register_blueprint(question_bp)
```

### config.py
集中管理配置: 路径、BKT参数、题库映射等。

### controllers/
处理HTTP请求，返回模板渲染的HTML。

| 模块 | 职责 |
|------|------|
| auth.py | 登录、注册、退出 |
| question.py | 首页、答题、科目切换 |
| review.py | 错题复习、艾宾浩斯、收藏 |
| stats.py | 统计、重置、导出数据 |

### services/
业务逻辑，可被控制器调用。

| 模块 | 职责 |
|------|------|
| recommend/ | 推荐引擎 (BKT实现) |
| user_service.py | 用户注册、登录、答题记录 |
| grader_service.py | 判题 (numeric/formula/string) |

### repositories/
数据持久化。

| 模块 | 职责 |
|------|------|
| user_repo.py | 用户数据读写 (JSON) |
| question_repo.py | 题库加载与内存缓存 |

### models/
数据结构定义，使用dataclass提高性能。

| 类 | 职责 |
|----|------|
| User | 用户完整数据模型 |
| UserState | 用于推荐引擎的用户状态 |
| AnswerHistory | 答题历史记录 |
| Question | 题目模型 |
| QuestionCollection | 题目集合+索引 |

## 推荐引擎扩展

系统使用抽象接口设计，便于后期替换为深度学习模型:

```python
# services/recommend/base.py
class RecommendEngine(ABC):
    @abstractmethod
    def recommend(self, user_state, questions, available_qids):
        pass

    @abstractmethod
    def update(self, user_state, question, is_correct, **extra_data):
        pass

    @abstractmethod
    def get_name(self):
        pass
```

切换引擎:
```python
from services.recommend import register_engine, set_engine

register_engine('dl', MyDeepLearningEngine())
set_engine('dl')
```

## AI训练数据

答题历史记录包含丰富的特征:

```json
{
  "qid": "m1_001",
  "user_answer": "2",
  "correct": true,
  "timestamp": "2024-01-01T10:00:00",
  "time_spent": 15.3,
  "question_difficulty": 0.6,
  "question_type": "fill_in",
  "knowledge_tags": ["极限计算"],
  "subject": "高等数学",
  "chapter": "极限"
}
```

导出训练数据: `/export_training_data`

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
  "favorites": ["m1_005"],
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
  "history": [...]
}
```

## 代码规范
- 使用 f-string
- 4空格缩进
- 类型注解 (Type Hints)
- 中文注释
- 分层清晰: 控制器 → 服务 → 仓库 → 模型

## 注意事项
1. LaTeX 在 JSON 中需双反斜杠: `\\frac`
2. 推荐引擎通过 `services/recommend/` 扩展
3. 题库加载后缓存在内存中，提升性能
4. 密码使用 bcrypt 哈希存储

## 部署
1. `git push` 触发 GitHub Actions
2. PythonAnywhere 自动 pull 并重启

## 外部资源
- KaTeX: https://cdn.jsdelivr.net/npm/katex@0.16.10
- MathLive: https://cdn.jsdelivr.net/npm/mathlive@0.100.0
