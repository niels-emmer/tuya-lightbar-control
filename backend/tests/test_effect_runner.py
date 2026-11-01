"""EffectRunner: a poisoned effect task must never take the API down.

Live incident (2026-10-24): the running effect's task became uncancellable —
it was parked in ``await asyncio.gather(<itself>)``, so ``Task.cancel()``
recursed until ``RecursionError``. ``stop()`` let that escape, so every later
``POST /api/effect`` returned 500 and the runner stayed poisoned for good.
"""

import asyncio

import effects.registry
from effect_runner import EffectRunner


def _poison(holder: dict):
    """A task whose ``cancel()`` raises RecursionError, like the live one."""

    async def poison():
        me = asyncio.current_task()
        # Awaiting a gather that contains the current task makes cancel()
        # recurse: Task.cancel -> _GatheringFuture.cancel -> Task.cancel ...
        g = asyncio.gather(me, return_exceptions=True)
        holder["gather"] = g
        await g

    return poison


def _run_isolated(coro) -> None:
    """Run a scenario, then drop the loop without draining it.

    The deliberately-uncancellable task never finishes, so ``asyncio.run()``'s
    shutdown would wait for it forever.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        for task in asyncio.all_tasks(loop):
            task._log_destroy_pending = False
        loop.close()


def test_stop_survives_an_uncancellable_task(monkeypatch):
    monkeypatch.setattr("effect_runner._STOP_TIMEOUT", 0.1)

    async def go():
        runner = EffectRunner()
        holder: dict = {}
        runner._task = asyncio.create_task(_poison(holder)())
        runner._current = {"name": "polestar", "params": {}}
        await asyncio.sleep(0.05)  # let it park inside the gather

        await runner.stop()  # must not raise

        assert runner.current is None
        assert runner._task is None
        # And a second stop is harmless rather than re-raising.
        await runner.stop()

    _run_isolated(go())


def test_activate_starts_a_new_effect_after_an_uncancellable_one(monkeypatch):
    monkeypatch.setattr("effect_runner._STOP_TIMEOUT", 0.1)

    class FakeEffect:
        name = "fake"

        def __init__(self) -> None:
            self.started = asyncio.Event()

        async def run(self, driver, brightness, params) -> None:
            self.started.set()
            await asyncio.sleep(3600)

    class FakeDriver:
        def set_power(self, on) -> bool:
            return True

    effect = FakeEffect()
    monkeypatch.setattr(effects.registry, "get_effect", lambda name: effect)

    async def go():
        runner = EffectRunner()
        holder: dict = {}
        runner._task = asyncio.create_task(_poison(holder)())
        await asyncio.sleep(0.05)

        await runner.activate(FakeDriver(), "fake", {}, 80)

        await asyncio.wait_for(effect.started.wait(), 1)
        assert runner.current == {"name": "fake", "params": {}}
        await runner.stop()

    _run_isolated(go())


def test_activate_rejects_unknown_effect_without_poisoning_the_runner(monkeypatch):
    monkeypatch.setattr(effects.registry, "get_effect", lambda name: None)

    class FakeDriver:
        def set_power(self, on) -> bool:
            return True

    async def go():
        runner = EffectRunner()
        runner._current = {"name": "polestar", "params": {}}
        try:
            await runner.activate(FakeDriver(), "nope", {}, 80)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
        # The running effect is untouched — a bad name must not stop it.
        assert runner.current == {"name": "polestar", "params": {}}

    _run_isolated(go())


def test_run_does_not_clear_a_successor_effects_state(monkeypatch):
    """An abandoned task finishing late must not wipe the new effect."""
    monkeypatch.setattr("effect_runner._STOP_TIMEOUT", 0.01)

    class SlowEffect:
        name = "slow"

        async def run(self, driver, brightness, params) -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                await asyncio.sleep(0.1)  # slow to unwind -> abandoned
                raise

    class FakeDriver:
        def set_power(self, on) -> bool:
            return True

    async def go():
        runner = EffectRunner()
        runner._current = {"name": "old", "params": {}}
        stale = asyncio.create_task(runner._run(SlowEffect(), FakeDriver(), {}, 80))
        runner._task = stale
        await asyncio.sleep(0.01)

        await runner.stop()  # times out and abandons `stale`
        assert runner.current is None

        # A new effect takes over.
        successor = {"name": "new", "params": {}}
        runner._current = successor
        runner._task = asyncio.create_task(asyncio.sleep(3600))

        await asyncio.sleep(0.2)  # `stale` finishes here

        # The abandoned task's finally block must not have cleared the new state.
        assert runner.current == successor
        runner._task.cancel()

    _run_isolated(go())
