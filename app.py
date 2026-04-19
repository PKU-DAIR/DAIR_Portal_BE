import os
import sys
import json
import asyncio
import contextlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.models.body import response_body
from api.controllers.user import router as user_router
from api.controllers.major import router as major_router
from api.controllers.group import router as group_router
from api.controllers.edu import router as edu_router
from api.controllers.team import router as team_router
from api.controllers.towhere import router as towhere_router
from api.controllers.award import router as award_router
from api.controllers.member import router as member_router
from api.controllers.news import router as news_router
from api.controllers.pub import router as pub_router
from api.models.db_backup import create_monthly_db_backup

with open('./api/app_config.json') as f:
    app_config = json.load(f)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = 'sqlite://./db/db.sqlite3'
BACKUP_CHECK_SECONDS = 24 * 60 * 60
TORTOISE_MODULES = {'models': ['api.models.db_models']}
backup_task = None

os.makedirs('./db', exist_ok=True)
register_tortoise(
    app,
    db_url=DB_URL,
    modules=TORTOISE_MODULES,
    generate_schemas=True,
    add_exception_handlers=True,
)


async def run_db_backup():
    try:
        await asyncio.to_thread(create_monthly_db_backup)
    except Exception as exc:
        print(f'Database backup failed: {exc}')


async def periodic_db_backup():
    while True:
        await asyncio.sleep(BACKUP_CHECK_SECONDS)
        await run_db_backup()


@app.on_event('startup')
async def startup():
    global backup_task
    await run_db_backup()
    backup_task = asyncio.create_task(periodic_db_backup())


@app.on_event('shutdown')
async def shutdown():
    if backup_task is not None:
        backup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await backup_task

app.include_router(user_router)
app.include_router(major_router)
app.include_router(group_router)
app.include_router(edu_router)
app.include_router(team_router)
app.include_router(towhere_router)
app.include_router(award_router)
app.include_router(member_router)
app.include_router(news_router)
app.include_router(pub_router)


@app.get('/', operation_id='Home')
def home():
    res = response_body(message='PKU_DAIR Backend is running...')
    return res()
