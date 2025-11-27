import uvicorn
from fastapi import FastAPI
from config import settings
from contextlib import asynccontextmanager
import os
from fastapi.staticfiles import StaticFiles
from models import db_helper, Base
from api import router  


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with db_helper.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    os.makedirs("static/uploads", exist_ok=True)
    yield
    await db_helper.dispose()

main_app = FastAPI(lifespan=lifespan)
main_app.include_router(router)  
main_app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run(
        "main:main_app",
        host=settings.run.host,
        port=settings.run.port,
        reload=settings.run.reload,
    )
