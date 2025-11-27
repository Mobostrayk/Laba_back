from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String
from typing import List
from .base import Base

class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    recipe_ingredients: Mapped[List["RecipeIngredient"]] = relationship(
        back_populates="ingredient"
    )

    def __repr__(self):
        return f"Ingredient(id={self.id}, name={self.name})"