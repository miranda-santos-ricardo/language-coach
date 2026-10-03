from pydantic import BaseModel

class TranscriptionResult(BaseModel):
    transcript: str
    language: str

