from __future__ import annotations

import os
import secrets
import hmac
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app_config import DATA_DIR, load_config, save_config

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
LOG_PATH = DATA_DIR / "let_bot.log"
ADMIN_AUTH_PATH = DATA_DIR / "admin_auth.json"
_ADMIN_AUTH_CACHE: tuple[str, str, bool] | None = None
_ADMIN_AUTH_LOGGED = False
SESSION_TTL_SECONDS = 12 * 60 * 60
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_FAILURES = 8
_SESSIONS: dict[str, float] = {}
_LOGIN_FAILURES: dict[str, list[float]] = {}


def log_auto_admin_auth(username: str, password: str, from_file: bool) -> None:
    global _ADMIN_AUTH_LOGGED
    if _ADMIN_AUTH_LOGGED:
        return
    print(f"LET_ADMIN_USERNAME={username}", flush=True)
    if from_file:
        print("LET_ADMIN_PASSWORD=<stored plaintext in /app/data/admin_auth.json>", flush=True)
        print("LET_ADMIN_SOURCE=existing", flush=True)
    else:
        print(f"LET_ADMIN_PASSWORD={password}", flush=True)
        print("LET_ADMIN_SOURCE=generated", flush=True)
    _ADMIN_AUTH_LOGGED = True


def get_admin_auth() -> tuple[str, str]:
    global _ADMIN_AUTH_CACHE
    if _ADMIN_AUTH_CACHE:
        username, password, from_file = _ADMIN_AUTH_CACHE
        if from_file:
            log_auto_admin_auth(username, password, from_file=True)
        return username, password

    env_user = os.getenv("ADMIN_USERNAME", "").strip()
    env_password = os.getenv("ADMIN_PASSWORD", "").strip()
    if env_user and env_password:
        _ADMIN_AUTH_CACHE = (env_user, env_password, False)
        return env_user, env_password

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ADMIN_AUTH_PATH.exists():
        try:
            import json

            data = json.loads(ADMIN_AUTH_PATH.read_text(encoding="utf-8"))
            username = str(data.get("username", "")).strip()
            password = str(data.get("password", "")).strip()
            password_hash = str(data.get("password_hash", "")).strip()
            if username and password:
                _ADMIN_AUTH_CACHE = (username, password, True)
                log_auto_admin_auth(username, password, from_file=True)
                return username, password
            if username and password_hash:
                new_password = secrets.token_urlsafe(18)
                ADMIN_AUTH_PATH.write_text(
                    json.dumps(
                        {"username": username, "password": new_password},
                        ensure_ascii=False,
                        indent=2,
                    ) + "\n",
                    encoding="utf-8",
                )
                try:
                    ADMIN_AUTH_PATH.chmod(0o600)
                except OSError:
                    pass
                _ADMIN_AUTH_CACHE = (username, new_password, True)
                log_auto_admin_auth(username, new_password, from_file=False)
                return username, new_password
        except (OSError, ValueError):
            pass

    import json

    username = "admin"
    password = secrets.token_urlsafe(18)
    ADMIN_AUTH_PATH.write_text(
        json.dumps({"username": username, "password": password}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        ADMIN_AUTH_PATH.chmod(0o600)
    except OSError:
        pass
    _ADMIN_AUTH_CACHE = (username, password, True)
    log_auto_admin_auth(username, password, from_file=False)
    return username, password

app = FastAPI(title="LET Bot Admin")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def ensure_admin_auth() -> None:
    get_admin_auth()


class ConfigPayload(BaseModel):
    config: dict[str, object]


class LoginPayload(BaseModel):
    username: str
    password: str


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_login_limit(key: str) -> None:
    now = time.time()
    failures = [ts for ts in _LOGIN_FAILURES.get(key, []) if now - ts < LOGIN_WINDOW_SECONDS]
    _LOGIN_FAILURES[key] = failures
    if len(failures) >= LOGIN_MAX_FAILURES:
        raise HTTPException(status_code=429, detail="登录失败次数过多，请稍后再试")


def record_login_failure(key: str) -> None:
    now = time.time()
    _LOGIN_FAILURES[key] = [
        ts for ts in _LOGIN_FAILURES.get(key, []) if now - ts < LOGIN_WINDOW_SECONDS
    ] + [now]


def clear_login_failures(key: str) -> None:
    _LOGIN_FAILURES.pop(key, None)


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = time.time() + SESSION_TTL_SECONDS
    return token


def require_admin(x_admin_session: str | None = Header(default=None)) -> None:
    now = time.time()
    for token, expires_at in list(_SESSIONS.items()):
        if expires_at <= now:
            _SESSIONS.pop(token, None)
    if not x_admin_session or _SESSIONS.get(x_admin_session, 0) <= now:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    _SESSIONS[x_admin_session] = now + SESSION_TTL_SECONDS


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/auth/login")
async def login(payload: LoginPayload, request: Request) -> dict[str, object]:
    key = client_key(request)
    check_login_limit(key)
    username, password = get_admin_auth()
    if not hmac.compare_digest(payload.username or "", username):
        record_login_failure(key)
        raise HTTPException(status_code=401, detail="管理员账号不存在")
    if not hmac.compare_digest(payload.password or "", password):
        record_login_failure(key)
        raise HTTPException(status_code=401, detail="管理员密码错误")
    clear_login_failures(key)
    return {"message": "登录成功", "session": create_session(), "expires_in": SESSION_TTL_SECONDS}


@app.get("/api/config")
async def get_config(
    x_admin_session: str | None = Header(default=None),
) -> dict[str, object]:
    require_admin(x_admin_session)
    return {"config": load_config(mask_secrets=True)}


@app.post("/api/config")
async def update_config(
    payload: ConfigPayload,
    x_admin_session: str | None = Header(default=None),
) -> dict[str, object]:
    require_admin(x_admin_session)
    return {"config": save_config(payload.config), "message": "配置已保存"}


@app.get("/api/logs")
async def get_logs(
    lines: int = 400,
    x_admin_session: str | None = Header(default=None),
) -> dict[str, object]:
    require_admin(x_admin_session)
    lines = max(50, min(lines, 3000))
    if not LOG_PATH.exists():
        return {"logs": ""}

    with LOG_PATH.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(size - 256_000, 0))
        text = fh.read().decode("utf-8", errors="replace")

    return {"logs": "\n".join(text.splitlines()[-lines:])}


@app.post("/api/logs/clear")
async def clear_logs(
    x_admin_session: str | None = Header(default=None),
) -> JSONResponse:
    require_admin(x_admin_session)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")
    return JSONResponse({"message": "日志已清空"})
