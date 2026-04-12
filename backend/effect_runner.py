from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


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
            self._current = None

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._current = None
