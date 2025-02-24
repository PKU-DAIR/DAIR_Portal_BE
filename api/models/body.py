from typing import Optional, List
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
    name: Optional[str] = None
    pwd: str
    avatar: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    invite_code: Optional[str] = None
    role: Optional[str] = None


class UserInfo(User):
    userid: str = None
    pwd: str = None


class UserSecurityInfo(BaseModel):
    userid: str = None
    pwd: str
    confirm_pwd: str


class Major(BaseModel):
    id: str = None
    name: str = None


class Group(BaseModel):
    id: str = None
    name: str = None


class Edu(BaseModel):
    id: str = None
    name: str = None


class Team(BaseModel):
    id: str = None
    name: str = None

class ClientTeam(BaseModel):
    id: str = None
    name: str = None
    groups: List[Group] = None

class ToWhere(BaseModel):
    id: str = None
    name: str = None


class AwardItem(BaseModel):
    id: str = None
    name: str = None


class AwardLevel(BaseModel):
    id: str = None
    level: str = None


class MemberAward(BaseModel):
    competitionName: str
    level: str
    session: str
    date: str
    region: str


class MemberInfo(BaseModel):
    id: str = None
    name: str
    grade: str
    session: str
    major: str
    title: str
    toWhere: str
    postAddress: str
    educations: List[Edu]
    teams: List[Team]
    groups: List[Group]
    introduction: str
    photo: str = None
    userid: Optional[str] = None
    awards: List[MemberAward]
    email: str
    mobile: str
