"""Original episode categories retained in user-supplied shs_options.sav files.

FUN_00092734 / FUN_000980e4 read the catalog; FUN_00078910 uses its
category strings as section headers. No original catalog ships with the app.
"""
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
import struct

from .content import ContentError


MAX_ENTRIES = 4096
MAX_CATALOG_BYTES = 4 * 1024 * 1024


def basename(filename):
    # Catalog filenames identify records only. Never open their paths.
    return PurePosixPath(filename.replace('\\', '/')).name.casefold()


@dataclass(frozen=True)
class CatalogEntry:
    pack_id: int
    episode_id: int
    title: str
    category: str
    filename: str

    @property
    def key(self):
        return self.pack_id, self.episode_id, self.title, basename(self.filename)

    def validate(self):
        if (any(type(value) is not int or not 0 <= value <= 65535
                for value in (self.pack_id, self.episode_id))
                or any(not isinstance(value, str) or len(value) > 32767 or '\0' in value
                       for value in (self.title, self.category, self.filename))):
            raise ContentError('Invalid episode catalog entry')


class EpisodeCatalog:
    def __init__(self, entries=()):
        unique = {}
        for entry in entries:
            entry.validate()
            unique[entry.key] = entry
        if len(unique) > MAX_ENTRIES:
            raise ContentError('Episode catalog contains too many entries')
        self.entries = tuple(unique.values())
        self.by_filename, self.by_title = {}, {}
        for entry in self.entries:
            if entry.filename:
                self.by_filename.setdefault(basename(entry.filename), []).append(entry)
            key = entry.pack_id, entry.episode_id, entry.title
            self.by_title.setdefault(key, []).append(entry)

    def merge(self, other):
        return EpisodeCatalog((*self.entries, *other.entries))

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, list) or len(data) > MAX_ENTRIES:
            raise ContentError('Invalid episode catalog in library')
        try:
            return cls(CatalogEntry(**entry) for entry in data)
        except (TypeError, AttributeError) as error:
            raise ContentError('Invalid episode catalog in library') from error

    def to_data(self):
        return [asdict(entry) for entry in self.entries]

    def category(self, record):
        candidates = self.by_filename.get(basename(record['name']), ())
        if candidates:
            # A catalog filename can recur in different downloads. Prefer the
            # matching title; filenames still handle native synthetic IDs for
            # the bundled Season 1 and novel entries.
            candidates = [e for e in candidates if e.title == record['titles'][0]] or candidates
        else:
            candidates = self.by_title.get((record['pack_id'], record['episode_id'], record['titles'][0]), ())
        categories = {e.category for e in candidates if e.category.strip()}
        return next(iter(categories)) if len(categories) == 1 else None


class _Reader:
    def __init__(self, data, position):
        self.data, self.position = data, position

    def take(self, count):
        end = self.position + count
        if count < 0 or end > len(self.data):
            raise ContentError('Truncated native episode catalog')
        value = self.data[self.position:end]
        self.position = end
        return value

    def integer(self, format):
        return struct.unpack(format, self.take(struct.calcsize(format)))[0]

    def boolean(self):
        value = self.integer('B')
        if value not in (0, 1):
            raise ContentError('Invalid native catalog presence flag')
        return bool(value)

    def string(self):
        raw = self.take(self.integer('>H'))
        if len(raw) > 32767 or b'\0' in raw:
            raise ContentError('Invalid native catalog string')
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            # Legacy saves contain byte characters in some translated titles.
            # EXP resource 1 remains strictly UTF-8; this is a different format.
            return raw.decode('latin-1')

    def entry(self):
        if not self.boolean():
            return None
        pack, episode = self.integer('>H'), self.integer('>H')
        titles = [self.string() for _ in range(5)]
        categories = [self.string() for _ in range(5)]
        filename = self.string()
        self.integer('>i')  # Native download identifier, not a content hash.
        return CatalogEntry(pack, episode, titles[0], categories[0], basename(filename))


def read_options_catalog(data):
    """Read categories only; never import native preferences or saved progress.

    The inspected Android reader has a 36-byte prefix. The supplied legacy
    version-18 file has a 32-byte prefix. Both must validate through the end
    of the string-pair table and versioned flags; no arbitrary byte scanning.
    """
    if len(data) > MAX_CATALOG_BYTES or len(data) < 32 or data[:12] != b'SHS_OPTIONS\0':
        raise ContentError('Not a supported shs_options.sav catalog')
    version = struct.unpack_from('>i', data, 12)[0]
    if version not in (16, 17, 18):
        raise ContentError(f'Unsupported native options version: {version}')
    results = []
    for prefix in (32, 36):
        try:
            r = _Reader(data, prefix)
            current = r.entry()
            count = r.integer('>i')
            if not 0 <= count <= MAX_ENTRIES:
                raise ContentError('Invalid native catalog entry count')
            entries = [r.entry() for _ in range(count)]
            pairs = r.integer('>h')
            if not 0 <= pairs <= MAX_ENTRIES:
                raise ContentError('Invalid native string-pair count')
            for _ in range(pairs * 2):
                r.string()  # Discard native runtime/user strings.
            for _ in range(version - 16):
                r.boolean()
            if r.position != len(data):
                raise ContentError('Unsupported trailing native options data')
            results.append(EpisodeCatalog(e for e in [current, *entries] if e is not None))
        except ContentError:
            continue
    if len(results) != 1:
        raise ContentError('Invalid or ambiguous native episode catalog')
    return results[0]
