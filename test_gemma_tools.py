import asyncio
import unittest

import gemma_tools


class TestCreateBgTask(unittest.IsolatedAsyncioTestCase):
    """create_bg_task exists to prevent the 'Task Destruction Bug' -- tasks
    created without a strong reference can be silently garbage-collected
    mid-execution. These tests confirm the strong reference is held while the
    task is running and released once it completes."""

    async def test_task_is_tracked_while_running(self):
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        release = asyncio.Event()

        async def coro():
            started.set()
            await release.wait()

        task = gemma_tools.create_bg_task(loop, coro())
        try:
            await started.wait()
            self.assertIn(task, gemma_tools.background_tasks)
        finally:
            release.set()
            await task

    async def test_task_is_discarded_after_completion(self):
        loop = asyncio.get_running_loop()

        async def coro():
            return "done"

        task = gemma_tools.create_bg_task(loop, coro())
        await task
        # The done-callback fires via call_soon, so it may not have run
        # synchronously the instant `await task` returns -- yield once.
        await asyncio.sleep(0)
        self.assertNotIn(task, gemma_tools.background_tasks)

    async def test_returns_the_created_task(self):
        loop = asyncio.get_running_loop()

        async def coro():
            return 42

        task = gemma_tools.create_bg_task(loop, coro())
        self.assertIsInstance(task, asyncio.Task)
        self.assertEqual(await task, 42)


class TestHandleEndSession(unittest.IsolatedAsyncioTestCase):
    async def test_drains_queue_and_returns_true(self):
        queue = asyncio.Queue()
        queue.put_nowait("leftover audio chunk 1")
        queue.put_nowait("leftover audio chunk 2")

        result = await gemma_tools.handle_end_session(queue)

        self.assertTrue(result)
        self.assertTrue(queue.empty())

    async def test_returns_true_when_queue_already_empty(self):
        queue = asyncio.Queue()
        result = await gemma_tools.handle_end_session(queue)
        self.assertTrue(result)
        self.assertTrue(queue.empty())


if __name__ == "__main__":
    unittest.main()
