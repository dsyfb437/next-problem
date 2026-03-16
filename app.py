"""
Flask应用入口 - 重构后版本

分层架构:
- controllers/  : 路由层，处理HTTP请求
- services/     : 业务逻辑层
- repositories/ : 数据访问层
- models/       : 数据模型
- templates/   : HTML模板
"""
import os
from flask import Flask
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

import config
from models.user import User
from repositories import UserRepository, get_question_repo
from services import UserService
from controllers import (
    create_auth_controller,
    create_question_controller,
    create_review_controller,
    create_stats_controller
)

# 加载环境变量
load_dotenv()

# 创建Flask应用
app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY

# 初始化扩展
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)  # CSRF 保护
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"

# 初始化仓库和服务
user_repo = UserRepository(config.DATA_DIR)
question_repo = get_question_repo()
user_service = UserService(user_repo)

# Flask-Login用户加载
@login_manager.user_loader
def load_user(user_id):
    return user_service.get_user(user_id)

# 注册蓝图
auth_bp = create_auth_controller(user_service, bcrypt)
question_bp = create_question_controller(user_service, question_repo, config.SUBJECT_FILES)
review_bp = create_review_controller(user_service, question_repo, config.SUBJECT_FILES)
stats_bp = create_stats_controller(user_service, question_repo, config.SUBJECT_FILES)

app.register_blueprint(auth_bp, url_prefix="/")
app.register_blueprint(question_bp, url_prefix="/")
app.register_blueprint(review_bp, url_prefix="/")
app.register_blueprint(stats_bp, url_prefix="/")

# 健康检查
@app.route("/health")
def health():
    return {"status": "ok"}

# 启动
if __name__ == "__main__":
    app.run(debug=config.DEBUG, host="0.0.0.0", port=5000)
