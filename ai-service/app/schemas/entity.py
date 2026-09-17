from pydantic import BaseModel


class EntityRequest(BaseModel):
    transcript: str


class ICDMatch(BaseModel):
    entity: str
    code: str
    description: str
    score: float
    considerations: list[str] = []


class EntityResponse(BaseModel):
    entity_count: int
    entities: list[str]
    matches: list[ICDMatch]