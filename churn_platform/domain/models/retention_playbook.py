from pydantic import BaseModel

class RetentionPlaybook(BaseModel):
    action_type: str
    action_payload: str
    channel: str # e.g., SMS, Email, In-App
