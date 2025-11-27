from typing import Annotated, List
from fastapi import APIRouter, Depends, status, HTTPException
from models import db_helper, Allergen
from pydantic import BaseModel, Field
from config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter(
    tags=["Allergens"],
    prefix=settings.url.allergens,
)

class AllergenRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class AllergenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Название аллергена не может быть пустым")

class AllergenUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Название аллергена не может быть пустым")

@router.get("", response_model=List[AllergenRead])
async def index(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
):

    stmt = select(Allergen).order_by(Allergen.id)
    allergens = await session.scalars(stmt)
    return allergens.all()

@router.post("", response_model=AllergenRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    allergen_create: AllergenCreate,
):

    existing_allergen = await session.scalar(
        select(Allergen).where(Allergen.name == allergen_create.name)
    )
    if existing_allergen:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allergen with name '{allergen_create.name}' already exists"
        )
    
    allergen = Allergen(name=allergen_create.name)
    session.add(allergen)
    await session.commit()
    return allergen

@router.get("/{id}", response_model=AllergenRead)
async def show(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
):

    allergen = await session.get(Allergen, id)
    if not allergen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Allergen with id {id} not found"
        )
    return allergen

@router.put("/{id}", response_model=AllergenRead)
async def update(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
    allergen_update: AllergenUpdate,
):

    allergen = await session.get(Allergen, id)
    if not allergen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Allergen with id {id} not found"
        )
    
    existing_allergen = await session.scalar(
        select(Allergen).where(
            Allergen.name == allergen_update.name,
            Allergen.id != id
        )
    )
    if existing_allergen:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allergen with name '{allergen_update.name}' already exists"
        )
    
    allergen.name = allergen_update.name
    await session.commit()
    return allergen

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
):

    allergen = await session.get(Allergen, id)
    if not allergen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Allergen with id {id} not found"
        )

    await session.delete(allergen)
    await session.commit()