from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String
from typing import List
from .base import Base

class Cuisine(Base):
    __tablename__ = "cuisines"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    recipes: Mapped[List["Recipe"]] = relationship(back_populates="cuisine")

    def __repr__(self):
        return f"Cuisine(id={self.id}, name={self.name})"