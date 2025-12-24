# api/recipes.py
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from models import db_helper, Recipe, Cuisine, Allergen, Ingredient, RecipeIngredient, User
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
from authentication.fastapi_users import fastapi_users

router = APIRouter(
    tags=["Recipes"],
    prefix=settings.url.recipes,
)

# Импортируем зависимости для авторизации
current_active_user = fastapi_users.current_user(active=True)
OptionalCurrentUser = fastapi_users.current_user(active=True, optional=True)

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

class UserReadShort(BaseModel):
    id: int
    first_name: Optional[str]
    last_name: Optional[str]

    class Config:
        from_attributes = True

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

class RecipeIngredientOutput(BaseModel):
    id: int = Field(..., alias="ingredient.id")
    quantity: int
    measurement: MeasurementEnum

    class Config:
        from_attributes = True
        populate_by_name = True


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
    ingredients: List[RecipeIngredientOutput] = Field(..., alias="recipe_ingredients")
    author: UserReadShort

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

class RecipeFilterStandard(Filter):
    title__like: Optional[str] = None
    order_by: Optional[List[str]] = None

    class Constants(Filter.Constants):
        model = Recipe
        ordering_field_name = "order_by"
        search_field_name = "title__like"
        search_model_fields = ["title"]

    def sort(self, stmt):
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

async def get_recipe_with_relations(session: AsyncSession, id: int):
    stmt = (
        select(Recipe)
        .where(Recipe.id == id)
        .options(
            joinedload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients).joinedload(RecipeIngredient.ingredient),
            joinedload(Recipe.author)
        )
    )
    result = await session.scalar(stmt)
    return result

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
            selectinload(Recipe.recipe_ingredients).joinedload(RecipeIngredient.ingredient),
            joinedload(Recipe.author)
        )
    )

    stmt = filter_standard.filter(stmt)
    stmt = filter_standard.sort(stmt)
    stmt = filter_ingredients.filter(stmt)

    result = await paginate(session, stmt)
    return result

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

@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    recipe_create: RecipeCreate,
    user: User = Depends(current_active_user),
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
        allergens=allergens,
        author_id=user.id
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

@router.put("/{id}", response_model=RecipeRead)
async def update_recipe(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    recipe_update: RecipeUpdate,
    user: User = Depends(current_active_user),
):
    recipe = await get_recipe_with_relations(session, id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Recipe with id {id} not found"
        )
    
    # Проверка авторства
    if recipe.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own recipes"
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
    user: User = Depends(current_active_user),
):
    recipe = await session.get(Recipe, id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Recipe with id {id} not found"
        )

    # Проверка авторства
    if recipe.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own recipes"
        )

    await session.delete(recipe)
    await session.commit()