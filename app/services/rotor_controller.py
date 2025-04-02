import asyncio

class RotorController:
    reader = None
    writer = None

    @classmethod
    async def initialize(cls):
        if cls.reader is None:
            cls.reader, cls.writer = await asyncio.open_connection("192.168.4.1", 4533)
        return cls

    @classmethod
    async def read(cls):
        cls.writer.write("p".encode())
        await cls.writer.drain()
        response = await cls.reader.read(64)
        response = response.decode()
        response = response.splitlines()
        az = response[0]
        el = response[1]
        return az, el


    @classmethod
    async def write(cls, az, el):
        cls.writer.write(f"P {az} {el}".encode())
        await cls.writer.drain()
        response = await cls.reader.read(64)