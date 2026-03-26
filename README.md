# 智能考研数学刷题系统

## 简介

基于 BKT (Bayesian Knowledge Tracing) + 遗忘曲线的智能考研数学刷题系统，支持高等数学、线性代数、概率论三个科目。

采用分层架构设计，便于后期扩展深度学习推荐引擎。

## 功能特点

- **智能推荐**：基于遗忘曲线驱动的有效掌握度推荐题目
- **错题本**：记录并复习答错的题目
- **遗忘曲线**：答对后掌握度随时间自动衰减，低时自动推荐复习
- **用户账号**：支持注册登录，数据持久化
- **收藏功能**：收藏重点题目
- **学习统计**：查看学习进度和正确率
- **考前突击**：集中练习模式，快速过2-3轮
- **AI准备**：答题数据支持导出用于深度学习训练

## 技术架构

```
Controllers (路由) → Services (业务) → Repositories (数据) → Models (模型)
```

- **Controllers**: auth, question, review, stats
- **Services**: recommend (可替换), user_service, grader_service
- **Repositories**: user_repo, question_repo
- **Models**: User, Question (dataclass)

## 快速开始

```bash
# 克隆项目
git clone <repo-url>
cd next-problem

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制示例文件并修改）
cp .env.example .env

# 运行
python app.py
```

> 注意：`.env` 文件包含敏感密钥，请勿提交到 Git。`.env` 已在 `.gitignore` 中忽略。

访问 http://localhost:5000

## 题库

| 科目 | 题目数 |
|------|--------|
| 高等数学 | 260+ |
| 线性代数 | 76+ |
| 概率论 | 64+ |

另有证明题库可选。

## 部署

项目已配置 GitHub Actions，自动部署到 PythonAnywhere。

### 生产环境配置

在 PythonAnywhere 后台设置环境变量：

```
Web 页面 → 配置 → 环境变量
- SECRET_KEY: 生成一个强随机密钥
- DEPLOY_KEY: 部署验证密钥（可选）
```

生成密钥：
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## 后期扩展

系统预留了推荐引擎接口，可轻松替换为深度学习模型：

```python
from services.recommend import register_engine, set_engine

register_engine('dl', MyDeepLearningEngine())
set_engine('dl')
```

## 遗忘曲线算法

系统采用遗忘曲线驱动的推荐机制：

```
有效掌握度 = mastery × e^(-t/τ)
```

- τ = 7天（遗忘曲线时间常数）
- 答对后记录 last_reviewed，BKT 更新 knowledge_state
- 遗忘曲线根据时间自动衰减有效掌握度
- 推荐时计算有效掌握度，优先推荐衰减严重的题目

### 冷启动优化
新知识点首次遇到时，last_reviewed 直接设为当前时间，确保遗忘曲线正常生效。

### 难度融入推荐
推荐算法综合考虑：
- 有效掌握度（低 → 高优先级）
- 题目难度与掌握度的差距（小 → 高优先级）

### 考前突击模式
访问 `/cram?rounds=2` 可进入考前突击模式：
- 临时提升推荐频率，快速多轮复习
- 不影响正常 BKT 知识状态
- 适合考前集中复习
