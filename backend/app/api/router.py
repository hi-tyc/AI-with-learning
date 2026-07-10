from fastapi import APIRouter
from app.api.endpoints import auth, settings_api, admin, materials, school

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(settings_api.router, prefix="/settings", tags=["settings"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(school.router, prefix="/school", tags=["school"])
