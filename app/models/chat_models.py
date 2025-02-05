from pydantic import BaseModel

class UserQuery(BaseModel):
    session_id : str
    text: str
    tag: str
    jwt_token: str | None

class ChatResponse(BaseModel):
    response: str
