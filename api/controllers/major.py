import os
import json
import uuid
from tinydb import Query
from fastapi import APIRouter, Header
from api.models.body import response_body, Major
from api.models.db_init import ensure_db
from api.models.verify_tool import valid_user
import asyncio

router = APIRouter()

major_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)

major_db = ensure_db('major_db.json')


@router.get("/get_majors")
async def get_majors(api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with major_lock:
        all_data = major_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_major")
async def add_major(major: Major, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with major_lock:
        major_data = major.dict()
        if major_db.search(lambda x: x['name'] == major_data['name']):
            return response_body(code=4001, status='failed', message='Major already exists')
        major_data['id'] = str(uuid.uuid4())
        major_db.insert(major_data)
    return response_body(code=200, status='success', message='Major added successfully', data=major_data)


@router.post("/remove_major")
async def remove_major(major: Major, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with major_lock:
        MajorQuery = Query()
        result = major_db.search(MajorQuery.id == major.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='Major does not exist')
        major_db.remove(MajorQuery.id == major.id)
    return response_body(code=200, status='success', message='Major removed successfully')
