from typing import Optional
from pydantic import BaseModel

class response_body:
    def __init__(self, code=200, status='success', message='', data=None):
        self.code = code
        self.status = status
        self.message = message
        self.data = data
    
    def __call__(self):
        res = {}
        for key, value in self.__dict__.items():
            if value:
                res[key] = value
        return res

class User(BaseModel):
    userid: str
    name: Optional[str]
    pwd: str
    email: Optional[str]
    phone: Optional[str]
    gender: Optional[str]
    invite_code: Optional[str]
    role: Optional[str]