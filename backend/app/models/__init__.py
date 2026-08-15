"""ORM models: single import point for all entities."""

from app.models.entities import (
    Base,
    ChildAccount,
    ErrorLogItem,
    MicroSkill,
    QuestionTemplate,
    Subject,
    Subscription,
    Topic,
    User,
    UserResponseLog,
)

MODEL_NAMES: list[str] = [
    "User",
    "ChildAccount",
    "Subject",
    "Topic",
    "MicroSkill",
    "QuestionTemplate",
    "UserResponseLog",
    "ErrorLogItem",
    "Subscription",
]

__all__ = MODEL_NAMES + ["Base"]
