from fastapi import APIRouter
from app.api.endpoints import auth, settings_api, upload, problems, solve, memory, admin, paths, usage, sessions, solve_sessions, materials, english_upload, chat, library_trash, match_answers, english_wrong

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(settings_api.router, prefix="/settings", tags=["settings"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(problems.router, prefix="/problems", tags=["problems"])
api_router.include_router(solve.router, prefix="/problems", tags=["solve"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(paths.router, prefix="/paths", tags=["paths"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(solve_sessions.router, prefix="/solve-sessions", tags=["solve-sessions"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(english_upload.router, prefix="/english-upload", tags=["english-upload"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(library_trash.router, prefix="/library-trash", tags=["library-trash"])
api_router.include_router(match_answers.router, prefix="/match-answers", tags=["match-answers"])
api_router.include_router(english_wrong.router, prefix="/english-wrong", tags=["english-wrong"])
