import json
import uuid
from fastapi import APIRouter
from api.models.body import response_body, AwardItem, AwardLevel
from api.models.verify_tool import Auth
from api.models.db_models import AwardItemDBModel, AwardLevelDBModel

router = APIRouter(tags=['Award'])

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)


@router.get('/get_award_levels')
@auth.require_user()
async def get_award_levels():
    all_data = await AwardLevelDBModel.all().values('id', 'level')
    return response_body(code=200, status='success', data=all_data)


@router.post('/add_award_level')
@auth.require_admin()
async def add_award_level(award_level: AwardLevel):
    award_level_data = award_level.dict()
    if await AwardLevelDBModel.filter(level=award_level_data['level']).exists():
        return response_body(code=4001, status='failed', message='AwardLevel already exists')
    award_level_data['id'] = str(uuid.uuid4())
    await AwardLevelDBModel.create(**award_level_data)
    return response_body(code=200, status='success', message='AwardLevel added successfully', data=award_level_data)


@router.post('/remove_award_level')
@auth.require_admin()
async def remove_award_level(award_level: AwardLevel):
    removed = await AwardLevelDBModel.filter(id=award_level.id).delete()
    if removed == 0:
        return response_body(code=4004, status='failed', message='AwardLevel does not exist')
    return response_body(code=200, status='success', message='AwardLevel removed successfully')


@router.get('/get_award_items')
@auth.require_user()
async def get_award_items():
    all_data = await AwardItemDBModel.all().values('id', 'name')
    return response_body(code=200, status='success', data=all_data)


@router.post('/add_award_item')
@auth.require_admin()
async def add_award_item(award_item: AwardItem):
    award_item_data = award_item.dict()
    if await AwardItemDBModel.filter(name=award_item_data['name']).exists():
        return response_body(code=4001, status='failed', message='AwardItem already exists')
    award_item_data['id'] = str(uuid.uuid4())
    await AwardItemDBModel.create(**award_item_data)
    return response_body(code=200, status='success', message='AwardItem added successfully', data=award_item_data)


@router.post('/remove_award_item')
@auth.require_admin()
async def remove_award_item(award_item: AwardItem):
    removed = await AwardItemDBModel.filter(id=award_item.id).delete()
    if removed == 0:
        return response_body(code=4004, status='failed', message='AwardItem does not exist')
    return response_body(code=200, status='success', message='AwardItem removed successfully')
