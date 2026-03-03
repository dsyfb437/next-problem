"""
统计控制器
"""
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, make_response

stats_bp = Blueprint("stats", __name__)


def create_stats_controller(user_service, question_repo, subject_files):
    """创建统计控制器"""

    @stats_bp.route("/stats")
    def show_stats():
        """学习统计页面"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        subject = request.args.get("subject", "高等数学")
        coll = question_repo.get_by_subject(subject, subject_files)

        # 统计
        subject_qids = {q.id for q in coll.questions}
        answered = user.answered_questions & subject_qids
        total = len(answered)

        correct = sum(1 for h in user.history if h.get("qid") in answered and h.get("correct"))
        wrong = total - correct
        correct_rate = round(correct / total * 100, 1) if total > 0 else 0

        # 每日数据
        days = 7
        daily_data = []
        today = datetime.now()
        for i in range(days):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            stats = user.daily_stats.get(date, {"answered": 0, "correct": 0})
            daily_data.append({
                "date": date,
                "answered": stats.get("answered", 0),
                "correct": stats.get("correct", 0)
            })
        daily_data.reverse()

        return render_template(
            "stats.html",
            user=user,
            current_subject=subject,
            subjects=list(subject_files.keys()),
            total=total,
            correct=correct,
            wrong=wrong,
            correct_rate=correct_rate,
            daily_data=daily_data,
            knowledge=user.knowledge_state
        )

    @stats_bp.route("/export_training_data")
    def export_training_data():
        """导出AI训练数据"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        training_data = {
            "user_id": user.user_id,
            "username": user.username,
            "exported_at": datetime.now().isoformat(),
            "total_records": len(user.history),
            "records": [h.to_dict() for h in user.history] if user.history and hasattr(user.history[0], "to_dict") else user.history
        }

        response = make_response(json.dumps(training_data, ensure_ascii=False, indent=2))
        response.headers["Content-Disposition"] = f"attachment; filename=training_data_{user.user_id}.json"
        response.headers["Content-Type"] = "application/json"
        return response

    @stats_bp.route("/reset")
    def reset():
        """完全重置"""
        user_id = session.get("user_id")
        if user_id:
            from pathlib import Path
            import os
            file_path = Path("data") / f"user_{user_id}.json"
            if file_path.exists():
                os.remove(file_path)
            session.clear()
            flash("已完全重置进度", "correct")
        return redirect(url_for("auth.login"))

    @stats_bp.route("/restart")
    def restart():
        """重置题目进度"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        user.answered_questions = set()
        user.correct_in_round = set()
        for h in user.history:
            h.pop("reviewed", None)

        user_service.save_user(user)
        flash("已重置题目进度，知识点保留", "correct")
        return redirect(url_for("question.index"))

    return stats_bp
