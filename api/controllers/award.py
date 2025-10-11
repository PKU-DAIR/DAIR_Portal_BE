import os
import json
import uuid
from tinydb import Query
from fastapi import APIRouter, Header, Depends
from api.models.body import response_body, AwardItem, AwardLevel
from api.models.db_init import ensure_db
from api.models.verify_tool import Auth
import asyncio

router = APIRouter()

award_item_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

award_item_db = ensure_db('award_item_db.json')

award_level_lock = asyncio.Lock()

award_level_db = ensure_db('award_level_db.json')


@router.get("/get_award_levels")
@auth.require_user()
async def get_award_levels():
    async with award_level_lock:
        all_data = award_level_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_award_level")
@auth.require_admin()
async def add_award_level(award_level: AwardLevel):
    async with award_level_lock:
        award_level_data = award_level.dict()
        if award_level_db.search(lambda x: x['level'] == award_level_data['level']):
            return response_body(code=4001, status='failed', message='AwardLevel already exists')
        award_level_data['id'] = str(uuid.uuid4())
        award_level_db.insert(award_level_data)
    return response_body(code=200, status='success', message='AwardLevel added successfully', data=award_level_data)


@router.post("/remove_award_level")
@auth.require_admin()
async def remove_award_level(award_level: AwardLevel):
    async with award_level_lock:
        AwardLevelQuery = Query()
        result = award_level_db.search(AwardLevelQuery.id == award_level.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='AwardLevel does not exist')
        award_level_db.remove(AwardLevelQuery.id == award_level.id)
    return response_body(code=200, status='success', message='AwardLevel removed successfully')


@router.get("/get_award_items")
@auth.require_user()
async def get_award_items():
    async with award_item_lock:
        all_data = award_item_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_award_item")
@auth.require_admin()
async def add_award_item(award_item: AwardItem):
    async with award_item_lock:
        award_item_data = award_item.dict()
        if award_item_db.search(lambda x: x['name'] == award_item_data['name']):
            return response_body(code=4001, status='failed', message='AwardItem already exists')
        award_item_data['id'] = str(uuid.uuid4())
        award_item_db.insert(award_item_data)
    return response_body(code=200, status='success', message='AwardItem added successfully', data=award_item_data)


@router.post("/remove_award_item")
@auth.require_admin()
async def remove_award_item(award_item: AwardItem):
    async with award_item_lock:
        AwardItemQuery = Query()
        result = award_item_db.search(AwardItemQuery.id == award_item.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='AwardItem does not exist')
        award_item_db.remove(AwardItemQuery.id == award_item.id)
    return response_body(code=200, status='success', message='AwardItem removed successfully')
