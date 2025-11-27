from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String
from typing import List
from .base import Base

class Allergen(Base):
    __tablename__ = "allergens"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    recipes: Mapped[List["Recipe"]] = relationship(
        secondary="recipe_allergens",  
        back_populates="allergens"
    )

    def __repr__(self):
        return f"Allergen(id={self.id}, name={self.name})"