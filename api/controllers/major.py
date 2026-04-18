import json
import uuid
from fastapi import APIRouter
from api.models.body import response_body, Major
from api.models.verify_tool import Auth
from api.models.db_models import MajorDBModel

router = APIRouter(tags=['Major'])

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)


@router.get('/get_majors')
@auth.require_user()
async def get_majors():
    all_data = await MajorDBModel.all().values('id', 'name')
    return response_body(code=200, status='success', data=all_data)


@router.post('/add_major')
@auth.require_admin()
async def add_major(major: Major):
    major_data = major.dict()
    if await MajorDBModel.filter(name=major_data['name']).exists():
        return response_body(code=4001, status='failed', message='Major already exists')
    major_data['id'] = str(uuid.uuid4())
    await MajorDBModel.create(**major_data)
    return response_body(code=200, status='success', message='Major added successfully', data=major_data)


@router.post('/remove_major')
@auth.require_admin()
async def remove_major(major: Major):
    removed = await MajorDBModel.filter(id=major.id).delete()
    if removed == 0:
        return response_body(code=4004, status='failed', message='Major does not exist')
    return response_body(code=200, status='success', message='Major removed successfully')
