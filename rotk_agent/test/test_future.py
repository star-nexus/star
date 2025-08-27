import asyncio

async def consumer(fut: asyncio.Future):
    print("等待结果中...")
    try:
        result = await asyncio.wait_for(fut, timeout=5)
        print("拿到结果：", result)
    except asyncio.TimeoutError:
        print("超时未拿到结果")

async def producer(fut: asyncio.Future):
    await asyncio.sleep(4)  # 模拟异步处理
    fut.set_result({"success": True, "data": 42})

async def main():
    loop = asyncio.get_running_loop()
    fut = loop.create_future()  # 创建Future占位符
    await asyncio.gather(consumer(fut), producer(fut))

asyncio.run(main())