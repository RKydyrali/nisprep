"""Analytics: grant-readiness, weak micro-skills, gap graph, theta history, due reviews."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.math import ReadinessPredictor
from app.db.base import redis_get_json
from app.models import (
    ChildAccount,
    ErrorLogItem,
    MicroSkill,
    Topic,
    UserResponseLog,
)
from app.services.clone_generator_service import clone_question

RD = ReadinessPredictor

T_NORM: dict[str, float] = {"math": 90.0, "quant": 30.0, "nat_sci": 90.0, "lang": 120.0}

THETA_ATTR: dict[str, str] = {
    "math": "theta_math",
    "quant": "theta_quant",
    "nat_sci": "theta_nat_sci",
    "lang": "theta_lang",
}

T_AVG_ATTR: dict[str, str] = {
    "math": "t_avg_math",
    "quant": "t_avg_quant",
    "nat_sci": "t_avg_nat_sci",
    "lang": "t_avg_lang",
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _compute_psi(child: ChildAccount) -> tuple[float, float, dict[str, float]]:
    theta = {code: float(getattr(child, THETA_ATTR[code])) for code in THETA_ATTR}
    t_speeds = [
        _clamp((t_norm - float(getattr(child, T_AVG_ATTR[code]))) / t_norm)
        for code, t_norm in T_NORM.items()
    ]
    t_speed = sum(t_speeds) / len(t_speeds) if t_speeds else 0.0
    t_avg_scaled = 90.0 * (1.0 - t_speed)
    psi = RD.readiness_score(
        theta["math"], theta["quant"], theta["nat_sci"], theta["lang"], t_avg=t_avg_scaled
    )
    return psi, t_speed, theta


async def _weak_skills(db: AsyncSession, child: ChildAccount) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(
                MicroSkill,
                func.count(UserResponseLog.id).label("cnt"),
                func.avg(UserResponseLog.is_correct.cast(Integer)).label("acc"),
                func.max(UserResponseLog.created_at).label("last_at"),
            )
            .join(UserResponseLog, UserResponseLog.micro_skill_id == MicroSkill.id)
            .where(UserResponseLog.child_id == child.id)
            .group_by(MicroSkill.id)
            .having(func.avg(UserResponseLog.is_correct.cast(Integer)) < 0.6)
            .order_by(func.avg(UserResponseLog.is_correct.cast(Integer)).asc())
        )
    ).all()
    result: list[dict[str, Any]] = []
    for skill, cnt, acc, last_at in rows:
        if cnt >= 3:
            result.append(
                {
                    "micro_skill_id": skill.id,
                    "name_ru": skill.name_ru,
                    "name_kk": skill.name_kk,
                    "code": skill.code,
                    "accuracy": round(float(acc), 4),
                    "count": int(cnt),
                    "last_practiced_at": last_at,
                }
            )
        if len(result) >= 5:
            break
    return result


async def _gap_graph(db: AsyncSession, child: ChildAccount) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(
                MicroSkill,
                Topic,
                func.count(UserResponseLog.id).label("cnt"),
                func.avg(UserResponseLog.is_correct.cast(Integer)).label("acc"),
            )
            .join(Topic, Topic.id == MicroSkill.topic_id)
            .join(UserResponseLog, UserResponseLog.micro_skill_id == MicroSkill.id)
            .where(UserResponseLog.child_id == child.id)
            .group_by(MicroSkill.id, Topic.id)
        )
    ).all()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for skill, topic, cnt, acc in rows:
        accuracy = round(float(acc), 4)
        nodes.append(
            {
                "id": skill.id,
                "name_ru": skill.name_ru,
                "name_kk": skill.name_kk,
                "accuracy": accuracy,
                "weight": int(cnt),
            }
        )
        edges.append(
            {"from_id": topic.id, "to_id": skill.id, "value": accuracy}
        )
    return {"nodes": nodes, "edges": edges}


async def _theta_history(db: AsyncSession, child: ChildAccount) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(
                func.date(UserResponseLog.created_at).label("day"),
                UserResponseLog.subject_code,
                UserResponseLog.theta_after,
            )
            .where(
                UserResponseLog.child_id == child.id,
                UserResponseLog.theta_after.is_not(None),
            )
            .order_by(UserResponseLog.created_at.asc())
        )
    ).all()
    last_per_day: dict[tuple[str, str], float] = {}
    for day, subject_code, theta_after in rows:
        if day is not None and theta_after is not None:
            last_per_day[(str(day), subject_code)] = float(theta_after)
    dates = sorted({day for day, _ in last_per_day})
    series = {code: [last_per_day.get((day, code)) for day in dates] for code in ("math", "quant", "nat_sci", "lang")}
    return {"dates": dates, "series": series}


async def get_readiness(db: AsyncSession, child: ChildAccount) -> dict[str, Any]:
    psi, t_speed, theta = _compute_psi(child)
    p_grant = RD.grant_probability(psi)
    weak_skills = await _weak_skills(db, child)
    graph = await _gap_graph(db, child)
    history = await _theta_history(db, child)
    return {
        "psi": round(psi, 4),
        "p_grant": round(p_grant, 4),
        "band": RD.interpret_band(psi),
        "theta": theta,
        "t_speed": round(t_speed, 4),
        "weak_skills": weak_skills,
        "graph": graph,
        "history": history,
    }


async def get_due_error_log(
    db: AsyncSession, redis, child: ChildAccount, now: datetime | None = None
) -> dict[str, Any]:
    """Due error-log items with freshly cloned questions (mode 'revision')."""
    now = now or datetime.now(timezone.utc)
    items = (
        await db.scalars(
            select(ErrorLogItem)
            .where(
                ErrorLogItem.child_id == child.id,
                ErrorLogItem.next_review_at <= now,
            )
            .order_by(ErrorLogItem.next_review_at.asc())
        )
    ).all()
    result: list[dict[str, Any]] = []
    for item in items:
        try:
            question = await clone_question(db, item.template_id)
        except ValueError:
            continue
        result.append(
            {
                "item_id": item.id,
                "review_number": item.review_number,
                "ef": item.ef,
                "interval_days": item.interval_days,
                "next_review_at": item.next_review_at,
                "wrong_count": item.wrong_count,
                "question": question,
            }
        )
    return {"items": result}
