import asyncio

# Глобальные объекты
ALL_CHATS_DATA = {}
lock = asyncio.Lock()
characters_lock = asyncio.Lock()

