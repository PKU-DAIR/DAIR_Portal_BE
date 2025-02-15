import os
import json
from tinydb import TinyDB
from fastapi import APIRouter, Header
from api.models.body import response_body, User
from api.models.tinydb_middle import LockingMiddleware
import asyncio

router = APIRouter()

apply_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)

user_db = TinyDB('db/user_db.json', Storage=LockingMiddleware)

@router.post("/apply_user")
async def apply(user: User):
    if user.invite_code != app_config['invite_code']:
        return response_body(code='403', status='failed', message='invlid invite code')
    if user_db.search(lambda x: x['userid'] == user.userid):
        return response_body(code=400, status='failed', message='User already exists')

    user_data = user.dict()  # 将 Pydantic 模型转换为字典
    user_db.insert(user_data)

    return response_body(code=200, status='success', message='User registered successfully', data=user_data)

@router.get("/user/get_users")
async def get_users():
    res = response_body(message='PKU_DAIR Users is running...')
    return res()
