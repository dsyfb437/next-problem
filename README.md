# 智能考研数学刷题系统

## 简介

基于 BKT (Bayesian Knowledge Tracing) 算法的智能考研数学刷题系统，支持高等数学、线性代数、概率论三个科目。

## 功能特点

- **智能推荐**：基于知识点掌握度智能推荐题目
- **错题本**：记录并复习答错的题目
- **艾宾浩斯复习**：根据遗忘曲线自动安排复习
- **用户账号**：支持注册登录，数据持久化

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

## 部署

项目已配置 GitHub Actions，自动部署到 PythonAnywhere。

## 题库

- 高等数学：260 题
- 线性代数：76 题
- 概率论：64 题
