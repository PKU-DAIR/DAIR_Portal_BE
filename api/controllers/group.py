import json
import uuid
from fastapi import APIRouter
from api.models.body import response_body, Group
from api.models.verify_tool import Auth
from api.models.db_models import GroupDBModel

router = APIRouter(tags=['Group'])

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)


@router.get('/get_groups', operation_id='GetGroups')
@auth.require_user()
async def get_groups():
    all_data = await GroupDBModel.all().values('id', 'name')
    return response_body(code=200, status='success', data=all_data)


@router.post('/add_group', operation_id='AddGroup')
@auth.require_admin()
async def add_group(group: Group):
    group_data = group.dict()
    if await GroupDBModel.filter(name=group_data['name']).exists():
        return response_body(code=4001, status='failed', message='Group already exists')
    group_data['id'] = str(uuid.uuid4())
    await GroupDBModel.create(**group_data)
    return response_body(code=200, status='success', message='Group added successfully', data=group_data)


@router.post('/remove_group', operation_id='RemoveGroup')
@auth.require_admin()
async def remove_group(group: Group):
    removed = await GroupDBModel.filter(id=group.id).delete()
    if removed == 0:
        return response_body(code=4004, status='failed', message='Group does not exist')
    return response_body(code=200, status='success', message='Group removed successfully')
