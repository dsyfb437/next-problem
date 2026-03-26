"""
复习控制器 - 错题复习、收藏
"""
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from utils import logger

review_bp = Blueprint("review", __name__)


def create_review_controller(user_service, question_repo, subject_files):
    """创建复习控制器"""

    @review_bp.route("/review_wrong")
    def review_wrong():
        """错题复习"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        subject = request.args.get("subject", "高等数学")
        coll = question_repo.get_by_subject(subject, subject_files)

        # 获取错题
        wrong_qids = {
            h.get("qid") for h in user.history
            if not h.get("correct", False) and not h.get("reviewed", False)
        }
        wrong_questions = [q for q in coll.questions if q.id in wrong_qids]

        return render_template(
            "review_wrong.html",
            questions=wrong_questions,
            current_subject=subject,
            subjects=list(subject_files.keys())
        )

    @review_bp.route("/answer_review", methods=["POST"])
    def answer_review():
        """错题答题提交"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        qid = request.form.get("qid", "")
        user_answer = request.form.get("answer", "").strip()

        from services.grader_service import get_grader
        grader = get_grader()

        # 获取题目
        question = None
        for subject_name in subject_files.keys():
            coll = question_repo.get_by_subject(subject_name, subject_files)
            q = coll.get_by_id(qid)
            if q:
                question = q.to_dict()
                break

        if not question:
            flash("题目不存在", "wrong")
            return redirect(url_for("review.review_wrong"))

        is_correct = grader.check(question, user_answer)

        if is_correct:
            flash("回答正确！", "correct")
            user.mark_reviewed(qid)
            # 更新知识点掌握度（调用BKT引擎）
            from services.recommend import get_current_engine
            engine = get_current_engine()
            user_state = {
                "knowledge_state": user.knowledge_state,
                "last_reviewed": user.last_reviewed,
                "answered_questions": user.answered_questions
            }
            engine.update(user_state, question, True)
            user.knowledge_state = user_state["knowledge_state"]
            user.last_reviewed = user_state.get("last_reviewed", user.last_reviewed)
        else:
            flash(f"回答错误。正确答案：{question.get('answer', '')}", "wrong")

        user_service.save_user(user)
        return redirect(url_for("review.review_wrong"))

    @review_bp.route("/review_due")
    def review_due():
        """知识点掌握度统计（基于遗忘曲线）"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        from services.recommend import apply_forgetting_curve

        # 计算每个知识点的有效掌握度
        effective_mastery = {}
        for tag, mastery in user.knowledge_state.items():
            last = user.get_tag_last_reviewed(tag)
            effective = apply_forgetting_curve(mastery, last)
            effective_mastery[tag] = effective

        # 按有效掌握度排序，低于0.5的为需要加强的知识点
        weak_tags = [(tag, eff) for tag, eff in effective_mastery.items() if eff < 0.5]
        weak_tags.sort(key=lambda x: x[1])

        # 知识点列表（用于显示）
        all_tags = sorted(effective_mastery.items(), key=lambda x: x[1])

        return render_template(
            "review_due.html",
            weak_tags=weak_tags[:10],
            all_tags=all_tags,
            current_subject=request.args.get("subject", "高等数学"),
            subjects=list(subject_files.keys())
        )

    @review_bp.route("/favorites")
    def favorites():
        """收藏列表"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        subject = request.args.get("subject", "高等数学")
        coll = question_repo.get_by_subject(subject, subject_files)

        fav_questions = [q for q in coll.questions if q.id in user.favorites]

        return render_template(
            "favorites.html",
            questions=fav_questions,
            current_subject=subject,
            subjects=list(subject_files.keys())
        )

    @review_bp.route("/favorite/toggle/<qid>")
    def favorite_toggle(qid):
        """切换收藏状态 - 返回JSON"""
        from flask import jsonify

        user = user_service.get_user(session.get("user_id"))
        if not user:
            return jsonify({"status": "error", "message": "请先登录"})

        favorited = False
        if qid in user.favorites:
            user.favorites.remove(qid)
        else:
            user.favorites.append(qid)
            favorited = True

        user_service.save_user(user)
        return jsonify({"status": "ok", "favorited": favorited})

    return review_bp
