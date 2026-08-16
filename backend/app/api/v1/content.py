"""Admin content management: question template CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import get_session
from app.models import MicroSkill, QuestionTemplate, Subject, User
from app.schemas.content import TemplateCreateIn, TemplateOut, TemplateUpdateIn
from app.services.auth_service import get_current_admin
from app.services.clone_generator_service import generate_params, safe_eval

router = APIRouter(prefix="/content", tags=["content"])


def _validate_template_schema(payload: TemplateCreateIn | TemplateUpdateIn) -> None:
    schema = payload.param_schema
    if schema:
        sample: dict = {}
        for key, spec in schema.items():
            if isinstance(spec, dict) and "derived" in spec:
                continue
            if isinstance(spec, dict) and "min" in spec and "max" in spec:
                step = float(spec.get("step", 1))
                if step <= 0:
                    raise HTTPException(status_code=422, detail=f"Параметр {key}: step должен быть > 0")
                if float(spec["min"]) > float(spec["max"]):
                    raise HTTPException(
                        status_code=422, detail=f"Параметр {key}: min не может быть больше max"
                    )
                sample[key] = spec["min"]
            elif isinstance(spec, dict) and "values" in spec:
                if not spec["values"]:
                    raise HTTPException(status_code=422, detail=f"Параметр {key}: пустой список values")
                sample[key] = spec["values"][0]
            else:
                raise HTTPException(
                    status_code=422,
                    detail=f"Параметр {key}: нужен {{min,max,step}}, {{values}} или {{derived}}",
                )
    if payload.answer_type != "text":
        try:
            safe_eval(payload.answer_expr, sample)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"answer_expr не валиден: {exc}"
            ) from exc
    if payload.answer_type == "choice":
        if not payload.choices:
            raise HTTPException(status_code=422, detail="Для answer_type=choice нужны choices")
        try:
            safe_eval(payload.answer_expr, sample)
        except ValueError:
            raise
        if not (0 <= int(safe_eval(payload.answer_expr, sample)) < len(payload.choices)):
            raise HTTPException(
                status_code=422, detail="answer_expr должен давать индекс из choices"
            )


@router.post("/templates", response_model=TemplateOut, status_code=201)
async def create_template(
    payload: TemplateCreateIn,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> TemplateOut:
    subject = await db.scalar(select(Subject).where(Subject.code == payload.subject_code))
    if subject is None:
        raise HTTPException(status_code=422, detail=f"Предмет {payload.subject_code!r} не найден")
    skill = await db.scalar(
        select(MicroSkill)
        .options(selectinload(MicroSkill.topic))
        .where(MicroSkill.id == payload.micro_skill_id)
    )
    if skill is None or skill.topic.subject_id != subject.id:
        raise HTTPException(
            status_code=422, detail="micro_skill_id не принадлежит выбранному предмету"
        )
    _validate_template_schema(payload)
    template = QuestionTemplate(
        subject_id=subject.id,
        micro_skill_id=payload.micro_skill_id,
        title=payload.title,
        question_text=payload.question_text,
        param_schema=payload.param_schema,
        answer_type=payload.answer_type,
        answer_expr=payload.answer_expr,
        choices=payload.choices,
        difficulty_b=payload.difficulty_b,
        discrimination_a=payload.discrimination_a,
        is_demo=payload.is_demo,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return TemplateOut(
        id=template.id,
        subject_id=template.subject_id,
        subject_code=subject.code,
        micro_skill_id=template.micro_skill_id,
        title=template.title,
        question_text=template.question_text,
        param_schema=template.param_schema,
        answer_type=template.answer_type,
        answer_expr=template.answer_expr,
        choices=template.choices,
        difficulty_b=template.difficulty_b,
        discrimination_a=template.discrimination_a,
        is_demo=template.is_demo,
        created_at=template.created_at,
    )


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(
    subject: str | None = Query(default=None),
    micro_skill: int | None = Query(default=None, alias="micro_skill"),
    is_demo: bool | None = Query(default=None),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> list[TemplateOut]:
    stmt = (
        select(QuestionTemplate)
        .options(selectinload(QuestionTemplate.subject))
        .join(Subject, Subject.id == QuestionTemplate.subject_id)
    )
    if subject:
        stmt = stmt.where(Subject.code == subject)
    if micro_skill:
        stmt = stmt.where(QuestionTemplate.micro_skill_id == micro_skill)
    if is_demo is not None:
        stmt = stmt.where(QuestionTemplate.is_demo == is_demo)
    templates = (await db.scalars(stmt.order_by(QuestionTemplate.id))).all()
    return [
        TemplateOut(
            id=t.id,
            subject_id=t.subject_id,
            subject_code=t.subject.code,
            micro_skill_id=t.micro_skill_id,
            title=t.title,
            question_text=t.question_text,
            param_schema=t.param_schema,
            answer_type=t.answer_type,
            answer_expr=t.answer_expr,
            choices=t.choices,
            difficulty_b=t.difficulty_b,
            discrimination_a=t.discrimination_a,
            is_demo=t.is_demo,
            created_at=t.created_at,
        )
        for t in templates
    ]


@router.get("/templates/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: int,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> TemplateOut:
    template = await db.scalar(
        select(QuestionTemplate)
        .options(selectinload(QuestionTemplate.subject))
        .where(QuestionTemplate.id == template_id)
    )
    if template is None:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return TemplateOut(
        id=template.id,
        subject_id=template.subject_id,
        subject_code=template.subject.code,
        micro_skill_id=template.micro_skill_id,
        title=template.title,
        question_text=template.question_text,
        param_schema=template.param_schema,
        answer_type=template.answer_type,
        answer_expr=template.answer_expr,
        choices=template.choices,
        difficulty_b=template.difficulty_b,
        discrimination_a=template.discrimination_a,
        is_demo=template.is_demo,
        created_at=template.created_at,
    )


@router.patch("/templates/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: int,
    payload: TemplateUpdateIn,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> TemplateOut:
    template = await db.scalar(
        select(QuestionTemplate)
        .options(selectinload(QuestionTemplate.subject))
        .where(QuestionTemplate.id == template_id)
    )
    if template is None:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    updates = payload.model_dump(exclude_unset=True)
    if "param_schema" in updates or "answer_expr" in updates or "choices" in updates or "answer_type" in updates:
        _validate_template_schema(
            TemplateCreateIn(
                subject_code=template.subject.code,
                micro_skill_id=updates.get("micro_skill_id", template.micro_skill_id),
                title=updates.get("title", template.title),
                question_text=updates.get("question_text", template.question_text),
                param_schema=updates.get("param_schema", template.param_schema),
                answer_type=updates.get("answer_type", template.answer_type),
                answer_expr=updates.get("answer_expr", template.answer_expr),
                choices=updates.get("choices", template.choices),
                difficulty_b=updates.get("difficulty_b", template.difficulty_b),
                discrimination_a=updates.get("discrimination_a", template.discrimination_a),
            )
        )
    if "micro_skill_id" in updates:
        skill = await db.get(MicroSkill, updates["micro_skill_id"])
        if skill is None or skill.topic.subject_id != template.subject_id:
            raise HTTPException(status_code=422, detail="micro_skill_id не принадлежит предмету")
    for key, value in updates.items():
        setattr(template, key, value)
    await db.commit()
    await db.refresh(template)
    return await get_template(template.id, user=admin, db=db)


@router.delete("/templates/{template_id}", status_code=200)
async def delete_template(
    template_id: int,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    template = await db.get(QuestionTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    # Защита: удаление шаблона с историей ответов уничтожит психометрику детей.
    from app.models import ErrorLogItem, UserResponseLog

    log_count = await db.scalar(
        select(func.count(UserResponseLog.id)).where(UserResponseLog.template_id == template_id)
    )
    error_count = await db.scalar(
        select(func.count(ErrorLogItem.id)).where(ErrorLogItem.template_id == template_id)
    )
    if log_count or error_count:
        raise HTTPException(
            status_code=409,
            detail="Шаблон используется в истории ответов учеников. Отредактируйте его вместо удаления.",
        )
    await db.delete(template)
    await db.commit()
    return {"ok": True}
