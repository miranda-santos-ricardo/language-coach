import uuid

from io import BytesIO

from app.services.errors import (
    CommunicationRegisterNotFoundError, 
    InactiveReferenceDataError, 
    LanguageProfileNotFoundError,
    PracticeSessionNotFoundError, 
    RegisterModeNotAllowedError, 
    UserNotFoundError,
    InvalidPracticeSessionTransitionError
)

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from sqlalchemy.orm import Session

from app.db.session import get_db

from app.schemas.practice_session import (
    PracticeSessionCreate,
    PracticeSessionRead,
)

from app.services.practice_session import PracticeSessionService
from app.services.practice_session_mapper import to_practice_session_read

from app.core.config import get_settings

from app.schemas.transcription import TranscriptionResult

from app.services.audio_upload import validate_audio_upload
from app.services.audio_upload_errors import (
    AudioFileTooLargeError,
    EmptyAudioFileError,
    UnsupportedAudioTypeError,
)

from app.services.transcription_dependencies import (
    get_transcription_service,
)

from app.services.transcription_errors import (
    TranscriptionSessionInactiveError,
)

from app.services.stt_errors import (
    STTConfigurationError,
    STTProviderError,
    STTRateLimitError,
    STTTimeoutError,
)


router = APIRouter(
    prefix="/users/{user_id}/language-profiles/{profile_id}/sessions",
    tags=["practice-sessions"]
)

service = PracticeSessionService()

@router.post(
    "",
    response_model=PracticeSessionRead,
    status_code=status.HTTP_201_CREATED
)
def create_practice_session (
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload:PracticeSessionCreate,
    db: Session = Depends (get_db)
) -> PracticeSessionRead:
    try:
                
        practice_session = service.create(
            db,
            user_id,
            profile_id,
            payload
        )

        return to_practice_session_read(practice_session)

    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except LanguageProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except CommunicationRegisterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    except (
        InactiveReferenceDataError,
        RegisterModeNotAllowedError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

@router.get(
    "",
    response_model=list[PracticeSessionRead]
)
def list_practice_session(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    db: Session = Depends (get_db)
) -> list[PracticeSessionRead]:

    try:
        sessions = service.list(
            db,
            user_id,
            profile_id,
        )

        return [
            to_practice_session_read(practice_session)
            for practice_session in sessions
        ]

    except (
        UserNotFoundError,
        LanguageProfileNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

@router.get(
    "/{practice_session_id}",
    response_model=PracticeSessionRead,
)
def get_practice_session(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    practice_session_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> PracticeSessionRead:
    try:
        practice_session = service.get(
            db,
            user_id,
            profile_id,
            practice_session_id,
        )

        return to_practice_session_read(practice_session)

    except (
        UserNotFoundError,
        LanguageProfileNotFoundError,
        PracticeSessionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

@router.post(
    "/{practice_session_id}/complete",
    response_model=PracticeSessionRead,
)
def complete_practice_session(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    practice_session_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> PracticeSessionRead:
    try:
        practice_session = service.complete(
            db,
            user_id,
            profile_id,
            practice_session_id,
        )

        return to_practice_session_read(practice_session)

    except (
        UserNotFoundError,
        LanguageProfileNotFoundError,
        PracticeSessionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except InvalidPracticeSessionTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

@router.post(
    "/{practice_session_id}/abandon",
    response_model=PracticeSessionRead,
)
def abandon_practice_session(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    practice_session_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> PracticeSessionRead:
    try:
        practice_session = service.abandon(
            db,
            user_id,
            profile_id,
            practice_session_id,
        )

        return to_practice_session_read(practice_session)

    except (
        UserNotFoundError,
        LanguageProfileNotFoundError,
        PracticeSessionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except InvalidPracticeSessionTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/{practice_session_id}/transcriptions",
    response_model=TranscriptionResult,
    status_code=status.HTTP_200_OK,
)
def transcribe_practice_session_audio(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    practice_session_id: uuid.UUID,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> TranscriptionResult:
    try:
        settings = get_settings()

        content = audio.file.read()

        validated_audio = validate_audio_upload(
            content=content,
            filename=audio.filename,
            content_type=audio.content_type,
            max_size_bytes=settings.max_audio_upload_bytes,
        )

        transcription_service = get_transcription_service()

        return transcription_service.transcribe(
            session=db,
            user_id=user_id,
            profile_id=profile_id,
            practice_session_id=practice_session_id,
            audio_file=BytesIO(validated_audio.content),
            filename=validated_audio.filename,
            content_type=validated_audio.content_type,
        )

    except (
        UserNotFoundError,
        LanguageProfileNotFoundError,
        PracticeSessionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except TranscriptionSessionInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except EmptyAudioFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except UnsupportedAudioTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc

    except AudioFileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc

    except STTConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech-to-text service is not configured.",
        ) from exc

    except STTRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech-to-text service is temporarily unavailable.",
        ) from exc

    except STTTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Speech-to-text service timed out.",
        ) from exc

    except STTProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech-to-text service is temporarily unavailable.",
        ) from exc