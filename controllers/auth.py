"""
认证控制器 - 登录注册
"""
from flask import Blueprint, request, redirect, url_for, flash, render_template, session
from flask_login import login_user, logout_user, login_required, current_user

auth_bp = Blueprint("auth", __name__)


def create_auth_controller(user_service, bcrypt):
    """创建认证控制器"""

    @auth_bp.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

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
            return redirect(url_for("index"))

        return render_template("login.html")

    @auth_bp.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")

            if not username or not password:
                flash("请填写所有字段", "wrong")
                return redirect(url_for("auth.register"))

            if password != confirm:
                flash("两次密码不一致", "wrong")
                return redirect(url_for("auth.register"))

            try:
                user = user_service.register(username, password, bcrypt)
                login_user(user)
                session["user_id"] = user.user_id
                flash(f"注册成功！欢迎 {user.username}", "correct")
                return redirect(url_for("index"))
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
