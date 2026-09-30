from fastapi import APIRouter

from app.api.communication_registers import router as communication_registers_router
from app.api.health import router as health_router
from app.api.language_profiles import router as language_profiles_router
from app.api.languages import router as languages_router
from app.api.users import router as users_router
from app.api.practice_sessions import router as practice_session

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(users_router)
api_router.include_router(languages_router)
api_router.include_router(communication_registers_router)
api_router.include_router(language_profiles_router)
api_router.include_router(practice_session)
