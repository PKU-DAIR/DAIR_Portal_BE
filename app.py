import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import shutil
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware

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

with open('./api/app_config.json') as f:
    app_config = json.load(f)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许的前端地址
    allow_credentials=True,  # 是否允许发送 Cookie
    allow_methods=["*"],  # 允许的 HTTP 方法
    allow_headers=["*"],  # 允许的请求头
)

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

@app.get("/")
def home():
    res = response_body(message='PKU_DAIR Backend is running...')
    return res()
