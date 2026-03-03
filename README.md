# 智能考研数学刷题系统

## 简介

基于 BKT (Bayesian Knowledge Tracing) 算法的智能考研数学刷题系统，支持高等数学、线性代数、概率论三个科目。

采用分层架构设计，便于后期扩展深度学习推荐引擎。

## 功能特点

- **智能推荐**：基于知识点掌握度智能推荐题目
- **错题本**：记录并复习答错的题目
- **艾宾浩斯复习**：根据遗忘曲线自动安排复习
- **用户账号**：支持注册登录，数据持久化
- **收藏功能**：收藏重点题目
- **学习统计**：查看学习进度和正确率
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

# 运行
python app.py
```

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

## 后期扩展

系统预留了推荐引擎接口，可轻松替换为深度学习模型：

```python
from services.recommend import register_engine, set_engine

register_engine('dl', MyDeepLearningEngine())
set_engine('dl')
```
