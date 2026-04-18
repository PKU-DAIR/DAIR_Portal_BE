import json
import uuid
from fastapi import APIRouter
from api.models.body import response_body, Team, ClientTeam
from api.models.verify_tool import Auth
from api.models.db_models import TeamDBModel, ClientTeamDBModel

router = APIRouter(tags=['Team'])

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)


@router.get('/get_teams')
@auth.require_user()
async def get_teams():
    all_data = await TeamDBModel.all().values('id', 'name')
    return response_body(code=200, status='success', data=all_data)


@router.post('/add_team')
@auth.require_admin()
async def add_team(team: Team):
    team_data = team.dict()
    if await TeamDBModel.filter(name=team_data['name']).exists():
        return response_body(code=4001, status='failed', message='Team already exists')
    team_data['id'] = str(uuid.uuid4())
    await TeamDBModel.create(**team_data)
    return response_body(code=200, status='success', message='Team added successfully', data=team_data)


@router.post('/remove_team')
@auth.require_admin()
async def remove_team(team: Team):
    removed = await TeamDBModel.filter(id=team.id).delete()
    if removed == 0:
        return response_body(code=4004, status='failed', message='Team does not exist')
    return response_body(code=200, status='success', message='Team removed successfully')


@router.get('/get_client_teams')
async def get_client_teams():
    all_data = await ClientTeamDBModel.all().values('id', 'name', 'groups')
    return response_body(code=200, status='success', data=all_data)


@router.post('/add_client_team')
@auth.require_admin()
async def add_client_team(team: ClientTeam):
    team_data = team.dict()
    if await ClientTeamDBModel.filter(name=team_data['name']).exists():
        return response_body(code=4001, status='failed', message='Team already exists')
    team_data['id'] = team_data.get('id') or str(uuid.uuid4())
    await ClientTeamDBModel.create(**team_data)
    return response_body(code=200, status='success', message='Team added successfully', data=team_data)


@router.post('/remove_client_team')
@auth.require_admin()
async def remove_client_team(team: Team):
    removed = await ClientTeamDBModel.filter(name=team.name).delete()
    if removed == 0:
        return response_body(code=4004, status='failed', message='Team does not exist')
    return response_body(code=200, status='success', message='Team removed successfully')


@router.post('/add_client_team/group')
@auth.require_admin()
async def update_client_team_group(team: ClientTeam):
    team_data = team.dict()
    updated = await ClientTeamDBModel.filter(name=team_data['name']).update(groups=team_data['groups'])
    if updated == 0:
        return response_body(code=4001, status='failed', message='Team does not exist')
    return response_body(code=200, status='success', message='Team added successfully', data=team.groups)
