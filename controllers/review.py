"""
复习控制器 - 错题复习、艾宾浩斯复习、收藏
"""
from datetime import datetime, timedelta
from flask import Blueprint, request, redirect, url_for, flash, session, render_template

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
            h["qid"] for h in user.history
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
        else:
            flash(f"回答错误。正确答案：{question.get('answer', '')}", "wrong")

        user_service.save_user(user)
        return redirect(url_for("review.review_wrong"))

    @review_bp.route("/review_due")
    def review_due():
        """艾宾浩斯复习"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        subject = request.args.get("subject", "高等数学")
        coll = question_repo.get_by_subject(subject, subject_files)

        now = datetime.now()
        due_qids = set()

        for h in user.history:
            if h.get("correct") and h.get("next_review"):
                try:
                    next_review = datetime.fromisoformat(h["next_review"])
                    if next_review <= now:
                        due_qids.add(h["qid"])
                except:
                    continue

        due_questions = [q for q in coll.questions if q.id in due_qids]

        return render_template(
            "review_due.html",
            questions=due_questions,
            current_subject=subject,
            subjects=list(subject_files.keys())
        )

    @review_bp.route("/answer_due", methods=["POST"])
    def answer_due():
        """艾宾浩斯答题提交"""
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
            return redirect(url_for("review.review_due"))

        is_correct = grader.check(question, user_answer)

        if is_correct:
            flash("回答正确！", "correct")
            # 更新复习状态
            for h in user.history:
                if h.get("qid") == qid and h.get("correct"):
                    review_count = h.get("review_count", 0) + 1
                    h["review_count"] = review_count
                    h["last_reviewed"] = datetime.now().isoformat()
                    from services.user_service import calculate_next_review_interval
                    interval = calculate_next_review_interval(review_count)
                    h["next_review"] = (datetime.now() + timedelta(days=interval)).isoformat()
                    break
        else:
            flash(f"回答错误。正确答案：{question.get('answer', '')}", "wrong")
            # 重置复习周期
            for h in user.history:
                if h.get("qid") == qid and h.get("correct"):
                    h["review_count"] = 0
                    h["next_review"] = datetime.now().isoformat()
                    break

        user_service.save_user(user)
        return redirect(url_for("review.review_due"))

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
        """切换收藏状态"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        if qid in user.favorites:
            user.favorites.remove(qid)
            flash("已取消收藏", "correct")
        else:
            user.favorites.append(qid)
            flash("已添加收藏", "correct")

        user_service.save_user(user)
        return redirect(url_for("question.index"))

    return review_bp
