from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from app.core.config import settings
def normalise_database_url(url: str) -> tuple[str, dict]:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    connect_args: dict = {}
    if url.startswith("postgresql+asyncpg://"):
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        sslmode = query.pop("sslmode", None)
        query.pop("channel_binding", None)
        if sslmode and sslmode != "disable":
            connect_args["ssl"] = True
        url = urlunsplit(parts._replace(query=urlencode(query)))
    return url, connect_args
_url, _connect_args = normalise_database_url(settings.DATABASE_URL)
engine = create_async_engine(
    _url,
    echo=settings.DEBUG,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=not _url.startswith("sqlite"),
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
class Base(DeclarativeBase):
    pass
def add_missing_columns(sync_conn) -> list[str]:
    from sqlalchemy import inspect
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())
    added = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            col_type = col.type.compile(dialect=sync_conn.dialect)
            sync_conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}')
            added.append(f"{table.name}.{col.name}")
    return added
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
