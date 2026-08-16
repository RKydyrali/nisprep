"""Question clone generation: safe arithmetic evaluation and template rendering."""

from __future__ import annotations

import ast
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.math import SmartErrorLogEngine
from app.models import MicroSkill, QuestionTemplate, Topic

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
)

MAX_EXPR_LENGTH = 200
MAX_POW_EXPONENT = 100


def safe_eval(expr: str, params: dict[str, Any]) -> float | int:
    """Evaluate a restricted arithmetic expression over ``params``.

    Only + - * / // % ** and unary +/- on plain numeric constants and parameter
    names are allowed. Calls, attributes, subscripts and dunder tricks raise
    ValueError. Guards: expression length, exponent size (CPU/memory DoS),
    MemoryError/RecursionError during evaluation.
    """
    if not isinstance(expr, str) or not expr.strip():
        raise ValueError("expression must be a non-empty string")
    if len(expr) > MAX_EXPR_LENGTH:
        raise ValueError(f"expression too long (max {MAX_EXPR_LENGTH} chars)")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid expression: {expr}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError(f"unsupported constant in expression: {node.value!r}")
            if not math.isfinite(float(node.value)):
                raise ValueError("non-finite numeric constants are not allowed")
        elif isinstance(node, ast.Name):
            if node.id not in params:
                raise ValueError(f"unknown parameter in expression: {node.id}")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            if (
                isinstance(node.right, ast.Constant)
                and isinstance(node.right.value, (int, float))
                and abs(float(node.right.value)) > MAX_POW_EXPONENT
            ):
                raise ValueError(f"exponent too large (max {MAX_POW_EXPONENT})")
        elif not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"node type not allowed in expression: {type(node).__name__}")

    for name in {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}:
        value = params[name]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"parameter {name!r} must be numeric, got {type(value).__name__}")

    try:
        result = eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, dict(params))
    except (ZeroDivisionError, OverflowError, TypeError, ValueError, MemoryError, RecursionError) as exc:
        raise ValueError(f"expression evaluation failed: {exc}") from exc

    if isinstance(result, bool) or not isinstance(result, (int, float)):
        raise ValueError(f"expression must evaluate to a number, got {result!r}")
    result = float(result)
    if not math.isfinite(result):
        raise ValueError("expression result must be finite")
    if abs(result) > 1e15:
        raise ValueError("expression result is unreasonably large")
    if result.is_integer():
        return int(result)
    return result


def _fmt_param(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _format_text(text: str, params: dict[str, Any]) -> str:
    try:
        return text.format(**{k: _fmt_param(v) for k, v in params.items()})
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError(f"question text references unknown placeholder: {exc}") from exc


def generate_params(schema: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    """Instantiate a param_schema: plain specs via clone_parameters, then
    derived keys ({"derived": "a*k+b"}) computed afterwards with safe_eval."""
    if not schema:
        return {}
    derived: dict[str, str] = {
        key: spec["derived"]
        for key, spec in schema.items()
        if isinstance(spec, dict) and "derived" in spec
    }
    base_schema = {key: spec for key, spec in schema.items() if key not in derived}
    params: dict[str, Any] = (
        SmartErrorLogEngine.clone_parameters(base_schema, seed) if base_schema else {}
    )
    for key, expr in derived.items():
        params[key] = safe_eval(expr, params)
    return params


def render_question(
    template: QuestionTemplate, params: dict[str, Any]
) -> dict[str, Any]:
    """Render a template into {question_text, choices, correct_answer, answer_type}."""
    answer_type = template.answer_type
    question_text = _format_text(template.question_text, params)
    choices: list[str] | None = None
    if template.choices:
        choices = [_format_text(c, params) for c in template.choices]

    if answer_type == "choice":
        if not choices:
            raise ValueError(f"template {template.id}: choice answer requires choices")
        correct_index = safe_eval(template.answer_expr, params) % len(choices)
        correct_answer = int(correct_index)
    elif answer_type == "text":
        correct_answer = template.answer_expr
    else:
        correct_answer = safe_eval(template.answer_expr, params)

    return {
        "question_text": question_text,
        "choices": choices,
        "correct_answer": correct_answer,
        "answer_type": answer_type,
    }


def _micro_skill_dict(skill: MicroSkill) -> dict[str, Any]:
    return {"id": skill.id, "code": skill.code, "name_ru": skill.name_ru, "name_kk": skill.name_kk}


async def clone_question(
    db: AsyncSession, template_id: int, seed: int | None = None
) -> dict[str, Any]:
    """Load a template and produce a fully rendered question clone."""
    template = await db.get(QuestionTemplate, template_id)
    if template is None:
        raise ValueError(f"question template {template_id} not found")
    params = generate_params(template.param_schema, seed)
    rendered = render_question(template, params)
    skill = await db.get(MicroSkill, template.micro_skill_id)
    return {
        "template_id": template.id,
        "params": params,
        "question_text": rendered["question_text"],
        "choices": rendered["choices"],
        "correct_answer": rendered["correct_answer"],
        "answer_type": rendered["answer_type"],
        "difficulty_b": template.difficulty_b,
        "discrimination_a": template.discrimination_a,
        "micro_skill": _micro_skill_dict(skill) if skill else None,
    }
