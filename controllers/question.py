"""
题目控制器 - 答题相关
"""
import random
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from models.user import User, AnswerHistory
from utils import logger

question_bp = Blueprint("question", __name__)


def create_question_controller(user_service, question_repo, subject_files):
    """创建题目控制器"""

    DEFAULT_SUBJECT = "高等数学"

    # ==================== 公共函数 ====================

    def _get_question_by_id(qid: str) -> Optional[Dict[str, Any]]:
        """根据ID获取题目"""
        for subject_name in subject_files.keys():
            coll = question_repo.get_by_subject(subject_name, subject_files)
            q = coll.get_by_id(qid)
            if q:
                return q.to_dict()
        return None

    def _calculate_time_spent(qid: str) -> Optional[float]:
        """计算答题耗时"""
        start_time = session.get(f"q_start_{qid}")
        if not start_time:
            return None
        try:
            start_dt = datetime.fromisoformat(start_time)
            session.pop(f"q_start_{qid}", None)
            return (datetime.now() - start_dt).total_seconds()
        except ValueError:
            logger.warning(f"时间解析失败: qid={qid}, start_time={start_time}")
            return None

    def _record_answer(user: User, qid: str, question: Dict, is_correct: bool,
                      user_answer: str = "", time_spent: Optional[float] = None) -> None:
        """记录答题结果（公共逻辑）"""
        now = datetime.now().isoformat()

        history_entry = AnswerHistory(
            qid=qid,
            user_answer=user_answer,
            correct=is_correct,
            timestamp=now,
            time_spent=time_spent,
            question_difficulty=question.get("difficulty", 0.5),
            question_type=question.get("type", "fill_in"),
            knowledge_tags=question.get("knowledge_tags", []),
            subject=question.get("subject", ""),
            chapter=question.get("chapter", ""),
        )

        if is_correct:
            history_entry.last_reviewed = now

        user.history.append(history_entry)
        user.answered_questions.add(qid)

        # 考前突击模式：不更新永久状态
        cram_mode = session.get("cram_mode", False)
        if cram_mode:
            # 突击模式只更新临时状态
            session["cram_questions_answered"] = session.get("cram_questions_answered", 0) + 1
        else:
            # 正常模式：更新知识点（包含遗忘曲线）
            from services.recommend import get_current_engine
            engine = get_current_engine()
            user_state = {
                "knowledge_state": user.knowledge_state,
                "last_reviewed": user.last_reviewed,
                "answered_questions": user.answered_questions
            }
            engine.update(user_state, question, is_correct)
            user.knowledge_state = user_state["knowledge_state"]
            user.last_reviewed = user_state.get("last_reviewed", user.last_reviewed)

        # 统计
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in user.daily_stats:
            user.daily_stats[today] = {"answered": 0, "correct": 0}
        user.daily_stats[today]["answered"] += 1
        if is_correct:
            user.daily_stats[today]["correct"] += 1
        user.total_stats["total_answered"] = len(user.answered_questions)
        user.total_stats["total_correct"] = sum(1 for h in user.history if h.get("correct"))
        user.total_stats["last_active_date"] = today

        user_service.save_user(user)

    def _shuffle_options(question: Dict) -> Dict:
        """打乱选择题选项"""
        options = question.get("options", [])
        correct_idx = question.get("correct_option", 0)

        indexed_options = list(enumerate(options))
        random.shuffle(indexed_options)

        new_correct = None
        shuffled_options = []
        for new_idx, (old_idx, opt) in enumerate(indexed_options):
            shuffled_options.append(opt)
            if old_idx == correct_idx:
                new_correct = new_idx

        question["options"] = shuffled_options
        question["correct_option"] = new_correct
        return question

    # ==================== 路由 ====================

    @question_bp.route("/")
    def index():
        """首页"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        subject = request.args.get("subject", DEFAULT_SUBJECT)
        collection = question_repo.get_by_subject(subject, subject_files)

        # 检查当前批次是否完成
        batch_remaining = session.get("batch_remaining", 0)
        batch_total = session.get("batch_total", 0)

        if batch_remaining <= 0 and batch_total > 0:
            batch_correct = session.get("batch_correct", 0)
            batch_total_actual = session.get("batch_total_actual", 0)
            session.pop("batch_remaining", None)
            session.pop("batch_total", None)
            session.pop("batch_correct", None)
            session.pop("batch_total_actual", None)
            return render_template(
                "batch_complete.html",
                batch_correct=batch_correct,
                batch_total=batch_total_actual,
                subjects=list(subject_files.keys())
            )

        # 检查是否有未完成的当前题目（刷新不换题）
        current_qid = session.get("current_qid")
        question = None
        if current_qid:
            q_already_answered = any(h.get("qid") == current_qid for h in user.history)
            if not q_already_answered:
                question = _get_question_by_id(current_qid)

        # 如果没有当前题目或已答完，推荐新题目
        if not question:
            from services.recommend import get_current_engine
            engine = get_current_engine()

            # 考前突击模式：使用临时状态
            cram_mode = session.get("cram_mode", False)
            if cram_mode:
                # 使用原始状态（突击模式不永久改变知识状态）
                user_state = {
                    "knowledge_state": session.get("cram_original_knowledge_state", user.knowledge_state),
                    "last_reviewed": session.get("cram_original_last_reviewed", user.last_reviewed),
                    "answered_questions": user.answered_questions
                }
                cram_rounds = session.get("cram_rounds", 2)
            else:
                user_state = {
                    "knowledge_state": user.knowledge_state,
                    "last_reviewed": user.last_reviewed,
                    "answered_questions": user.answered_questions
                }
                cram_rounds = 0

            available_qids = {q.id for q in collection.questions} - user.answered_questions
            question = engine.recommend(user_state, [q.to_dict() for q in collection.questions], available_qids, cram_rounds=cram_rounds)

            if question:
                session["current_qid"] = question["id"]
                session[f"q_start_{question['id']}"] = datetime.now().isoformat()
                if batch_remaining > 0:
                    batch_remaining -= 1
                    session["batch_remaining"] = batch_remaining

        if question and question.get("type") == "multiple_choice":
            question = _shuffle_options(question)

        total = len(user.answered_questions & {q.id for q in collection.questions})
        correct = sum(1 for h in user.history if h.get("correct") and h.get("qid") in {q.id for q in collection.questions})

        return render_template(
            "index.html",
            question=question,
            user=user,
            current_subject=subject,
            total_answered=total,
            correct_count=correct,
            wrong_count=total - correct,
            subjects=list(subject_files.keys()),
            batch_remaining=batch_remaining,
            batch_total=batch_total
        )

    @question_bp.route("/select_subject")
    def select_subject():
        """切换科目"""
        subject = request.args.get("subject", DEFAULT_SUBJECT)
        if subject in subject_files:
            flash(f"已切换到《{subject}》题库", "correct")
        return redirect(url_for("question.index", subject=subject))

    @question_bp.route("/start_batch", methods=["POST"])
    def start_batch():
        """开始批次练习"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        batch_size = request.form.get("batch_size", type=int, default=10)
        batch_size = max(1, min(batch_size, 50))

        session["batch_remaining"] = batch_size
        session["batch_total"] = batch_size
        session["batch_correct"] = 0
        session["batch_total_actual"] = 0

        flash(f"开始练习 {batch_size} 题", "correct")
        return redirect(url_for("question.index"))

    @question_bp.route("/cram")
    def cram():
        """考前突击模式"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        rounds = request.args.get("rounds", type=int, default=2)
        rounds = max(1, min(rounds, 5))  # 限制1-5轮

        # 保存当前状态用于突击模式
        session["cram_mode"] = True
        session["cram_rounds"] = rounds
        session["cram_current_round"] = 1
        session["cram_questions_answered"] = 0
        session["cram_original_knowledge_state"] = dict(user.knowledge_state)
        session["cram_original_last_reviewed"] = dict(user.last_reviewed)

        flash(f"开始考前突击模式（第1/{rounds}轮）", "correct")
        return redirect(url_for("question.index"))

    @question_bp.route("/answer_skip", methods=["POST"])
    def answer_skip():
        """我不会 - 跳过此题并记为错误"""
        from flask import jsonify
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return jsonify({"status": "error", "message": "请先登录"})

        qid = request.json.get("qid", "") if request.is_json else request.form.get("qid", "")

        if not qid:
            return jsonify({"status": "error", "message": "题目ID无效"})

        question = _get_question_by_id(qid)
        if not question:
            return jsonify({"status": "error", "message": "题目不存在"})

        _record_answer(user, qid, question, is_correct=False)

        session.pop("current_qid", None)
        return jsonify({"status": "ok", "message": "已收入错题本"})

    @question_bp.route("/answer_ajax", methods=["POST"])
    def answer_ajax():
        """AJAX提交答案"""
        from flask import jsonify
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return jsonify({"status": "error", "message": "请先登录"})

        qid = request.json.get("qid", "") if request.is_json else request.form.get("qid", "")
        user_answer = (request.json.get("answer", "") if request.is_json else request.form.get("answer", "")).strip()

        if not qid or not user_answer:
            return jsonify({"status": "error", "message": "请输入答案"})

        question = _get_question_by_id(qid)
        if not question:
            return jsonify({"status": "error", "message": "题目不存在"})

        from services.grader_service import get_grader
        grader = get_grader()
        is_correct = grader.check(question, user_answer)

        time_spent = _calculate_time_spent(qid)
        _record_answer(user, qid, question, is_correct, user_answer, time_spent)

        correct_answer = None
        if not is_correct:
            if question.get("type") == "multiple_choice" and question.get("options"):
                idx = question.get("correct_option", 0)
                opts = question.get("options", [])
                correct_answer = opts[idx] if idx < len(opts) else str(idx)
            else:
                correct_answer = question.get("answer", "")

        session.pop("current_qid", None)

        batch_remaining = session.get("batch_remaining", 0)
        batch_correct = session.get("batch_correct", 0)
        if is_correct:
            batch_correct += 1
            session["batch_correct"] = batch_correct

        return jsonify({
            "status": "ok",
            "correct": is_correct,
            "correct_answer": correct_answer,
            "batch_remaining": batch_remaining
        })

    @question_bp.route("/end_cram", methods=["POST"])
    def end_cram():
        """结束考前突击模式"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        cram_mode = session.pop("cram_mode", False)
        cram_rounds = session.pop("cram_rounds", 2)
        cram_current_round = session.pop("cram_current_round", 1)
        cram_questions_answered = session.pop("cram_questions_answered", 0)
        session.pop("cram_original_knowledge_state", None)
        session.pop("cram_original_last_reviewed", None)

        if cram_mode and cram_current_round < cram_rounds:
            # 还有下一轮
            session["cram_mode"] = True
            session["cram_rounds"] = cram_rounds
            session["cram_current_round"] = cram_current_round + 1
            session["cram_questions_answered"] = 0
            flash(f"进入第{cram_current_round + 1}/{cram_rounds}轮", "correct")
        else:
            # 突击模式结束
            flash(f"考前突击完成！共回答{cram_questions_answered}题（不计入正常进度）", "correct")

        return redirect(url_for("question.index"))

    return question_bp
