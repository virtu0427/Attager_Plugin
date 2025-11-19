# 앱 진입점
from fastapi import FastAPI
from . import users

app = FastAPI(title="JWT Auth Server", version="1.0")

app.include_router(users.router)
