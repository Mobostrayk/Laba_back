from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, ForeignKey, Table, Column
from typing import List, Optional
from .base import Base

recipe_allergen_association = Table(
    "recipe_allergens",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id"), primary_key=True),
    Column("allergen_id", ForeignKey("allergens.id"), primary_key=True),
)

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    measurement: Mapped[int] = mapped_column(Integer) 
    recipe: Mapped["Recipe"] = relationship(back_populates="recipe_ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_ingredients")

    def __repr__(self):
        return f"RecipeIngredient(id={self.id}, quantity={self.quantity})"

class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    cooking_time: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    cuisine_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cuisines.id"), 
        nullable=True
    )

    # Связи
    cuisine: Mapped[Optional["Cuisine"]] = relationship(back_populates="recipes")
    allergens: Mapped[List["Allergen"]] = relationship(
        secondary=recipe_allergen_association,
        back_populates="recipes"
    )
    recipe_ingredients: Mapped[List["RecipeIngredient"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"Recipe(id={self.id}, title={self.title})"