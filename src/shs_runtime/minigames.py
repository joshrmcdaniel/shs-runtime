"""Native minigame rules, independent of rendering and wall-clock time.

Evidence and argument schemas: docs/MINIGAMES.md. Random permutations are
part of saved gameplay state, never recomputed by a renderer.
"""
from dataclasses import dataclass, field
from time import process_time_ns


RAND48_INITIAL = 0x1234ABCD330E
RAND48_MASK = (1 << 48) - 1


@dataclass
class Random48:
    """The libc lrand48 stream for word choices, separate from services 4/27."""
    state: int = RAND48_INITIAL

    def next(self):
        self.state = (self.state * 0x5DEECE66D + 0xB) & RAND48_MASK
        return self.state >> 17

    def below(self, bound):
        if bound <= 0:
            raise ValueError('Random selection needs a positive bound')
        return self.next() % bound


@dataclass
class NativeRandom:
    """0004c248 / 00126fa8 / 00122554: CPU-clock seed and 32-bit LCG.

    The returned word includes bits from the full multiplication, before
    truncating the stored state. This is not the usual ANSI rand() result.
    """
    state: int = field(default_factory=lambda: (process_time_ns() // 1000) & 0xffffffff)

    def next(self):
        product = self.state * 0x41c64e6d + 0x3039
        self.state = product & 0xffffffff
        value = (product >> 16) & 0xffffffff
        return abs(value if value < 0x80000000 else value - 0x100000000)

    def below(self, bound):
        if bound <= 0:
            raise ValueError('Random selection needs a positive bound')
        return self.next() % bound

    def signed_below(self, bound):
        value, negative = self.below(bound), self.next() & 1
        return -value if negative else value


def pipe_list(text):
    result = text.split('|')
    # The native parser preserves a blank final field, including whitespace.
    if not result[-1].strip():
        result[-1] = ''
    return result


@dataclass
class WordGame:
    good: list[str]
    bad: list[str]
    duration_ms: int
    refresh_ms: int
    remaining_ms: int
    refresh_remaining_ms: int
    options: list[str] = field(default_factory=list)
    weights: list[int] = field(default_factory=list)
    score: int = 0
    round: int = 0
    entry_ms: int = 400
    animation_ms: int = 0
    last_delta: int = 0

    def deal(self, random):
        """FUN_000af010: rejection sampling, then exactly twenty pair swaps."""
        if len(self.good) < 2 or len(self.bad) < 3:
            raise ValueError('Word game needs at least two good and three bad entries')
        first, second = random.below(len(self.good)), random.below(len(self.bad))
        third = random.below(len(self.bad))
        while third == second:
            third = random.below(len(self.bad))
        good_fourth = random.next() & 1 == 0
        pool, excluded = (self.good, (first,)) if good_fourth else (self.bad, (second, third))
        fourth = random.below(len(pool))
        while fourth in excluded:
            fourth = random.below(len(pool))
        self.options = [self.good[first], self.bad[second], self.bad[third], pool[fourth]]
        self.weights = [1, -1, -1, 1 if good_fourth else -1]
        for _ in range(20):
            a, b = random.below(4), random.below(4)
            self.options[a], self.options[b] = self.options[b], self.options[a]
            self.weights[a], self.weights[b] = self.weights[b], self.weights[a]
        self.refresh_remaining_ms = self.refresh_ms
        self.round += 1

    def pick(self, index, random):
        if type(index) is not int or not 0 <= index < 4:
            raise ValueError('Choose a word by its zero-based index (0–3)')
        if self.entry_ms:
            return False  # Native transition input gate, FUN_000afee8.
        self.last_delta = self.weights[index]
        self.score = max(0, self.score + self.last_delta)
        self.deal(random)
        self.animation_ms = 200  # New labels slide in; native input stays live.
        return True

    def tick(self, elapsed_ms):
        self.entry_ms = max(0, self.entry_ms - elapsed_ms)
        self.animation_ms = max(0, self.animation_ms - elapsed_ms)
        self.remaining_ms -= elapsed_ms
        self.refresh_remaining_ms -= elapsed_ms
        # FUN_000ae4f4 uses a strict negative comparison. The refresh counter
        # is stored/subtracted, but has no expiry action in this Android build.
        return self.duration_ms > 0 and self.remaining_ms < 0

    def validate(self):
        if (len(self.good) < 2 or len(self.bad) < 3 or self.duration_ms <= 0
                or self.duration_ms > 32767 or not -32768 <= self.refresh_ms <= 32767
                or not 0 <= self.remaining_ms <= self.duration_ms
                or not self.refresh_ms - self.duration_ms <= self.refresh_remaining_ms <= self.refresh_ms
                or len(self.options) != 4 or len(self.weights) != 4
                or sum(w == 1 for w in self.weights) not in (1, 2)
                or any(w not in (-1, 1) for w in self.weights)
                or any(s not in (self.good if w == 1 else self.bad)
                       for s, w in zip(self.options, self.weights))
                or self.round < 1 or not 0 <= self.score < self.round
                or not 0 <= self.entry_ms <= 400 or not 0 <= self.animation_ms <= 200
                or self.last_delta not in (-1, 0, 1)):
            raise ValueError('Invalid saved word game')
