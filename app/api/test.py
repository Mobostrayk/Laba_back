from typing import List, Optional, Union
from fastapi import APIRouter, Query, Path, Body, Form, HTTPException, status, File, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, EmailStr
from config import settings
import os

router = APIRouter(
    tags=["Test"],
    prefix=settings.url.test,
)


@router.get("")
def index():
    return {"message": "Hello, World!"}


UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

#Pydantic 
class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: EmailStr

class ItemWithUser(BaseModel):
    item: Item
    user: User

class LoginForm(BaseModel):
    username: str
    password: str

# 1. Body 
@router.post("/body/items/")
async def create_item(item: Item):
    return item

# 2. Query Parameters and String Validations
@router.get("/query/items/")
async def read_items(
    q: Optional[str] = Query(
        None,
        alias="item-query",
        title="Query string",
        description="Query string for the items to search in the database that have a good match",
        min_length=3,
        max_length=50,
    ),
    skip: int = 0,
    limit: int = 100
):
    results = {"items": [{"name": "Foo"}, {"name": "Bar"}]}
    if q:
        results.update({"q": q})
    return results

# 3. Path Parameters and Numeric Validations
@router.get("/path/items/{item_id}")
async def read_item(
    item_id: int = Path(..., title="The ID of the item", gt=0, le=1000),
    q: Optional[str] = None
):
    return {"item_id": item_id, "q": q}

# 4. Query Parameter Models
class FilterParams(BaseModel):
    name: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None

@router.get("/query-model/items/")
async def filter_items(filters: FilterParams = Query(...)):
    return {
        "filters": filters,
        "items": [
            {"name": "Item1", "price": 10.0},
            {"name": "Item2", "price": 20.0}
        ]
    }

# 5. Nested Models
@router.post("/nested/items-with-user/")
async def create_item_with_user(item_with_user: ItemWithUser):
    return item_with_user


# 6. Request Forms
@router.post("/form/login/")
async def login_form(
    username: str = Form(...),
    password: str = Form(...)
):
    return {"username": username, "password": "****"}

# 7. Request Form Models
@router.post("/form-model/login/")
async def login_form_model(form_data: LoginForm = Form(...)):
    return {
        "username": form_data.username,
        "password": "****",
        "message": "Login successful"
    }

# 8. format
@router.get("/format")
async def format_example(format: Optional[str] = Query(None)):
    if format == "html":
        return HTMLResponse("<h1>HTML Response</h1>")
    elif format == "json":       
        return {"message": "JSON Response"}
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Неподдерживаемый формат. Используйте 'html' или 'json'"
    )


# 9. upload image
@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    allowed_formats = [".png", ".jpg", ".jpeg", ".webp"]
    file_ext = os.path.splitext(file.filename.lower())[1]
    
    if file_ext not in allowed_formats:
        raise HTTPException(
            status_code=400, 
            detail="Only PNG, JPG, WEBP formats are allowed"
        )

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    image_url = f"/static/uploads/{file.filename}"
    
    return {
        "message": "File uploaded successfully",
        "filename": file.filename,
        "url": image_url
    }