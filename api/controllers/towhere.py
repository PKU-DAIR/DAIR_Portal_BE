import os
import json
import uuid
from tinydb import Query
from fastapi import APIRouter, Header, Depends
from api.models.body import response_body, ToWhere
from api.models.db_init import ensure_db
from api.models.verify_tool import Auth
import asyncio

router = APIRouter()

towhere_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

towhere_db = ensure_db('towhere_db.json')


@router.get("/get_towheres")
@auth.require_user()
async def get_towheres():
    async with towhere_lock:
        all_data = towhere_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_towhere")
@auth.require_admin()
async def add_towhere(towhere: ToWhere):
    async with towhere_lock:
        towhere_data = towhere.dict()
        if towhere_db.search(lambda x: x['name'] == towhere_data['name']):
            return response_body(code=4001, status='failed', message='ToWhere already exists')
        towhere_data['id'] = str(uuid.uuid4())
        towhere_db.insert(towhere_data)
    return response_body(code=200, status='success', message='ToWhere added successfully', data=towhere_data)


@router.post("/remove_towhere")
@auth.require_admin()
async def remove_towhere(towhere: ToWhere):
    async with towhere_lock:
        ToWhereQuery = Query()
        result = towhere_db.search(ToWhereQuery.id == towhere.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='ToWhere does not exist')
        towhere_db.remove(ToWhereQuery.id == towhere.id)
    return response_body(code=200, status='success', message='ToWhere removed successfully')
