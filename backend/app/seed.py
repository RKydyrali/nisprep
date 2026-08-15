"""Idempotent database seeder: subjects, topics, micro-skills, demo templates, admin.

Run with: python -m app.seed
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import get_session_factory, init_db
from app.models import MicroSkill, QuestionTemplate, Subject, Topic, User
from app.services.auth_service import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


SUBJECTS = [
    {"code": "math", "name_ru": "Математика", "name_kk": "Математика",
     "questions_count": 40, "time_limit_sec": 3600, "per_question_sec": 90},
    {"code": "quant", "name_ru": "Количественные характеристики", "name_kk": "Сандық сипаттамалар",
     "questions_count": 60, "time_limit_sec": 1800, "per_question_sec": 30},
    {"code": "nat_sci", "name_ru": "Естествознание", "name_kk": "Жаратылыстану",
     "questions_count": 20, "time_limit_sec": 1800, "per_question_sec": 90},
    {"code": "lang", "name_ru": "Язык", "name_kk": "Тіл",
     "questions_count": 60, "time_limit_sec": 7200, "per_question_sec": 120},
]

TOPICS = [
    {"subject": "math", "code": "algebra", "name_ru": "Алгебра", "name_kk": "Алгебра"},
    {"subject": "math", "code": "geometry", "name_ru": "Геометрия", "name_kk": "Геометрия"},
    {"subject": "math", "code": "arithmetic", "name_ru": "Арифметика", "name_kk": "Арифметика"},
    {"subject": "quant", "code": "speed", "name_ru": "Скорость и время", "name_kk": "Жылдамдық және уақыт"},
    {"subject": "quant", "code": "percent", "name_ru": "Проценты", "name_kk": "Пайыздар"},
    {"subject": "nat_sci", "code": "physics", "name_ru": "Физика", "name_kk": "Физика"},
    {"subject": "nat_sci", "code": "chemistry", "name_ru": "Химия", "name_kk": "Химия"},
    {"subject": "lang", "code": "reading", "name_ru": "Чтение и понимание", "name_kk": "Оқу және түсіну"},
    {"subject": "lang", "code": "grammar", "name_ru": "Грамматика", "name_kk": "Грамматика"},
]

MICRO_SKILLS = [
    {"topic": "algebra", "code": "linear_eq", "name_ru": "Линейные уравнения", "name_kk": "Сызықтық теңдеулер", "b": -0.5, "a": 1.0},
    {"topic": "algebra", "code": "fractions", "name_ru": "Дробные выражения", "name_kk": "Бөлшек өрнектер", "b": 0.8, "a": 1.1},
    {"topic": "algebra", "code": "powers", "name_ru": "Степени", "name_kk": "Дәрежелер", "b": 1.5, "a": 1.0},
    {"topic": "geometry", "code": "perimeter", "name_ru": "Периметр", "name_kk": "Периметр", "b": -1.0, "a": 0.9},
    {"topic": "geometry", "code": "area", "name_ru": "Площадь", "name_kk": "Аудан", "b": 0.0, "a": 1.0},
    {"topic": "geometry", "code": "volume", "name_ru": "Объём", "name_kk": "Көлем", "b": 1.0, "a": 1.1},
    {"topic": "arithmetic", "code": "percent", "name_ru": "Проценты", "name_kk": "Пайыздар", "b": -0.3, "a": 0.9},
    {"topic": "arithmetic", "code": "order_ops", "name_ru": "Порядок операций", "name_kk": "Амалдар реті", "b": 0.5, "a": 1.0},
    {"topic": "speed", "code": "speed_time_dist", "name_ru": "Скорость, время, расстояние", "name_kk": "Жылдамдық, уақыт, қашықтық", "b": 0.0, "a": 1.0},
    {"topic": "speed", "code": "avg_speed", "name_ru": "Средняя скорость", "name_kk": "Орташа жылдамдық", "b": 0.7, "a": 1.1},
    {"topic": "percent", "code": "percent_of", "name_ru": "Процент от числа", "name_kk": "Санның пайызы", "b": -0.5, "a": 0.9},
    {"topic": "percent", "code": "percent_change", "name_ru": "Изменение в процентах", "name_kk": "Пайыздық өзгеріс", "b": 1.0, "a": 1.0},
    {"topic": "physics", "code": "density", "name_ru": "Плотность", "name_kk": "Тығыздық", "b": 0.0, "a": 1.1},
    {"topic": "physics", "code": "motion", "name_ru": "Механическое движение", "name_kk": "Механикалық қозғалыс", "b": 0.3, "a": 1.0},
    {"topic": "chemistry", "code": "matter", "name_ru": "Строение вещества", "name_kk": "Зат құрылысы", "b": -0.2, "a": 0.9},
    {"topic": "chemistry", "code": "reactions", "name_ru": "Химические реакции", "name_kk": "Химиялық реакциялар", "b": 0.9, "a": 1.0},
    {"topic": "reading", "code": "text_comprehension", "name_ru": "Понимание текста", "name_kk": "Мәтінді түсіну", "b": -0.4, "a": 0.8},
    {"topic": "reading", "code": "text_reasoning", "name_ru": "Текстовые рассуждения", "name_kk": "Мәтіндік ой қорытынды", "b": 0.6, "a": 0.9},
    {"topic": "grammar", "code": "word_formation", "name_ru": "Словообразование", "name_kk": "Сөзжасам", "b": 0.1, "a": 0.9},
    {"topic": "grammar", "code": "syntax", "name_ru": "Синтаксис", "name_kk": "Синтаксис", "b": 1.1, "a": 1.0},
]

LANG_TEXT = (
    "Вода на Земле непрерывно совершает круговорот. Солнечное излучение нагревает "
    "поверхность океанов и рек, вызывая испарение. Пары воды поднимаются в атмосферу, "
    "где при охлаждении образуются облака. Затем влага выпадает в виде осадков, "
    "пополняя запасы воды в природе."
)

DEMO_TEMPLATES = [
    {
        "subject": "math", "skill": "linear_eq", "title": "Линейное уравнение",
        "question_text": "Решите уравнение: {a}x + {b} = {rhs}. Чему равен x?",
        "param_schema": {
            "a": {"min": 2, "max": 9, "step": 1},
            "b": {"min": 1, "max": 20, "step": 1},
            "k": {"min": 2, "max": 12, "step": 1},
            "rhs": {"derived": "a*k + b"},
        },
        "answer_type": "integer", "answer_expr": "k",
        "b": -0.5, "a": 1.0,
    },
    {
        "subject": "math", "skill": "percent", "title": "Процент от числа",
        "question_text": "{p}% от числа {n} равно?",
        "param_schema": {
            "p": {"min": 1, "max": 100, "step": 1},
            "n": {"min": 10, "max": 500, "step": 1},
        },
        "answer_type": "float", "answer_expr": "p*n/100",
        "b": -0.3, "a": 0.9,
    },
    {
        "subject": "quant", "skill": "speed_time_dist", "title": "Спринт: скорость",
        "question_text": "Спринт: {d} км за {t} минут. Чему равна скорость (км/ч)?",
        "param_schema": {
            "d": {"min": 2, "max": 50, "step": 1},
            "t": {"min": 5, "max": 120, "step": 1},
        },
        "answer_type": "float", "answer_expr": "d*60/t",
        "b": 0.0, "a": 1.0,
    },
    {
        "subject": "nat_sci", "skill": "density", "title": "Плотность",
        "question_text": "Масса тела {m} кг, объём {v} м³. Чему равна плотность (кг/м³)?",
        "param_schema": {
            "m": {"min": 5, "max": 200, "step": 1},
            "v": {"min": 1, "max": 50, "step": 1},
        },
        "answer_type": "float", "answer_expr": "m/v",
        "b": 0.0, "a": 1.1,
    },
    {
        "subject": "lang", "skill": "text_comprehension", "title": "Понимание текста",
        "question_text": LANG_TEXT + "\n\nЧто является главной движущей силой круговорота воды?",
        "param_schema": {},
        "answer_type": "choice",
        "answer_expr": "1",
        "choices": [
            "A) Гравитация Луны",
            "B) Солнечная энергия",
            "C) Ветер",
            "D) Землетрясения",
        ],
        "b": -0.4, "a": 0.8,
    },
]


async def seed_database(db: AsyncSession) -> dict:
    summary: dict = {"subjects": 0, "topics": 0, "micro_skills": 0, "templates": 0, "admin": False}

    existing_subjects = {s.code: s for s in (await db.scalars(select(Subject))).all()}
    for spec in SUBJECTS:
        subject = existing_subjects.get(spec["code"])
        if subject is None:
            subject = Subject(**spec)
            db.add(subject)
            await db.flush()
            summary["subjects"] += 1
        else:
            for key, value in spec.items():
                setattr(subject, key, value)
        existing_subjects[spec["code"]] = subject
    await db.commit()

    existing_topics = {
        (t.subject_id, t.code): t
        for t in (await db.scalars(select(Topic))).all()
    }
    for spec in TOPICS:
        subject = existing_subjects[spec["subject"]]
        key = (subject.id, spec["code"])
        topic = existing_topics.get(key)
        if topic is None:
            topic = Topic(subject_id=subject.id, code=spec["code"], name_ru=spec["name_ru"], name_kk=spec["name_kk"])
            db.add(topic)
            await db.flush()
            summary["topics"] += 1
        else:
            topic.name_ru = spec["name_ru"]
            topic.name_kk = spec["name_kk"]
        existing_topics[key] = topic
    await db.commit()

    existing_skills = {
        (s.topic_id, s.code): s
        for s in (await db.scalars(select(MicroSkill))).all()
    }
    for spec in MICRO_SKILLS:
        topic = next(t for t in existing_topics.values() if t.code == spec["topic"])
        key = (topic.id, spec["code"])
        skill = existing_skills.get(key)
        if skill is None:
            skill = MicroSkill(
                topic_id=topic.id, code=spec["code"], name_ru=spec["name_ru"],
                name_kk=spec["name_kk"], difficulty_b=spec["b"], discrimination_a=spec["a"],
            )
            db.add(skill)
            await db.flush()
            summary["micro_skills"] += 1
        else:
            skill.name_ru = spec["name_ru"]
            skill.name_kk = spec["name_kk"]
            skill.difficulty_b = spec["b"]
            skill.discrimination_a = spec["a"]
        existing_skills[key] = skill
    await db.commit()

    skills_by_code = {s.code: s for s in existing_skills.values()}
    for spec in DEMO_TEMPLATES:
        skill = skills_by_code[spec["skill"]]
        subject = existing_subjects[spec["subject"]]
        exists = await db.scalar(
            select(QuestionTemplate).where(
                QuestionTemplate.subject_id == subject.id,
                QuestionTemplate.title == spec["title"],
            )
        )
        if exists is None:
            db.add(
                QuestionTemplate(
                    subject_id=subject.id,
                    micro_skill_id=skill.id,
                    title=spec["title"],
                    question_text=spec["question_text"],
                    param_schema=spec["param_schema"],
                    answer_type=spec["answer_type"],
                    answer_expr=spec["answer_expr"],
                    choices=spec.get("choices"),
                    difficulty_b=spec["b"],
                    discrimination_a=spec["a"],
                    is_demo=True,
                    created_at=utc_now(),
                )
            )
            summary["templates"] += 1
    await db.commit()

    if settings.admin_email and settings.admin_password:
        admin = await db.scalar(select(User).where(User.email == settings.admin_email))
        if admin is None:
            db.add(
                User(
                    role="ADMIN",
                    email=settings.admin_email,
                    hashed_password=hash_password(settings.admin_password),
                    full_name="Administrator",
                )
            )
            summary["admin"] = True
            await db.commit()
        else:
            summary["admin"] = True

    return summary


async def main() -> None:
    await init_db()
    async with get_session_factory()() as db:
        summary = await seed_database(db)
    logger.info("Seed complete: %s", summary)


if __name__ == "__main__":
    asyncio.run(main())
