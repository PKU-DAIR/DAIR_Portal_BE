import os
import json
import uuid
from tinydb import Query
from fastapi import APIRouter, Header
from api.models.body import response_body, ToWhere
from api.models.db_init import ensure_db
from api.models.verify_tool import valid_user
import asyncio

router = APIRouter()

towhere_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)

towhere_db = ensure_db('towhere_db.json')


@router.get("/get_towheres")
async def get_towheres(api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with towhere_lock:
        all_data = towhere_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_towhere")
async def add_towhere(towhere: ToWhere, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with towhere_lock:
        towhere_data = towhere.dict()
        if towhere_db.search(lambda x: x['name'] == towhere_data['name']):
            return response_body(code=4001, status='failed', message='ToWhere already exists')
        towhere_data['id'] = str(uuid.uuid4())
        towhere_db.insert(towhere_data)
    return response_body(code=200, status='success', message='ToWhere added successfully', data=towhere_data)


@router.post("/remove_towhere")
async def remove_towhere(towhere: ToWhere, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with towhere_lock:
        ToWhereQuery = Query()
        result = towhere_db.search(ToWhereQuery.id == towhere.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='ToWhere does not exist')
        towhere_db.remove(ToWhereQuery.id == towhere.id)
    return response_body(code=200, status='success', message='ToWhere removed successfully')
