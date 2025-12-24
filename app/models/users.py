
from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List
from .base import Base


class User(SQLAlchemyBaseUserTable[int], Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(nullable=True)
    last_name: Mapped[str] = mapped_column(nullable=True)
    recipes: Mapped[List["Recipe"]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan"
    )