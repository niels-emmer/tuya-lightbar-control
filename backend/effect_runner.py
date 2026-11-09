from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# A healthy effect stops within a couple of device writes. A task still running
# after this long is abandoned, so one stuck effect cannot wedge the API.
_STOP_TIMEOUT = 5.0


class EffectRunner:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._current: Optional[dict] = None

    @property
    def current(self) -> Optional[dict]:
        return self._current

    async def activate(self, driver, name: str, params: dict, brightness: int) -> None:
        from effects.registry import get_effect

        effect = get_effect(name)
        if effect is None:
            raise ValueError(f"Unknown effect: {name!r}")

        await self.stop()
        # set_power blocks on the device socket — keep it off the event loop.
        await asyncio.to_thread(driver.set_power, True)
        self._current = {"name": name, "params": params}
        self._task = asyncio.create_task(self._run(effect, driver, params, brightness))

    async def _run(self, effect, driver, params, brightness):
        try:
            await effect.run(driver, brightness, params)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Effect {effect.name} crashed: {e}", exc_info=True)
        finally:
            # Only clear state this task still owns. An abandoned task that
            # finishes late must not wipe the effect that replaced it.
            if self._task is asyncio.current_task():
                self._current = None

    async def stop(self) -> None:
        """Cancel the running effect. Never raises, never hangs.

        A task can become uncancellable — e.g. one parked in
        ``await asyncio.gather(<itself>)``, where ``Task.cancel()`` recurses
        until ``RecursionError``. Letting that escape used to leave the runner
        permanently poisoned, so every later ``POST /api/effect`` returned 500.
        """
        task, self._task = self._task, None
        self._current = None
        if task is None or task.done():
            return

        try:
            task.cancel()
        except BaseException:
            logger.exception("Effect task could not be cancelled; abandoning it")
            return

        # Bounded wait, and asyncio.wait never cancels the task on timeout.
        done, _ = await asyncio.wait({task}, timeout=_STOP_TIMEOUT)
        if not done:
            logger.warning(
                f"Effect task still running after {_STOP_TIMEOUT}s; abandoning it"
            )
