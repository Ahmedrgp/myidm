import asyncio

ACTIVE_TASKS = {}
request_queue = asyncio.Queue()
