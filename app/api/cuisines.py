from typing import Annotated, List
from fastapi import APIRouter, Depends, status, HTTPException
from models import db_helper, Cuisine
from pydantic import BaseModel, Field
from config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter(
    tags=["Cuisines"],
    prefix=settings.url.cuisines, 
)

class CuisineRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class CuisineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Название кухни не может быть пустым")

class CuisineUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Название кухни не может быть пустым")

@router.get("", response_model=List[CuisineRead])
async def index(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
):

    stmt = select(Cuisine).order_by(Cuisine.id)
    cuisines = await session.scalars(stmt)
    return cuisines.all()

@router.post("", response_model=CuisineRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    cuisine_create: CuisineCreate,
):

    existing_cuisine = await session.scalar(
        select(Cuisine).where(Cuisine.name == cuisine_create.name)
    )
    if existing_cuisine:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cuisine with name '{cuisine_create.name}' already exists"
        )
    
    cuisine = Cuisine(name=cuisine_create.name)
    session.add(cuisine)
    await session.commit()
    return cuisine

@router.get("/{id}", response_model=CuisineRead)
async def show(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
):

    cuisine = await session.get(Cuisine, id)
    if not cuisine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cuisine with id {id} not found"
        )
    return cuisine

@router.put("/{id}", response_model=CuisineRead)
async def update(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
    cuisine_update: CuisineUpdate,
):

    cuisine = await session.get(Cuisine, id)
    if not cuisine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cuisine with id {id} not found"
        )
    
    existing_cuisine = await session.scalar(
        select(Cuisine).where(
            Cuisine.name == cuisine_update.name,
            Cuisine.id != id
        )
    )
    if existing_cuisine:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cuisine with name '{cuisine_update.name}' already exists"
        )
    
    cuisine.name = cuisine_update.name
    await session.commit()
    return cuisine

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
):

    cuisine = await session.get(Cuisine, id)
    if not cuisine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Cuisine with id {id} not found"
        )

    await session.delete(cuisine)
    await session.commit()