from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import CommunicationRegister
from app.schemas import CommunicationRegisterRead
from app.services import CommunicationRegisterService

router = APIRouter(
    prefix="/communication-registers",
    tags=["communication-registers"],
)
service = CommunicationRegisterService()


@router.get("", response_model=list[CommunicationRegisterRead])
def list_communication_registers(
    session: Annotated[Session, Depends(get_db)],
) -> list[CommunicationRegister]:
    return service.list(session)
