"""Adaptive testing sessions: sprint / day1 / day2 / cat / free over Redis state."""

from __future__ import annotations

import asyncio
import random
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.notifier import send_error_alert
from app.core.math import DynamicEloTracker, ItemResponseTheory, SmartErrorLogEngine
from app.db.base import redis_get_json, redis_set_json
from app.models import (
    ChildAccount,
    ErrorLogItem,
    QuestionTemplate,
    Subject,
    UserResponseLog,
)
from app.services.clone_generator_service import (
    generate_params,
    render_question,
    safe_eval,
)

IRT = ItemResponseTheory
ELO = DynamicEloTracker
SM2 = SmartErrorLogEngine

SESSION_TTL_SECONDS = 7200
SESSION_LOCK_TTL_SECONDS = 5
SESSION_LOCK_RETRIES = 10
SESSION_LOCK_RETRY_DELAY = 0.15


async def _acquire_session_lock(redis, session_id: str) -> bool:
    """SETNX-блокировка на запись состояния сессии (H2: защита от гонок)."""
    return bool(
        await redis.set(f"session_lock:{session_id}", "1", nx=True, ex=SESSION_LOCK_TTL_SECONDS)
    )


def _with_session_lock(redis, session_id: str):
    """Асинхронный контекст-менеджер: захватывает блокировку с ретраями."""
    import contextlib

    @contextlib.asynccontextmanager
    async def _lock():
        acquired = False
        for _ in range(SESSION_LOCK_RETRIES):
            if await _acquire_session_lock(redis, session_id):
                acquired = True
                break
            await asyncio.sleep(SESSION_LOCK_RETRY_DELAY)
        if not acquired:
            raise PermissionError("Сессия занята, попробуйте ещё раз")
        try:
            yield
        finally:
            await redis.delete(f"session_lock:{session_id}")

    return _lock()

MODE_SUBJECT: dict[str, str | None] = {
    "sprint": "quant",
    "day1": "math",
    "day2": "lang",
    "cat": "nat_sci",
    "free": None,  # random subject
}

MODE_MAX_QUESTIONS: dict[str, int] = {
    "sprint": 10,
    "day1": 8,
    "day2": 6,
    "cat": 12,
    "free": 10,
}

SUBJECT_CODES = ("math", "quant", "nat_sci", "lang")

THETA_ATTR: dict[str, str] = {
    "math": "theta_math",
    "quant": "theta_quant",
    "nat_sci": "theta_nat_sci",
    "lang": "theta_lang",
}

STREAK_BONUS_ELO = 50.0
CONSECUTIVE_ERROR_ALERT_AT = 3


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_subject(db: AsyncSession, code: str) -> Subject:
    subject = await db.scalar(select(Subject).where(Subject.code == code))
    if subject is None:
        raise ValueError(f"subject {code!r} is not configured")
    return subject


async def _get_subject_of_template(db: AsyncSession, template: QuestionTemplate) -> Subject:
    subject = await db.get(Subject, template.subject_id)
    if subject is None:
        raise ValueError(f"subject #{template.subject_id} is not configured")
    return subject


async def start_session(db: AsyncSession, redis, child: ChildAccount, mode: str) -> dict:
    """Create a session in Redis and return the first question."""
    if mode not in MODE_MAX_QUESTIONS:
        raise ValueError(f"unknown mode {mode!r}")
    subject_code = MODE_SUBJECT.get(mode)
    if subject_code is None:
        subject_code = random.choice(SUBJECT_CODES)
    await _get_subject(db, subject_code)
    session_id = str(uuid4())
    data = {
        "child_id": child.id,
        "mode": mode,
        "subject_code": subject_code,
        "asked": [],
        "max_questions": MODE_MAX_QUESTIONS[mode],
        "answers": [],
        "consecutive_errors": 0,
        "created_at": utc_now().isoformat(),
    }
    await redis_set_json(redis, f"session:{session_id}", data, SESSION_TTL_SECONDS)
    question = await get_next_question(db, redis, session_id, child)
    return question


async def get_next_question(
    db: AsyncSession, redis, session_id: str, child: ChildAccount
) -> dict | None:
    """Pick the next question for the session (never repeats; marks asked in Redis)."""
    async with _with_session_lock(redis, session_id):
        session = await redis_get_json(redis, f"session:{session_id}")
        if session is None:
            return None
        asked: list[int] = session["asked"]
        max_questions: int = session["max_questions"]
        if len(asked) >= max_questions:
            return None

        subject_code: str = session["subject_code"]
        mode: str = session["mode"]
        subject = await _get_subject(db, subject_code)
        stmt = select(QuestionTemplate).where(QuestionTemplate.subject_id == subject.id)
        if asked:
            stmt = stmt.where(QuestionTemplate.id.not_in(asked))
        candidates = list((await db.scalars(stmt)).all())
        if not candidates:
            # Pool exhausted: recycle with a fresh clone. Exclude only the most
            # recent template so the immediate repeat is avoided when possible.
            stmt = select(QuestionTemplate).where(QuestionTemplate.subject_id == subject.id)
            if len(asked) > 1:
                stmt = stmt.where(QuestionTemplate.id != asked[-1])
            candidates = list((await db.scalars(stmt)).all())
        if not candidates:
            return None

        if mode == "cat":
            theta = float(getattr(child, THETA_ATTR[subject_code]))
            items = [
                {"id": str(t.id), "b": t.difficulty_b, "a": t.discrimination_a}
                for t in candidates
            ]
            chosen = IRT.select_next_question(theta, items)
            template = next(t for t in candidates if str(t.id) == chosen["id"])
        else:
            template = await _pick_balanced(db, candidates, asked)

        asked.append(template.id)
        session["asked"] = asked
        await redis_set_json(redis, f"session:{session_id}", session, SESSION_TTL_SECONDS)

        params = generate_params(template.param_schema)
        rendered = render_question(template, params)
        skill = template.micro_skill
        return {
            "session_id": session_id,
            "question_id": len(asked),
            "template_id": template.id,
            "micro_skill": {
                "id": skill.id,
                "code": skill.code,
                "name_ru": skill.name_ru,
                "name_kk": skill.name_kk,
            },
            "question_text": rendered["question_text"],
            "choices": rendered["choices"],
            "answer_type": rendered["answer_type"],
            "params": params,
            "time_limit_sec": subject.per_question_sec,
            "mode": mode,
            "total_questions": max_questions,
            "progress": round(len(asked) / max_questions, 4),
        }


async def _pick_balanced(
    db: AsyncSession, candidates: list[QuestionTemplate], asked: list[int]
) -> QuestionTemplate:
    """Random pick with micro-skill balance: prefer the skill least used so far."""
    asked_skills: dict[int, int] = {}
    if asked:
        rows = await db.execute(
            select(QuestionTemplate.id, QuestionTemplate.micro_skill_id).where(
                QuestionTemplate.id.in_(asked)
            )
        )
        for _, skill_id in rows.all():
            asked_skills[skill_id] = asked_skills.get(skill_id, 0) + 1

    groups: dict[int, list[QuestionTemplate]] = {}
    for t in candidates:
        groups.setdefault(t.micro_skill_id, []).append(t)

    usable = [skill_id for skill_id, items in groups.items() if items]
    if not usable:
        return random.choice(candidates)
    least_used = min(usable, key=lambda s: asked_skills.get(s, 0))
    return random.choice(groups[least_used])


def _correct_answer_for(template: QuestionTemplate, params: dict[str, Any]) -> Any:
    return render_question(template, params)["correct_answer"]


def _is_answer_correct(
    template: QuestionTemplate, correct_answer: Any, selected_answer: int | float | str
) -> bool:
    if template.answer_type == "choice":
        try:
            return int(selected_answer) == int(correct_answer)
        except (TypeError, ValueError):
            return False
    if template.answer_type == "text":
        return str(selected_answer).strip().lower() == str(correct_answer).strip().lower()
    try:
        return abs(float(selected_answer) - float(correct_answer)) < 0.01
    except (TypeError, ValueError):
        return False


def _wrong_quality(time_taken_sec: float, time_limit_sec: int) -> float:
    if time_taken_sec <= 0.5 * time_limit_sec:
        return 2.0
    if time_taken_sec <= time_limit_sec:
        return 1.0
    return 0.0


def _success_quality(time_taken_sec: float, time_limit_sec: int) -> float:
    if time_taken_sec <= 0.5 * time_limit_sec:
        return 5.0
    if time_taken_sec <= time_limit_sec:
        return 4.0
    return 3.0


def _due_datetime(iso_date: str) -> datetime:
    due_date = date.fromisoformat(iso_date)
    return datetime.combine(due_date, dtime.min, tzinfo=timezone.utc)


async def _update_theta(db: AsyncSession, child: ChildAccount, subject_code: str) -> float:
    # Пересчёт по последним 300 ответам (окно) — на больших историях MLE всё
    # равно вырождается, а полный пересчёт на каждый ответ дорогой.
    rows = (
        await db.execute(
            select(
                UserResponseLog.is_correct,
                UserResponseLog.difficulty_b,
                UserResponseLog.discrimination_a,
            )
            .where(
                UserResponseLog.child_id == child.id,
                UserResponseLog.subject_code == subject_code,
            )
            .order_by(UserResponseLog.id.desc())
            .limit(300)
        )
    ).all()
    rows = list(reversed(rows))
    if not rows:
        return float(getattr(child, THETA_ATTR[subject_code]))
    pattern = [1 if r.is_correct else 0 for r in rows]
    b = [float(r.difficulty_b) for r in rows]
    a = [float(r.discrimination_a) for r in rows]
    theta = IRT.estimate_theta(pattern, b, a)
    setattr(child, THETA_ATTR[subject_code], theta)
    return theta


async def _update_streak(child: ChildAccount) -> int:
    """Streak считается по часовому поясу платформы (Asia/Almaty)."""
    from zoneinfo import ZoneInfo

    from app.core.config import get_settings

    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz).date()
    yesterday = today - timedelta(days=1)
    if child.last_active_date is None:
        streak = 1
    elif child.last_active_date == today:
        streak = child.streak_days
    elif child.last_active_date == yesterday:
        streak = child.streak_days + 1
    else:
        streak = 1
    child.streak_days = streak
    child.last_active_date = today
    return streak


async def _handle_error_log_wrong(
    db: AsyncSession,
    child: ChildAccount,
    template: QuestionTemplate,
    params: dict[str, Any],
    time_taken_sec: float,
    subject: Subject,
) -> None:
    """Upsert: один item на (child, template) — без дублей в журнале.

    Каждый неверный ответ немедленно делает запись снова due
    (next_review_at=now), интервал по SM-2 начнёт расти после успеха.
    """
    quality = _wrong_quality(time_taken_sec, subject.per_question_sec)
    now = utc_now()
    existing = await db.scalar(
        select(ErrorLogItem)
        .where(
            ErrorLogItem.child_id == child.id,
            ErrorLogItem.template_id == template.id,
        )
        .order_by(ErrorLogItem.id.desc())
        .limit(1)
    )
    if existing is not None:
        existing.wrong_count += 1
        existing.quality = quality
        schedule = SM2().schedule_review(existing.wrong_count, quality, existing.ef)
        existing.ef = schedule["ef"]
        existing.interval_days = schedule["interval_days"]
        existing.review_number = schedule["review_number"]
        existing.next_review_at = now
        existing.last_reviewed_at = now
        existing.params_used = params
    else:
        schedule = SM2().schedule_review(1, quality, 2.5)
        db.add(
            ErrorLogItem(
                child_id=child.id,
                template_id=template.id,
                micro_skill_id=template.micro_skill_id,
                params_used=params,
                review_number=schedule["review_number"],
                quality=quality,
                ef=schedule["ef"],
                interval_days=schedule["interval_days"],
                next_review_at=now,
                last_reviewed_at=now,
                wrong_count=1,
            )
        )


async def _handle_error_log_success(
    db: AsyncSession,
    child: ChildAccount,
    template: QuestionTemplate,
    time_taken_sec: float,
    subject: Subject,
) -> None:
    quality = _success_quality(time_taken_sec, subject.per_question_sec)
    now = utc_now()
    item = await db.scalar(
        select(ErrorLogItem)
        .where(
            ErrorLogItem.child_id == child.id,
            ErrorLogItem.template_id == template.id,
        )
        .order_by(ErrorLogItem.id.desc())
        .limit(1)
    )
    if item is None:
        return
    # review_number растёт на каждом успешном повторении → SM-2 прогрессия
    # интервалов I_1=1, I_2=3, I_n=I_{n-1}·EF реально достигается.
    schedule = SM2().schedule_review(
        item.wrong_count, quality, item.ef, review_number=item.review_number + 1
    )
    item.ef = schedule["ef"]
    item.interval_days = schedule["interval_days"]
    item.review_number = schedule["review_number"]
    item.quality = quality
    item.next_review_at = _due_datetime(schedule["due_at"])
    item.last_reviewed_at = now
    if quality < 3.0:
        item.wrong_count += 1


async def submit_answer(
    db: AsyncSession,
    redis,
    session_id: str | None,
    child: ChildAccount,
    template_id: int,
    params: dict[str, Any],
    selected_answer: int | float | str,
    time_taken_sec: float,
) -> dict:
    """Validate an answer, update theta/Elo/streak and maintain the error log.

    ``session_id=None`` marks a revision answer coming from the smart error log.
    """
    template = await db.get(QuestionTemplate, template_id)
    if template is None:
        raise ValueError(f"question template {template_id} not found")
    subject = await _get_subject_of_template(db, template)
    subject_code = subject.code

    # Повтор из журнала ошибок приходит с session_id="revision" (или пустым).
    is_revision = session_id is None or session_id in ("", "revision")
    if is_revision:
        # C2: повторение доступно ТОЛЬКО для вопросов из журнала ошибок ребёнка.
        in_log = await db.scalar(
            select(ErrorLogItem.id)
            .where(
                ErrorLogItem.child_id == child.id,
                ErrorLogItem.template_id == template.id,
            )
            .limit(1)
        )
        if in_log is None:
            raise PermissionError(
                "Повторение доступно только для вопросов из вашего журнала ошибок"
            )

    session: dict | None = None
    if not is_revision:
        session = await redis_get_json(redis, f"session:{session_id}")
        if session is None:
            raise ValueError("session not found or expired")
        if int(session.get("child_id", -1)) != child.id:
            raise PermissionError("session belongs to another child")
        # H1: вопрос должен быть выдан в этой сессии, и на него ещё не отвечали.
        if template.id not in session.get("asked", []):
            raise PermissionError("Вопрос не входит в текущую сессию")
        for entry in session.get("answered", []):
            if entry.get("template_id") == template.id and entry.get("params") == params:
                raise PermissionError("На этот вопрос уже дан ответ")

    correct_answer = _correct_answer_for(template, params)
    is_correct = _is_answer_correct(template, correct_answer, selected_answer)

    session_mode = "revision" if is_revision else session["mode"]
    log_entry = UserResponseLog(
        child_id=child.id,
        template_id=template.id,
        micro_skill_id=template.micro_skill_id,
        subject_code=subject_code,
        params_used=params,
        is_correct=is_correct,
        time_taken_sec=time_taken_sec,
        difficulty_b=template.difficulty_b,
        discrimination_a=template.discrimination_a,
        session_id=session_id or "revision",
        mode=session_mode,
    )
    db.add(log_entry)
    theta_after = await _update_theta(db, child, subject_code)
    log_entry.theta_after = theta_after

    score = 1.0 if is_correct else 0.0
    old_elo = child.current_elo
    new_elo = ELO.update_vs_item_difficulty(
        old_elo,
        template.difficulty_b,
        score,
        time_taken_sec,
        child.total_solved,
        t_norm=float(subject.per_question_sec),
    )
    elo_delta = round(new_elo - old_elo, 4)
    streak_bonus: float | None = None
    streak_days = await _update_streak(child)
    if is_correct and streak_days > 0 and streak_days % 7 == 0:
        new_elo = round(new_elo + STREAK_BONUS_ELO, 4)
        elo_delta = round(elo_delta + STREAK_BONUS_ELO, 4)
        streak_bonus = STREAK_BONUS_ELO
    child.current_elo = new_elo
    child.total_solved += 1
    if is_correct:
        child.total_correct += 1
    log_entry.elo_after = new_elo
    log_entry.elo_delta = elo_delta

    if is_correct:
        await _handle_error_log_success(db, child, template, time_taken_sec, subject)
    else:
        await _handle_error_log_wrong(db, child, template, params, time_taken_sec, subject)

    # M4: скользящее среднее времени (EMA 0.8/0.2) — t_speed в readiness живая.
    t_avg_attr = {
        "math": "t_avg_math",
        "quant": "t_avg_quant",
        "nat_sci": "t_avg_nat_sci",
        "lang": "t_avg_lang",
    }
    old_avg = float(getattr(child, t_avg_attr[subject_code]))
    setattr(child, t_avg_attr[subject_code], round(old_avg * 0.8 + time_taken_sec * 0.2, 4))

    consecutive_errors = 0
    if not is_revision:
        async with _with_session_lock(redis, session_id):
            session = await redis_get_json(redis, f"session:{session_id}")
            if session is not None:
                consecutive_errors = int(session.get("consecutive_errors", 0))
                consecutive_errors = 0 if is_correct else consecutive_errors + 1
                session["consecutive_errors"] = consecutive_errors
                session["answers"].append(
                    {
                        "template_id": template.id,
                        "is_correct": is_correct,
                        "time_taken_sec": time_taken_sec,
                        "theta_after": theta_after,
                        "elo_after": new_elo,
                    }
                )
                session.setdefault("answered", []).append(
                    {"template_id": template.id, "params": params}
                )
                await redis_set_json(redis, f"session:{session_id}", session, SESSION_TTL_SECONDS)
                if consecutive_errors == CONSECUTIVE_ERROR_ALERT_AT:
                    asyncio.create_task(send_error_alert(child, consecutive_errors))

    await db.commit()
    await db.refresh(child)

    next_question: dict | None = None
    session_finished = True
    if not is_revision:
        next_question = await get_next_question(db, redis, session_id, child)
        session_finished = next_question is None

    return {
        "session_id": session_id or "revision",
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "theta_after": theta_after,
        "elo_after": new_elo,
        "elo_delta": elo_delta,
        "streak_days": child.streak_days,
        "streak_bonus": streak_bonus,
        "next_question": next_question,
        "session_finished": session_finished,
    }


async def get_session_state(redis, session_id: str) -> dict | None:
    session = await redis_get_json(redis, f"session:{session_id}")
    if session is None:
        return None
    ttl = await redis.ttl(f"session:{session_id}")
    return {
        "session_id": session_id,
        "child_id": session["child_id"],
        "mode": session["mode"],
        "subject_code": session["subject_code"],
        "asked": session["asked"],
        "question_idx": len(session["asked"]),
        "max_questions": session["max_questions"],
        "answers": session["answers"],
        "ttl_remaining_sec": max(0, ttl),
    }
