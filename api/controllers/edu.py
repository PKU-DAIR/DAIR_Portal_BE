import json
import uuid
from fastapi import APIRouter
from api.models.body import response_body, Edu
from api.models.verify_tool import Auth
from api.models.db_models import EduDBModel

router = APIRouter(tags=['Edu'])

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)


@router.get('/get_edus', operation_id='GetEdus')
@auth.require_user()
async def get_edus():
    all_data = await EduDBModel.all().values('id', 'name')
    return response_body(code=200, status='success', data=all_data)


@router.post('/add_edu', operation_id='AddEdu')
@auth.require_admin()
async def add_edu(edu: Edu):
    edu_data = edu.dict()
    if await EduDBModel.filter(name=edu_data['name']).exists():
        return response_body(code=4001, status='failed', message='Edu already exists')
    edu_data['id'] = str(uuid.uuid4())
    await EduDBModel.create(**edu_data)
    return response_body(code=200, status='success', message='Edu added successfully', data=edu_data)


@router.post('/remove_edu', operation_id='RemoveEdu')
@auth.require_admin()
async def remove_edu(edu: Edu):
    removed = await EduDBModel.filter(id=edu.id).delete()
    if removed == 0:
        return response_body(code=4004, status='failed', message='Edu does not exist')
    return response_body(code=200, status='success', message='Edu removed successfully')
