"""Service 91's application overlay and host execution gate.

FUN_0008e7d0 accumulates active milliseconds; FUN_0009ea70 clears the
overlay only once the counter is strictly greater than 3000.
"""
from dataclasses import dataclass

from .vm import VMError


@dataclass
class LoadingScreen:
    blocking: bool
    elapsed_ms: int = 0

    def tick(self, elapsed_ms: int) -> bool:
        self.elapsed_ms = min(3001, self.elapsed_ms + elapsed_ms)
        return self.elapsed_ms > 3000

    @property
    def frame(self):
        # FUN_0008952c: five common-pack frames, 500 ms each, repeated.
        return 23 + (self.elapsed_ms // 500) % 5

    def validate(self):
        if type(self.blocking) is not bool or type(self.elapsed_ms) is not int or not 0 <= self.elapsed_ms <= 3000:
            raise VMError('Invalid loading-screen state')
