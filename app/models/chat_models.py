from pydantic import BaseModel

class UserQuery(BaseModel):
    session_id : str
    text: str
    tag: str

class ChatResponse(BaseModel):
    response: str
