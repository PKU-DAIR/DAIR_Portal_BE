import os
import json
import uuid
from tinydb import Query
from fastapi import APIRouter, Header, Depends, File
from api.models.body import response_body, Group
from api.models.db_init import ensure_db
from api.models.verify_tool import valid_user, Auth
import asyncio

router = APIRouter()

group_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

group_db = ensure_db('group_db.json')


@router.get("/get_groups")
async def get_groups(vft=Depends(auth.is_admin)):
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    async with group_lock:
        all_data = group_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_group")
async def add_group(group: Group, vft=Depends(auth.is_admin)):
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    async with group_lock:
        group_data = group.dict()
        if group_db.search(lambda x: x['name'] == group_data['name']):
            return response_body(code=4001, status='failed', message='Group already exists')
        group_data['id'] = str(uuid.uuid4())
        group_db.insert(group_data)
    return response_body(code=200, status='success', message='Group added successfully', data=group_data)


@router.post("/remove_group")
async def remove_group(group: Group, vft=Depends(auth.is_admin)):
    if not vft[0]:
        return vft[1]
    valid_info = vft[1]
    async with group_lock:
        GroupQuery = Query()
        result = group_db.search(GroupQuery.id == group.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='Group does not exist')
        group_db.remove(GroupQuery.id == group.id)
    return response_body(code=200, status='success', message='Group removed successfully')
