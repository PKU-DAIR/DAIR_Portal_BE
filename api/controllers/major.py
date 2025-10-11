import os
import json
import uuid
from tinydb import Query
from fastapi import APIRouter, Header, Depends
from api.models.body import response_body, Major
from api.models.db_init import ensure_db
from api.models.verify_tool import Auth
import asyncio

router = APIRouter()

major_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

major_db = ensure_db('major_db.json')


@router.get("/get_majors")
@auth.require_user()
async def get_majors():
    async with major_lock:
        all_data = major_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_major")
@auth.require_admin()
async def add_major(major: Major):
    async with major_lock:
        major_data = major.dict()
        if major_db.search(lambda x: x['name'] == major_data['name']):
            return response_body(code=4001, status='failed', message='Major already exists')
        major_data['id'] = str(uuid.uuid4())
        major_db.insert(major_data)
    return response_body(code=200, status='success', message='Major added successfully', data=major_data)


@router.post("/remove_major")
@auth.require_admin()
async def remove_major(major: Major):
    async with major_lock:
        MajorQuery = Query()
        result = major_db.search(MajorQuery.id == major.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='Major does not exist')
        major_db.remove(MajorQuery.id == major.id)
    return response_body(code=200, status='success', message='Major removed successfully')
