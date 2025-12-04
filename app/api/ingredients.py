from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, status, HTTPException, Query
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

class RecipeBasic(BaseModel):
    id: int
    title: str
    description: str
    cooking_time: int
    difficulty: int

    class Config:
        from_attributes = True

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


@router.get("/{id}/recipes")
async def get_recipes_by_ingredient(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    include: Optional[str] = Query(None),
    select_var: Optional[str] = Query(None, alias="select"),
):
    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient with id {id} not found"
        )

    # Базовый запрос
    stmt = (
        select(Recipe)
        .join(Recipe.recipe_ingredients)
        .where(RecipeIngredient.ingredient_id == id)
        .order_by(Recipe.id)
    )

    include_list = []
    # Обработка параметра include
    if include:
        include_list = [item.strip() for item in include.split(",")]
        
        # Проверяем корректность параметров include
        for item in include_list:
            if item not in ["cuisine", "ingredients", "allergens"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Invalid value for include: {item}. Allowed values: cuisine, ingredients, allergens"
                )

        include_options = []
        if "cuisine" in include_list:
            include_options.append(joinedload(Recipe.cuisine))
        if "ingredients" in include_list:
            include_options.append(
                selectinload(Recipe.recipe_ingredients).joinedload(RecipeIngredient.ingredient)
            )
        if "allergens" in include_list:
            include_options.append(selectinload(Recipe.allergens))

        if include_options:
            stmt = stmt.options(*include_options)

    # Допустимые поля для select
    ALLOWED_FIELDS = {"id", "title", "difficulty", "description", "cooking_time"}
    
    requested_fields = ALLOWED_FIELDS  # По умолчанию все поля
    if select_var:
        requested_fields = {field.strip() for field in select_var.split(",")}
        # Проверяем, что запрошенные поля допустимы
        invalid_fields = requested_fields - ALLOWED_FIELDS
        if invalid_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid fields: {', '.join(invalid_fields)}. Allowed fields: {', '.join(ALLOWED_FIELDS)}"
            )

    # Выполняем запрос
    results = await session.scalars(stmt)
    recipes = results.unique().all()

    if not recipes:
        return []

    # Фильтрация полей в ответе
    if select_var:
        # Создаём словари с только запрошенными полями
        filtered_recipes = []
        for recipe in recipes:
            recipe_dict = {}
            # Добавляем только запрошенные поля
            for field in requested_fields:
                if field == "id":
                    recipe_dict["id"] = recipe.id
                elif field == "title":
                    recipe_dict["title"] = recipe.title
                elif field == "description":
                    recipe_dict["description"] = recipe.description
                elif field == "cooking_time":
                    recipe_dict["cooking_time"] = recipe.cooking_time
                elif field == "difficulty":
                    recipe_dict["difficulty"] = recipe.difficulty
            
            # Добавляем связанные данные, если они запрошены через include
            if include_list:
                if "cuisine" in include_list and recipe.cuisine:
                    recipe_dict["cuisine"] = {
                        "id": recipe.cuisine.id,
                        "name": recipe.cuisine.name
                    }
                if "ingredients" in include_list and recipe.recipe_ingredients:
                    recipe_dict["recipe_ingredients"] = [
                        {
                            "id": ri.id,
                            "ingredient": {
                                "id": ri.ingredient.id,
                                "name": ri.ingredient.name
                            },
                            "quantity": ri.quantity,
                            "measurement": ri.measurement
                        }
                        for ri in recipe.recipe_ingredients
                    ]
                if "allergens" in include_list and recipe.allergens:
                    recipe_dict["allergens"] = [
                        {"id": a.id, "name": a.name} for a in recipe.allergens
                    ]
                    
            filtered_recipes.append(recipe_dict)
        return filtered_recipes
    
    # Если select_var не указан, но есть include
    if include_list:
        result = []
        for recipe in recipes:
            data = {
                "id": recipe.id,
                "title": recipe.title,
                "description": recipe.description,
                "cooking_time": recipe.cooking_time,
                "difficulty": recipe.difficulty
            }
            
            if "cuisine" in include_list and recipe.cuisine:
                data["cuisine"] = {
                    "id": recipe.cuisine.id,
                    "name": recipe.cuisine.name
                }
                
            if "allergens" in include_list and recipe.allergens:
                data["allergens"] = [
                    {"id": a.id, "name": a.name} for a in recipe.allergens
                ]
                
            if "ingredients" in include_list and recipe.recipe_ingredients:
                data["recipe_ingredients"] = [
                    {
                        "id": ri.id,
                        "ingredient": {
                            "id": ri.ingredient.id,
                            "name": ri.ingredient.name
                        },
                        "quantity": ri.quantity,
                        "measurement": ri.measurement
                    }
                    for ri in recipe.recipe_ingredients
                ]
                
            result.append(data)
        return result
    
    # Если не указаны ни select, ни include, возвращаем базовые данные
    return [
        {
            "id": recipe.id,
            "title": recipe.title,
            "description": recipe.description,
            "cooking_time": recipe.cooking_time,
            "difficulty": recipe.difficulty
        }
        for recipe in recipes
    ]