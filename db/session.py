from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from configs import PG_DSN
class AsyncDatabaseSession:
    def __init__(self):  
        self._engine = create_async_engine(PG_DSN)
        self._session = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    def __call__(self):
        return self._session()

    def __getattr__(self, name):
        return getattr(self._session, name)

    async def close(self):
        await self._engine.dispose()


async_db_session = AsyncDatabaseSession()

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_db_session() as session:
        yield session
        await session.commit()