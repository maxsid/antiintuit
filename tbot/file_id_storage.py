from aiogram.contrib.fsm_storage.redis import RedisStorage2

from tbot.arguments import config

__all__ = [
    "file_id_storage"
]


class FileIdStorage(RedisStorage2):
    def __init__(self, host: str = None, port=None, db=4, prefix='tbot_photo_id', **kwargs):
        host = host or config.redis_host
        port = port or config.redis_port
        super().__init__(host, port, db, prefix=prefix, **kwargs)

    async def get_file_id(self, file_key: str) -> str or None:
        if file_key is None:
            raise ValueError("The Parameter is None")
        key = self.generate_key(file_key)
        redis = await self.redis()
        return await redis.get(key, encoding='utf8') or None

    async def set_file_id(self, file_key: str, file_id: str):
        if file_key is None or file_id is None:
            raise ValueError("The Parameters are None")
        key = self.generate_key(file_key)
        redis = await self.redis()
        await redis.set(key, file_id, expire=self._state_ttl)

    async def delete_file_id(self, file_key: str):
        if file_key is None:
            raise ValueError("The Parameter is None")
        key = self.generate_key(file_key)
        redis = await self.redis()
        await redis.delete(key)


file_id_storage = FileIdStorage()
