from typing import Annotated, List
from fastapi import APIRouter, Depends, status, HTTPException
from models import db_helper, Ingredient, Recipe, Cuisine, Allergen, RecipeIngredient
from pydantic import BaseModel, Field
from config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload

router = APIRouter(
    tags=["Ingredients"],
    prefix=settings.url.ingredients,
)

class IngredientRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class IngredientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Название ингредиента не может быть пустым")

class IngredientUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Название ингредиента не может быть пустым")

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
    measurement: int

    class Config:
        from_attributes = True

class RecipeRead(BaseModel):
    id: int
    title: str
    description: str
    cooking_time: int
    difficulty: int
    cuisine: CuisineRead | None = None
    allergens: List[AllergenRead] = []
    recipe_ingredients: List[RecipeIngredientRead] = []

    class Config:
        from_attributes = True

# CRUD операции для Ingredient
@router.get("", response_model=List[IngredientRead])
async def index(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
):
    stmt = select(Ingredient).order_by(Ingredient.id)
    ingredients = await session.scalars(stmt)
    return ingredients.all()

@router.post("", response_model=IngredientRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    ingredient_create: IngredientCreate,
):

    existing_ingredient = await session.scalar(
        select(Ingredient).where(Ingredient.name == ingredient_create.name)
    )
    if existing_ingredient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ingredient with name '{ingredient_create.name}' already exists"
        )
    
    ingredient = Ingredient(name=ingredient_create.name)
    session.add(ingredient)
    await session.commit()
    return ingredient

@router.get("/{id}", response_model=IngredientRead)
async def show(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
):

    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Ingredient with id {id} not found"
        )
    return ingredient

@router.put("/{id}", response_model=IngredientRead)
async def update(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
    ingredient_update: IngredientUpdate,
):

    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Ingredient with id {id} not found"
        )

    existing_ingredient = await session.scalar(
        select(Ingredient).where(
            Ingredient.name == ingredient_update.name,
            Ingredient.id != id
        )
    )
    if existing_ingredient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ingredient with name '{ingredient_update.name}' already exists"
        )
    
    ingredient.name = ingredient_update.name
    await session.commit()
    return ingredient

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
):

    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Ingredient with id {id} not found"
        )

    await session.delete(ingredient)
    await session.commit()

# Все рецепты по id
@router.get("/{id}/recipes", response_model=List[RecipeRead])
async def get_recipes_by_ingredient(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
):
    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient with id {id} not found"
        )

    stmt = (
        select(Recipe)
        .join(Recipe.recipe_ingredients)
        .where(RecipeIngredient.ingredient_id == id)
        .options(
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients).joinedload(RecipeIngredient.ingredient),
            joinedload(Recipe.cuisine)
        )
        .order_by(Recipe.id)
    )
    
    recipes = await session.scalars(stmt)
    return recipes.all()