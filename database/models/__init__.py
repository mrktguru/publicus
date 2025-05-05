from .base import Base
from .group import Group
from .post import Post
from .generated_series import GeneratedSeries
from .generated_post import GeneratedPost
from .generation_template import GenerationTemplate  # Добавляем новый импорт


__all__ = (
    "Base",
    "Group",
    "Post",
    "GeneratedSeries",
    "GeneratedPost",
    "GenerationTemplate",  # Добавляем в __all__
)
