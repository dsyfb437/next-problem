"""
认证控制器 - 登录注册
"""
import re
from flask import Blueprint, request, redirect, url_for, flash, render_template, session
from flask_login import login_user, logout_user, login_required, current_user

auth_bp = Blueprint("auth", __name__)

# 输入验证规则
USERNAME_MIN_LEN = 3
USERNAME_MAX_LEN = 20
PASSWORD_MIN_LEN = 6
PASSWORD_MAX_LEN = 20


def create_auth_controller(user_service, bcrypt):
    """创建认证控制器"""

    @auth_bp.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("question.index"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            user = user_service.login(username, password, bcrypt)
            if not user:
                flash("用户名或密码错误", "wrong")
                return redirect(url_for("auth.login"))

            login_user(user)
            session["user_id"] = user.user_id
            flash(f"欢迎回来，{user.username}！", "correct")
            return redirect(url_for("question.index"))

        return render_template("login.html")

    @auth_bp.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("question.index"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")

            # 验证用户名长度
            if len(username) < USERNAME_MIN_LEN or len(username) > USERNAME_MAX_LEN:
                flash(f"用户名长度需在 {USERNAME_MIN_LEN}-{USERNAME_MAX_LEN} 个字符之间", "wrong")
                return redirect(url_for("auth.register"))

            # 验证用户名格式（只允许字母、数字、下划线）
            if not re.match(r"^\w+$", username):
                flash("用户名只能包含字母、数字和下划线", "wrong")
                return redirect(url_for("auth.register"))

            # 验证密码长度
            if len(password) < PASSWORD_MIN_LEN or len(password) > PASSWORD_MAX_LEN:
                flash(f"密码长度需在 {PASSWORD_MIN_LEN}-{PASSWORD_MAX_LEN} 个字符之间", "wrong")
                return redirect(url_for("auth.register"))

            if password != confirm:
                flash("两次密码不一致", "wrong")
                return redirect(url_for("auth.register"))

            try:
                user = user_service.register(username, password, bcrypt)
                login_user(user)
                session["user_id"] = user.user_id
                flash(f"注册成功！欢迎 {user.username}", "correct")
                return redirect(url_for("question.index"))
            except ValueError as e:
                flash(str(e), "wrong")
                return redirect(url_for("auth.register"))

        return render_template("register.html")

    @auth_bp.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("已退出登录", "correct")
        return redirect(url_for("auth.login"))

    return auth_bp
