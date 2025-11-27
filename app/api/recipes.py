from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from models import db_helper, Recipe, Cuisine, Allergen, Ingredient, RecipeIngredient
from pydantic import BaseModel, Field
from config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc
from sqlalchemy.orm import selectinload, joinedload
from enum import IntEnum
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_filter import FilterDepends
from fastapi_filter.contrib.sqlalchemy import Filter

router = APIRouter(
    tags=["Recipes"],
    prefix=settings.url.recipes,
)

class MeasurementEnum(IntEnum):
    GRAMS = 1
    PIECES = 2
    MILLILITERS = 3

    @property
    def label(self) -> str:
        return {
            MeasurementEnum.GRAMS: "г",
            MeasurementEnum.PIECES: "шт", 
            MeasurementEnum.MILLILITERS: "мл",
        }[self]

class CuisineRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class AllergenRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class IngredientRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class RecipeIngredientRead(BaseModel):
    id: int
    ingredient: IngredientRead
    quantity: int
    measurement: MeasurementEnum

    class Config:
        from_attributes = True

class RecipeIngredientCreate(BaseModel):
    ingredient_id: int
    quantity: int = Field(..., gt=0, description="Количество должно быть больше 0")
    measurement: MeasurementEnum

class RecipeRead(BaseModel):
    id: int
    title: str
    description: str
    cooking_time: int
    difficulty: int
    cuisine: Optional[CuisineRead] = None
    allergens: List[AllergenRead] = []
    recipe_ingredients: List[RecipeIngredientRead] = [] 

    class Config:
        from_attributes = True

class RecipeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Название рецепта не может быть пустым")
    description: str = Field(..., min_length=1, description="Описание не может быть пустым")
    cooking_time: int = Field(..., gt=0, le=1440, description="Время готовки должно быть больше 0 минут и не больше суток")
    difficulty: int = Field(1, ge=1, le=5, description="Сложность от 1 до 5")
    cuisine_id: Optional[int] = None
    allergen_ids: List[int] = Field(default_factory=list)
    recipe_ingredients: List[RecipeIngredientCreate] = Field(default_factory=list)

class RecipeUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Название рецепта не может быть пустым")
    description: str = Field(..., min_length=1, description="Описание не может быть пустым")
    cooking_time: int = Field(..., gt=0, le=1440, description="Время готовки должно быть больше 0 минут и не больше суток")
    difficulty: int = Field(..., ge=1, le=5, description="Сложность от 1 до 5")
    cuisine_id: Optional[int] = None
    allergen_ids: List[int] = Field(default_factory=list)
    recipe_ingredients: List[RecipeIngredientCreate] = Field(default_factory=list)

# ФИЛЬТРЫ КАК В РАБОЧЕМ КОДЕ
class RecipeFilterStandard(Filter):
    title__like: Optional[str] = None
    order_by: Optional[List[str]] = None

    class Constants(Filter.Constants):
        model = Recipe
        ordering_field_name = "order_by"
        search_field_name = "title__like"
        search_model_fields = ["title"]

    def sort(self, stmt):
        """Кастомная сортировка"""
        if not self.order_by:
            return stmt

        order_fields = []
        for field in self.order_by:
            if field.startswith('-'):
                order_fields.append(desc(getattr(Recipe, field[1:])))
            else:
                order_fields.append(asc(getattr(Recipe, field)))

        return stmt.order_by(*order_fields)

class RecipeFilterIngredients(Filter):
    ingredient_id: Optional[str] = None

    class Constants(Filter.Constants):
        model = Recipe

    def filter(self, stmt):
        if self.ingredient_id:
            ids = [int(x.strip()) for x in self.ingredient_id.split(",") if x.strip()]
            stmt = stmt.join(Recipe.recipe_ingredients).filter(
                RecipeIngredient.ingredient_id.in_(ids)
            )
        return stmt

# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
async def get_recipe_with_relations(session: AsyncSession, id: int):
    stmt = (
        select(Recipe)
        .where(Recipe.id == id)
        .options(
            joinedload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients).joinedload(RecipeIngredient.ingredient)
        )
    )
    result = await session.scalar(stmt)
    return result

# НОВЫЙ МАРШРУТ ДЛЯ ФИЛЬТРАЦИИ И ПАГИНАЦИИ
@router.get("", response_model=Page[RecipeRead])
async def get_recipes(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    filter_standard: RecipeFilterStandard = FilterDepends(RecipeFilterStandard),
    filter_ingredients: RecipeFilterIngredients = FilterDepends(RecipeFilterIngredients),
):
    stmt = (
        select(Recipe)
        .options(
            joinedload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients).joinedload(RecipeIngredient.ingredient)
        )
    )

    # Применяем фильтры
    stmt = filter_standard.filter(stmt)
    stmt = filter_standard.sort(stmt)
    stmt = filter_ingredients.filter(stmt)

    result = await paginate(session, stmt)
    return result

# СТАРЫЕ МАРШРУТЫ (немного обновлены для консистентности)
@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    recipe_create: RecipeCreate,
):
    allergens = []
    if recipe_create.allergen_ids:
        stmt = select(Allergen).where(Allergen.id.in_(recipe_create.allergen_ids))
        allergens = (await session.scalars(stmt)).all()
    
    cuisine = None
    if recipe_create.cuisine_id:
        cuisine = await session.get(Cuisine, recipe_create.cuisine_id)
        if not cuisine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cuisine with id {recipe_create.cuisine_id} not found"
            )
    
    recipe = Recipe(
        title=recipe_create.title,
        description=recipe_create.description,
        cooking_time=recipe_create.cooking_time,
        difficulty=recipe_create.difficulty,
        cuisine=cuisine,
        allergens=allergens
    )
    
    for ing_data in recipe_create.recipe_ingredients:
        ingredient = await session.get(Ingredient, ing_data.ingredient_id)
        if not ingredient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingredient with id {ing_data.ingredient_id} not found"
            )
        
        recipe_ingredient = RecipeIngredient(
            ingredient=ingredient,
            quantity=ing_data.quantity,
            measurement=ing_data.measurement.value
        )
        recipe.recipe_ingredients.append(recipe_ingredient)
    
    session.add(recipe)
    await session.commit()
    return await get_recipe_with_relations(session, recipe.id)

@router.get("/{id}", response_model=RecipeRead)
async def get_recipe(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
):
    recipe = await get_recipe_with_relations(session, id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Recipe with id {id} not found"
        )
    return recipe

@router.put("/{id}", response_model=RecipeRead)
async def update_recipe(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    recipe_update: RecipeUpdate,
):
    recipe = await get_recipe_with_relations(session, id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Recipe with id {id} not found"
        )
    
    recipe.title = recipe_update.title
    recipe.description = recipe_update.description
    recipe.cooking_time = recipe_update.cooking_time
    recipe.difficulty = recipe_update.difficulty
    
    if recipe_update.cuisine_id:
        cuisine = await session.get(Cuisine, recipe_update.cuisine_id)
        if not cuisine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cuisine with id {recipe_update.cuisine_id} not found"
            )
        recipe.cuisine = cuisine
    else:
        recipe.cuisine = None
    
    if recipe_update.allergen_ids:
        stmt = select(Allergen).where(Allergen.id.in_(recipe_update.allergen_ids))
        allergens = (await session.scalars(stmt)).all()
        recipe.allergens = allergens
    else:
        recipe.allergens = []
    
    recipe.recipe_ingredients.clear()
    for ing_data in recipe_update.recipe_ingredients:
        ingredient = await session.get(Ingredient, ing_data.ingredient_id)
        if not ingredient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingredient with id {ing_data.ingredient_id} not found"
            )
        
        recipe_ingredient = RecipeIngredient(
            ingredient=ingredient,
            quantity=ing_data.quantity,
            measurement=ing_data.measurement.value
        )
        recipe.recipe_ingredients.append(recipe_ingredient)
    
    await session.commit()
    return await get_recipe_with_relations(session, id)

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
):
    recipe = await session.get(Recipe, id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Recipe with id {id} not found"
        )

    await session.delete(recipe)
    await session.commit()