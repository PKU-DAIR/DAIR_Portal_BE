import os
import json
import uuid
from tinydb import Query
from fastapi import APIRouter, Header
from api.models.body import response_body, AwardItem, AwardLevel
from api.models.db_init import ensure_db
from api.models.verify_tool import valid_user
import asyncio

router = APIRouter()

award_item_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)

award_item_db = ensure_db('award_item_db.json')

award_level_lock = asyncio.Lock()

award_level_db = ensure_db('award_level_db.json')


@router.get("/get_award_levels")
async def get_award_levels(api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with award_level_lock:
        all_data = award_level_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_award_level")
async def add_award_level(award_level: AwardLevel, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with award_level_lock:
        award_level_data = award_level.dict()
        if award_level_db.search(lambda x: x['level'] == award_level_data['level']):
            return response_body(code=4001, status='failed', message='AwardLevel already exists')
        award_level_data['id'] = str(uuid.uuid4())
        award_level_db.insert(award_level_data)
    return response_body(code=200, status='success', message='AwardLevel added successfully', data=award_level_data)


@router.post("/remove_award_level")
async def remove_award_level(award_level: AwardLevel, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with award_level_lock:
        AwardLevelQuery = Query()
        result = award_level_db.search(AwardLevelQuery.id == award_level.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='AwardLevel does not exist')
        award_level_db.remove(AwardLevelQuery.id == award_level.id)
    return response_body(code=200, status='success', message='AwardLevel removed successfully')


@router.get("/get_award_items")
async def get_award_items(api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with award_item_lock:
        all_data = award_item_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_award_item")
async def add_award_item(award_item: AwardItem, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with award_item_lock:
        award_item_data = award_item.dict()
        if award_item_db.search(lambda x: x['name'] == award_item_data['name']):
            return response_body(code=4001, status='failed', message='AwardItem already exists')
        award_item_data['id'] = str(uuid.uuid4())
        award_item_db.insert(award_item_data)
    return response_body(code=200, status='success', message='AwardItem added successfully', data=award_item_data)


@router.post("/remove_award_item")
async def remove_award_item(award_item: AwardItem, api_key=Header(None)):
    valid_info, valid_status = valid_user(api_key, app_config['jwt_key'])
    if not valid_status:
        return response_body(code=403, status='failed', message=valid_info['message'])
    role = valid_info['role']
    if role.find('admin') < 0:
        return response_body(code=403, status='failed', message='permission denied')
    async with award_item_lock:
        AwardItemQuery = Query()
        result = award_item_db.search(AwardItemQuery.id == award_item.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='AwardItem does not exist')
        award_item_db.remove(AwardItemQuery.id == award_item.id)
    return response_body(code=200, status='success', message='AwardItem removed successfully')
