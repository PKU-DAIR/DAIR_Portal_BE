import json
import uuid
from fastapi import APIRouter
from api.models.body import response_body, ToWhere
from api.models.verify_tool import Auth
from api.models.db_models import ToWhereDBModel

router = APIRouter(tags=['ToWhere'])

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)


@router.get('/get_towheres')
@auth.require_user()
async def get_towheres():
    all_data = await ToWhereDBModel.all().values('id', 'name')
    return response_body(code=200, status='success', data=all_data)


@router.post('/add_towhere')
@auth.require_admin()
async def add_towhere(towhere: ToWhere):
    towhere_data = towhere.dict()
    if await ToWhereDBModel.filter(name=towhere_data['name']).exists():
        return response_body(code=4001, status='failed', message='ToWhere already exists')
    towhere_data['id'] = str(uuid.uuid4())
    await ToWhereDBModel.create(**towhere_data)
    return response_body(code=200, status='success', message='ToWhere added successfully', data=towhere_data)


@router.post('/remove_towhere')
@auth.require_admin()
async def remove_towhere(towhere: ToWhere):
    removed = await ToWhereDBModel.filter(id=towhere.id).delete()
    if removed == 0:
        return response_body(code=4004, status='failed', message='ToWhere does not exist')
    return response_body(code=200, status='success', message='ToWhere removed successfully')
