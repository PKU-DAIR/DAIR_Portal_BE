import os
import json
import uuid
from tinydb import Query
from fastapi import APIRouter, Header, Depends
from api.models.body import response_body, Team, ClientTeam
from api.models.db_init import ensure_db
from api.models.verify_tool import Auth
import asyncio

router = APIRouter(tags=['Team'])

team_lock = asyncio.Lock()
client_team_lock = asyncio.Lock()

with open('./api/app_config.json') as f:
    app_config = json.load(f)
auth = Auth(app_config=app_config)

team_db = ensure_db('team_db.json')
client_team_db = ensure_db('client_team_db.json')


@router.get("/get_teams")
@auth.require_user()
async def get_teams():
    async with team_lock:
        all_data = team_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_team")
@auth.require_admin()
async def add_team(team: Team):
    async with team_lock:
        team_data = team.dict()
        if team_db.search(lambda x: x['name'] == team_data['name']):
            return response_body(code=4001, status='failed', message='Team already exists')
        team_data['id'] = str(uuid.uuid4())
        team_db.insert(team_data)
    return response_body(code=200, status='success', message='Team added successfully', data=team_data)


@router.post("/remove_team")
@auth.require_admin()
async def remove_team(team: Team):
    async with team_lock:
        TeamQuery = Query()
        result = team_db.search(TeamQuery.id == team.id)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='Team does not exist')
        team_db.remove(TeamQuery.id == team.id)
    return response_body(code=200, status='success', message='Team removed successfully')


@router.get("/get_client_teams")
async def get_client_teams():
    async with client_team_lock:
        all_data = client_team_db.all()
    return response_body(code=200, status='success', data=all_data)


@router.post("/add_client_team")
@auth.require_admin()
async def add_client_team(team: ClientTeam):
    async with client_team_lock:
        team_data = team.dict()
        if client_team_db.search(lambda x: x['name'] == team_data['name']):
            return response_body(code=4001, status='failed', message='Team already exists')
        client_team_db.insert(team_data)
    return response_body(code=200, status='success', message='Team added successfully', data=team_data)


@router.post("/remove_client_team")
@auth.require_admin()
async def remove_client_team(team: Team):
    async with client_team_lock:
        TeamQuery = Query()
        result = client_team_db.search(TeamQuery.name == team.name)
        if len(result) == 0:
            return response_body(code=4004, status='failed', message='Team does not exist')
        client_team_db.remove(TeamQuery.name == team.name)
    return response_body(code=200, status='success', message='Team removed successfully')


@router.post("/add_client_team/group")
@auth.require_admin()
async def update_client_team_group(team: ClientTeam):
    async with client_team_lock:
        TeamQuery = Query()
        team_data = team.dict()
        result = client_team_db.search(
            TeamQuery.name == team_data['name'])
        if len(result) == 0:
            return response_body(code=4001, status='failed', message='Team does not exist')
        client_team_db.update({'groups': team_data['groups']},
                              TeamQuery.name == team_data['name'])
    return response_body(code=200, status='success', message='Team added successfully', data=team.groups)
