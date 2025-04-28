from .models import Group, Post, GeneratedSeries, GeneratedPost
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def add_group(session: AsyncSession, chat_id: int, title: str, added_by: int):
    group = Group(chat_id=chat_id, title=title, added_by=added_by)
    session.add(group)
    await session.commit()

async def get_groups(session: AsyncSession):
    result = await session.execute(select(Group))
    return result.scalars().all()