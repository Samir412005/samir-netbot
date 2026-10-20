import asyncio
import ipaddress
import os
import time
from collections import defaultdict, deque
from typing import Literal
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from core import service

app = FastAPI(title='Samir Netbot device API')
from api.learn import router as learn_router
app.include_router(learn_router)
attempts = defaultdict(deque)

@app.middleware('http')
async def https_only(request: Request, call_next):
    # Trust forwarded headers ONLY from your reverse proxy (uvicorn --forwarded-allow-ips).
    local = os.getenv('ALLOW_HTTP_LOCAL','false') == 'true' and request.client and request.client.host in ('127.0.0.1','::1','testclient')
    if request.url.scheme != 'https' and not local:
        from starlette.responses import JSONResponse
        return JSONResponse({'detail':'HTTPS required'}, status_code=426)
    return await call_next(request)

class Registration(BaseModel):
    code: str = Field(pattern=r'^\d{6}$')
    name: str = Field(default='Android', min_length=1, max_length=80)

class Result(BaseModel):
    command_id: str = Field(min_length=36, max_length=36)
    outcome: Literal['response','fail','timeout']
    response: str = Field(default='', max_length=4000)

def bearer(authorization):
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401, 'Missing device token')
    return authorization[7:]

def run(fn, *args):
    try: return fn(*args)
    except ValueError as e:
        code = 401 if str(e) == 'unauthorized' else 400
        raise HTTPException(code, str(e)) from None

@app.get('/health')
def health():
    from sqlalchemy import text
    from core.db import Session
    with Session() as s: s.execute(text('SELECT 1'))
    return {'status':'ok'}

@app.post('/device/register')
def register(data: Registration, request: Request):
    # Single replica MVP limiter. Use Redis or gateway quotas before horizontal scaling.
    ip = request.client.host if request.client else 'unknown'
    q = attempts[ip]; t = time.monotonic()
    while q and q[0] < t-300: q.popleft()
    if len(q) >= 5: raise HTTPException(429, 'Too many pairing attempts; wait 5 minutes')
    q.append(t)
    if len(attempts) > 10000:
        for k in list(attempts):
            if not attempts[k] or attempts[k][-1] < t-300: attempts.pop(k, None)
    return run(service.register, data.code, data.name)

@app.get('/device/commands')
async def commands(authorization: str | None = Header(default=None)):
    token = bearer(authorization)
    for _ in range(20):
        command = run(service.poll, token)
        if command: return {'command':command}
        await asyncio.sleep(1)
    return {'command':None}

@app.post('/device/result')
def result(data: Result, authorization: str | None = Header(default=None)):
    return {'state':run(service.result, bearer(authorization), data.command_id, data.outcome, data.response)}
