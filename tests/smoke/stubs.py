"""Lightweight stand-ins for third-party libraries that cannot be installed in
this offline sandbox (aiogram, sqlalchemy, pydantic*, httpx, redis).

These stubs provide JUST enough surface for every ``app.*`` module to import and
for the smoke test to drive the real handler/service control flow. They are NOT
a reimplementation of the libraries -- on the real VPS the genuine packages are
installed via Docker/requirements.txt.

Call :func:`install` once, before importing anything under ``app``.
"""
from __future__ import annotations

import os
import sys
import types
from datetime import datetime


def _mod(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m


def install() -> None:
    if getattr(install, "_done", False):
        return
    install._done = True  # type: ignore[attr-defined]

    _install_aiogram()
    _install_sqlalchemy()
    _install_pydantic()
    _install_httpx()
    _install_redis()


# ---------------------------------------------------------------------------
# aiogram
# ---------------------------------------------------------------------------
def _install_aiogram() -> None:
    aiogram = _mod("aiogram")

    class _FField:
        def __eq__(self, other):
            return ("eq", other)

        def startswith(self, prefix):
            return ("startswith", prefix)

        def in_(self, values):
            return ("in", values)

    class _F:
        data = _FField()

    class BaseMiddleware:
        async def __call__(self, handler, event, data):  # pragma: no cover
            return await handler(event, data)

    class _Observer:
        def outer_middleware(self, mw):
            return mw

        def middleware(self, mw):
            return mw

    class Router:
        def __init__(self, name=None):
            self.name = name

        def _deco(self, *a, **k):
            def wrap(fn):
                return fn

            return wrap

        message = _deco
        callback_query = _deco
        errors = _deco

    class Dispatcher:
        def __init__(self, *a, **k):
            self.message = _Observer()
            self.callback_query = _Observer()

        def include_router(self, r):
            pass

        def errors(self):
            def wrap(fn):
                return fn

            return wrap

        def resolve_used_update_types(self):
            return []

        async def start_polling(self, *a, **k):
            pass

    class Bot:
        def __init__(self, *a, **k):
            pass

    aiogram.F = _F()
    aiogram.BaseMiddleware = BaseMiddleware
    aiogram.Router = Router
    aiogram.Dispatcher = Dispatcher
    aiogram.Bot = Bot

    # aiogram.types
    types_mod = _mod("aiogram.types")

    class _Base:
        def __init__(self, **kw):
            for key, value in kw.items():
                setattr(self, key, value)

    class TelegramObject(_Base):
        pass

    class User(_Base):
        pass

    class Message(_Base):
        pass

    class CallbackQuery(_Base):
        pass

    class ErrorEvent(_Base):
        pass

    class BotCommand(_Base):
        pass

    class InlineKeyboardButton:
        def __init__(self, text=None, callback_data=None, url=None,
                     icon_custom_emoji_id=None, **extra):
            self.text = text
            self.callback_data = callback_data
            self.url = url
            self.icon_custom_emoji_id = icon_custom_emoji_id

    class InlineKeyboardMarkup:
        def __init__(self, inline_keyboard=None, **k):
            self.inline_keyboard = inline_keyboard or []

    for cls in (TelegramObject, User, Message, CallbackQuery, ErrorEvent,
                BotCommand, InlineKeyboardButton, InlineKeyboardMarkup):
        setattr(types_mod, cls.__name__, cls)
    aiogram.types = types_mod

    # aiogram.filters
    filters_mod = _mod("aiogram.filters")

    class Command:
        def __init__(self, *a, **k):
            pass

    class CommandStart:
        def __init__(self, *a, **k):
            pass

    filters_mod.Command = Command
    filters_mod.CommandStart = CommandStart

    # aiogram.enums
    enums_mod = _mod("aiogram.enums")

    class ParseMode:
        HTML = "HTML"
        MARKDOWN = "Markdown"

    enums_mod.ParseMode = ParseMode

    # aiogram.exceptions
    exc_mod = _mod("aiogram.exceptions")

    class TelegramBadRequest(Exception):
        def __init__(self, message="bad request", method=None):
            super().__init__(message)
            self.message = message

    exc_mod.TelegramBadRequest = TelegramBadRequest

    # aiogram.fsm.*
    _mod("aiogram.fsm")
    ctx_mod = _mod("aiogram.fsm.context")

    class FSMContext:
        pass

    ctx_mod.FSMContext = FSMContext

    state_mod = _mod("aiogram.fsm.state")

    class State:
        def __init__(self, *a, **k):
            self.name = None

    class StatesGroup:
        pass

    state_mod.State = State
    state_mod.StatesGroup = StatesGroup

    _mod("aiogram.fsm.storage")
    base_storage = _mod("aiogram.fsm.storage.base")

    class BaseStorage:
        pass

    base_storage.BaseStorage = BaseStorage

    mem_storage = _mod("aiogram.fsm.storage.memory")

    class MemoryStorage(BaseStorage):
        pass

    mem_storage.MemoryStorage = MemoryStorage

    redis_storage = _mod("aiogram.fsm.storage.redis")

    class RedisStorage(BaseStorage):
        @classmethod
        def from_url(cls, *a, **k):
            return cls()

    redis_storage.RedisStorage = RedisStorage

    # aiogram.client.*
    _mod("aiogram.client")
    default_mod = _mod("aiogram.client.default")

    class DefaultBotProperties:
        def __init__(self, *a, **k):
            pass

    default_mod.DefaultBotProperties = DefaultBotProperties

    _mod("aiogram.client.session")
    aiohttp_mod = _mod("aiogram.client.session.aiohttp")

    class AiohttpSession:
        def __init__(self, *a, **k):
            pass

    aiohttp_mod.AiohttpSession = AiohttpSession

    tg_mod = _mod("aiogram.client.telegram")

    class TelegramAPIServer:
        @classmethod
        def from_base(cls, base, is_local=False):
            return cls()

    tg_mod.TelegramAPIServer = TelegramAPIServer

    # attach submodules as attributes
    aiogram.client = sys.modules["aiogram.client"]
    aiogram.filters = filters_mod
    aiogram.enums = enums_mod
    aiogram.exceptions = exc_mod


# ---------------------------------------------------------------------------
# sqlalchemy (import-surface only -- repos are monkeypatched in the smoke test)
# ---------------------------------------------------------------------------
def _install_sqlalchemy() -> None:
    sa = _mod("sqlalchemy")

    def _factory(*a, **k):
        return ("col", a, k)

    for name in (
        "BigInteger", "Boolean", "DateTime", "ForeignKey", "Integer",
        "String", "Text", "UniqueConstraint",
    ):
        setattr(sa, name, _factory)

    def select(*a, **k):
        return _Query()

    def update(*a, **k):
        return _Query()

    class _Func:
        def count(self, *a, **k):
            return ("count",)

    class _Query:
        def where(self, *a, **k):
            return self

        def select_from(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def values(self, *a, **k):
            return self

    sa.select = select
    sa.update = update
    sa.func = _Func()

    orm = _mod("sqlalchemy.orm")

    class DeclarativeBase:
        metadata = types.SimpleNamespace(create_all=lambda *a, **k: None)

    class _Mapped:
        def __getitem__(self, item):
            return self

    def mapped_column(*a, **k):
        return None

    def relationship(*a, **k):
        return None

    orm.DeclarativeBase = DeclarativeBase
    orm.Mapped = _Mapped()
    orm.mapped_column = mapped_column
    orm.relationship = relationship

    ext = _mod("sqlalchemy.ext")
    aio = _mod("sqlalchemy.ext.asyncio")

    class AsyncEngine:
        pass

    class AsyncSession:
        pass

    def create_async_engine(*a, **k):
        return AsyncEngine()

    def async_sessionmaker(*a, **k):
        return lambda: AsyncSession()

    aio.AsyncEngine = AsyncEngine
    aio.AsyncSession = AsyncSession
    aio.create_async_engine = create_async_engine
    aio.async_sessionmaker = async_sessionmaker
    sa.orm = orm
    sa.ext = ext


# ---------------------------------------------------------------------------
# pydantic + pydantic_settings (minimal env-reading BaseSettings)
# ---------------------------------------------------------------------------
class _FieldInfo:
    def __init__(self, default=None, alias=None):
        self.default = default
        self.alias = alias


def _install_pydantic() -> None:
    pydantic = _mod("pydantic")

    def Field(default=None, alias=None, **k):
        return _FieldInfo(default=default, alias=alias)

    pydantic.Field = Field

    ps = _mod("pydantic_settings")

    def SettingsConfigDict(**k):
        return dict(**k)

    class BaseSettings:
        def __init__(self, **overrides):
            for klass in reversed(type(self).__mro__):
                ann = getattr(klass, "__annotations__", {})
                for attr, default in list(vars(klass).items()):
                    if not isinstance(default, _FieldInfo):
                        continue
                    alias = default.alias or attr
                    raw = os.environ.get(alias)
                    if raw is None:
                        raw = overrides.get(attr, default.default)
                    setattr(self, attr, self._coerce(ann.get(attr), raw))

        @staticmethod
        def _coerce(annotation, value):
            if value is None:
                return None
            ann = str(annotation)
            if ann == "int":
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return 0
            if ann == "bool":
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in ("1", "true", "yes", "on")
            return value

    ps.BaseSettings = BaseSettings
    ps.SettingsConfigDict = SettingsConfigDict


# ---------------------------------------------------------------------------
# httpx (import-surface only)
# ---------------------------------------------------------------------------
def _install_httpx() -> None:
    httpx = _mod("httpx")

    class _E(Exception):
        pass

    for name in ("HTTPError", "ConnectError", "ConnectTimeout", "ReadTimeout",
                 "WriteTimeout", "PoolTimeout"):
        setattr(httpx, name, type(name, (_E,), {}))

    class Timeout:
        def __init__(self, *a, **k):
            pass

    class AsyncClient:
        def __init__(self, *a, **k):
            pass

    class Response:
        pass

    httpx.Timeout = Timeout
    httpx.AsyncClient = AsyncClient
    httpx.Response = Response


# ---------------------------------------------------------------------------
# redis (import-surface only)
# ---------------------------------------------------------------------------
def _install_redis() -> None:
    redis = _mod("redis")
    redis.Redis = type("Redis", (), {})
