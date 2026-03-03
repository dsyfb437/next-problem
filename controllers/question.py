"""
题目控制器 - 答题相关
"""
import random
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, session, render_template

question_bp = Blueprint("question", __name__)


def create_question_controller(user_service, question_repo, subject_files):
    """创建题目控制器"""

    current_subject = {"name": "高等数学", "collection": None}

    def load_subject_questions(subject_name: str):
        """加载科目题目"""
        if current_subject["name"] != subject_name or current_subject["collection"] is None:
            current_subject["name"] = subject_name
            current_subject["collection"] = question_repo.get_by_subject(
                subject_name, subject_files
            )
        return current_subject["collection"]

    @question_bp.route("/")
    def index():
        """首页"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        subject = request.args.get("subject", current_subject["name"])
        collection = load_subject_questions(subject)

        # 推荐题目
        from services.recommend import get_current_engine
        engine = get_current_engine()

        user_state = {
            "knowledge_state": user.knowledge_state,
            "answered_questions": user.answered_questions
        }

        available_qids = {q.id for q in collection.questions} - user.answered_questions
        question = engine.recommend(user_state, [q.to_dict() for q in collection.questions], available_qids)

        # 记录开始时间
        if question:
            session[f"q_start_{question['id']}"] = datetime.now().isoformat()

        # 打乱选择题选项
        if question and question.get("type") == "multiple_choice":
            question = _shuffle_options(question)

        # 统计
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
            subjects=list(subject_files.keys())
        )

    @question_bp.route("/select_subject")
    def select_subject():
        """切换科目"""
        subject = request.args.get("subject", "高等数学")
        if subject in subject_files:
            current_subject["name"] = subject
            current_subject["collection"] = question_repo.get_by_subject(subject, subject_files)
            flash(f"已切换到《{subject}》题库", "correct")
        return redirect(url_for("question.index", subject=subject))

    @question_bp.route("/answer", methods=["POST"])
    def answer():
        """提交答案"""
        user = user_service.get_user(session.get("user_id"))
        if not user:
            return redirect(url_for("auth.login"))

        qid = request.form.get("qid", "")
        user_answer = request.form.get("answer", "").strip()

        if not qid or not user_answer:
            flash("请输入答案", "wrong")
            return redirect(url_for("question.index"))

        # 获取题目
        from services.grader_service import get_grader
        grader = get_grader()

        # 从所有科目查找题目
        question = None
        for subject_name in subject_files.keys():
            coll = question_repo.get_by_subject(subject_name, subject_files)
            q = coll.get_by_id(qid)
            if q:
                question = q.to_dict()
                break

        if not question:
            flash("题目不存在", "wrong")
            return redirect(url_for("question.index"))

        # 判题
        is_correct = grader.check(question, user_answer)

        if is_correct:
            flash("回答正确！", "correct")
            user.correct_in_round.add(qid)
        else:
            flash(f"回答错误。正确答案：{question.get('answer', '')}", "wrong")

        # 计算答题时间
        start_time = session.get(f"q_start_{qid}")
        time_spent = None
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
                time_spent = (datetime.now() - start_dt).total_seconds()
            except:
                pass
            session.pop(f"q_start_{qid}", None)

        # 记录答题
        from config import REVIEW_INTERVALS
        from services.user_service import calculate_next_review_interval

        history_entry = {
            "qid": qid,
            "user_answer": user_answer,
            "correct": is_correct,
            "timestamp": datetime.now().isoformat(),
            "time_spent": time_spent,
            "question_difficulty": question.get("difficulty", 0.5),
            "question_type": question.get("type", "fill_in"),
            "knowledge_tags": question.get("knowledge_tags", []),
            "subject": question.get("subject", ""),
            "chapter": question.get("chapter", ""),
        }

        if is_correct:
            history_entry["review_count"] = 0
            history_entry["last_reviewed"] = datetime.now().isoformat()
            interval = calculate_next_review_interval(0)
            history_entry["next_review"] = (datetime.now() + timedelta(days=interval)).isoformat()

        user.history.append(history_entry)
        user.answered_questions.add(qid)

        # 更新知识点
        from services.recommend import get_current_engine
        engine = get_current_engine()
        engine.update(
            {"knowledge_state": user.knowledge_state, "answered_questions": user.answered_questions},
            question,
            is_correct
        )

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

        # 保存
        user_service.save_user(user)

        return redirect(url_for("question.index"))

    def _shuffle_options(question):
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

        # 获取题目
        question = None
        for subject_name in subject_files.keys():
            coll = question_repo.get_by_subject(subject_name, subject_files)
            q = coll.get_by_id(qid)
            if q:
                question = q.to_dict()
                break

        if not question:
            return jsonify({"status": "error", "message": "题目不存在"})

        # 记录为错误
        history_entry = {
            "qid": qid,
            "user_answer": "",
            "correct": False,
            "skipped": True,  # 标记为跳过
            "timestamp": datetime.now().isoformat(),
            "time_spent": None,
            "question_difficulty": question.get("difficulty", 0.5),
            "question_type": question.get("type", "fill_in"),
            "knowledge_tags": question.get("knowledge_tags", []),
            "subject": question.get("subject", ""),
            "chapter": question.get("chapter", ""),
        }

        user.history.append(history_entry)
        user.answered_questions.add(qid)

        # 统计
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in user.daily_stats:
            user.daily_stats[today] = {"answered": 0, "correct": 0}
        user.daily_stats[today]["answered"] += 1
        user.total_stats["total_answered"] = len(user.answered_questions)
        user.total_stats["total_correct"] = sum(1 for h in user.history if h.get("correct"))
        user.total_stats["last_active_date"] = today

        user_service.save_user(user)

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

        # 获取题目
        from services.grader_service import get_grader
        grader = get_grader()

        question = None
        for subject_name in subject_files.keys():
            coll = question_repo.get_by_subject(subject_name, subject_files)
            q = coll.get_by_id(qid)
            if q:
                question = q.to_dict()
                break

        if not question:
            return jsonify({"status": "error", "message": "题目不存在"})

        # 判题
        is_correct = grader.check(question, user_answer)

        # 计算答题时间
        start_time = session.get(f"q_start_{qid}")
        time_spent = None
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
                time_spent = (datetime.now() - start_dt).total_seconds()
            except:
                pass
            session.pop(f"q_start_{qid}", None)

        # 记录答题
        from services.user_service import calculate_next_review_interval

        history_entry = {
            "qid": qid,
            "user_answer": user_answer,
            "correct": is_correct,
            "timestamp": datetime.now().isoformat(),
            "time_spent": time_spent,
            "question_difficulty": question.get("difficulty", 0.5),
            "question_type": question.get("type", "fill_in"),
            "knowledge_tags": question.get("knowledge_tags", []),
            "subject": question.get("subject", ""),
            "chapter": question.get("chapter", ""),
        }

        if is_correct:
            history_entry["review_count"] = 0
            history_entry["last_reviewed"] = datetime.now().isoformat()
            interval = calculate_next_review_interval(0)
            history_entry["next_review"] = (datetime.now() + timedelta(days=interval)).isoformat()

        user.history.append(history_entry)
        user.answered_questions.add(qid)

        # 更新知识点
        from services.recommend import get_current_engine
        engine = get_current_engine()
        engine.update(
            {"knowledge_state": user.knowledge_state, "answered_questions": user.answered_questions},
            question,
            is_correct
        )

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

        return jsonify({
            "status": "ok",
            "correct": is_correct,
            "correct_answer": question.get("answer", "") if not is_correct else None
        })

    return question_bp
