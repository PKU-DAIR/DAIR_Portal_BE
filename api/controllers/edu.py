import os
import json
import uuid
from tinydb import Query
from fastapi import APIRouter, Header
from api.models.body import response_body, Edu
from api.models.db_init import ensure_db
from api.models.verify_tool import valid_user
import asyncio

router = APIRouter()

edu_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)

edu_db = ensure_db('edu_db.json')


@router.get("/get_edus")
async def get_edus(api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with edu_lock:
        all_data = edu_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_edu")
async def add_edu(edu: Edu, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with edu_lock:
        edu_data = edu.dict()
        if edu_db.search(lambda x: x['name'] == edu_data['name']):
            return response_body(code=4001, status='failed', message='Edu already exists')
        edu_data['id'] = str(uuid.uuid4())
        edu_db.insert(edu_data)
    return response_body(code=200, status='success', message='Edu added successfully', data=edu_data)


@router.post("/remove_edu")
async def remove_edu(edu: Edu, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with edu_lock:
        EduQuery = Query()
        result = edu_db.search(EduQuery.id == edu.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='Edu does not exist')
        edu_db.remove(EduQuery.id == edu.id)
    return response_body(code=200, status='success', message='Edu removed successfully')
