#database/models/base.py

from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    """
    Общий базовый класс для всех ORM-моделей проекта.
    Только наследуем — никаких столбцов здесь не задаётся.
    """
    pass
