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

        # 艾宾浩斯记忆曲线数据
        # 计算基于复习间隔的记忆保持率
        memory_curve_labels = ["立即", "1天后", "2天后", "4天后", "7天后", "15天后", "30天后"]
        memory_curve_values = []

        # 理论艾宾浩斯曲线: R = e^(-t/S), S=1 (标准稳定性)
        for days_passed in [0, 1, 2, 4, 7, 15, 30]:
            if days_passed == 0:
                memory_curve_values.append(100)
            else:
                # 使用艾宾浩斯公式计算保持率
                retention = 100 * (2.718 ** (-days_passed / 3))
                memory_curve_values.append(round(retention, 1))

        # 获取用户当前需要复习的题目数量
        due_count = 0
        for h in user.history:
            if h.get("next_review"):
                try:
                    next_review = datetime.fromisoformat(h.get("next_review"))
                    if next_review <= datetime.now():
                        due_count += 1
                except:
                    pass

        # 最近做题记录
        recent_history = []
        if user.history:
            # 按时间倒序取最近10条
            sorted_history = sorted(user.history, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]
            for h in sorted_history:
                qid = h.get("qid", "")
                # 查找题目内容
                question_text = ""
                question_full_text = ""
                question_answer = ""
                knowledge_tags = []
                for subject_name in subject_files.keys():
                    coll = question_repo.get_by_subject(subject_name, subject_files)
                    q = coll.get_by_id(qid)
                    if q:
                        question_text = q.to_dict().get("question_text", "")[:50] + "..."
                        question_full_text = q.to_dict().get("question_text", "")
                        question_answer = q.to_dict().get("answer", "")
                        knowledge_tags = q.knowledge_tags if hasattr(q, 'knowledge_tags') else []
                        break
                recent_history.append({
                    "qid": qid,
                    "question_text": question_text,
                    "question_full_text": question_full_text,
                    "question_answer": question_answer,
                    "knowledge_tags": knowledge_tags,
                    "correct": h.get("correct", False),
                    "user_answer": h.get("user_answer", ""),
                    "timestamp": h.get("timestamp", "")[:10]
                })

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
            knowledge=user.knowledge_state,
            memory_curve_labels=memory_curve_labels,
            memory_curve_values=memory_curve_values,
            due_count=due_count,
            recent_history=recent_history
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
