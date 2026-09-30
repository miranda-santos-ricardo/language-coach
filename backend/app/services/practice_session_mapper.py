from app.models import PracticeSession
from app.schemas.practice_session import PracticeSessionRead

def to_practice_session_read(
        practice_session: PracticeSession
) -> PracticeSessionRead:
    profile = practice_session.language_profile
    variant = profile.language_variant
    language = variant.language
    register = practice_session.communication_register

    return PracticeSessionRead.model_validate (
        {
            "id": practice_session.id,
            "language_profile_id": practice_session.language_profile_id,
            "training_mode": practice_session.training_mode,
            "register": register.code,
            "profile_cefr": practice_session.profile_cefr_snapshot,
            "target_cefr": practice_session.target_cefr,
            "effective_cefr": practice_session.effective_cefr,
            "language": language.code,
            "variant": variant.code,
            "scenario_key": practice_session.scenario_key,
            "status": practice_session.status,
            "started_at": practice_session.started_at,
            "ended_at": practice_session.ended_at,
            "created_at": practice_session.created_at,
            "updated_at": practice_session.updated_at,
        }
    )