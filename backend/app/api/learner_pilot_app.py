"""Isolated opt-in pilot application; never auto-mounted by app.main.

The host MUST deploy this as an alternative to the legacy application,
not alongside public legacy /users routes on the same app instance.
"""
from __future__ import annotations

from typing import Callable
from fastapi import FastAPI
from app.api.communication_registers import router as registers_router
from app.api.health import router as health_router
from app.api.languages import router as languages_router
from app.services.learner_identity import VerifiedLearnerIdentity
from app.services.learner_pilot_routes import create_guarded_learner_router


def create_learner_pilot_app(
    *, verify_bearer_token: Callable[[str], VerifiedLearnerIdentity],
) -> FastAPI:
    """Explicit factory requiring a host verifier; denies legacy public user APIs."""
    guarded = create_guarded_learner_router(verify_bearer_token)
    app = FastAPI(title="Language Coach — Isolated Learner Pilot (experimental)")
    app.include_router(health_router)
    app.include_router(languages_router)
    app.include_router(registers_router)
    app.include_router(guarded)
    return app
