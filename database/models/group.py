from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class Group(Base):
    __tablename__ = "groups"

    id:        Mapped[int]        = mapped_column(primary_key=True, autoincrement=True)
    chat_id:   Mapped[int]        = mapped_column(BigInteger, unique=True, index=True)
    title:     Mapped[str]        = mapped_column(String, nullable=False)
