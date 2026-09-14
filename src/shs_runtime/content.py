"""User-supplied game content, isolated from the distributable runtime.

The APK is opened as data only. No APK code is executed, and ZIP paths are
never extracted to the filesystem. Imported files use content-derived names.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import lzma
from pathlib import Path
import re
import shutil
import struct
import tempfile
from zipfile import BadZipFile, ZipFile

from .decode.bytecode import decode_program


PROFILE = 'shs-android-1.0.9'
NATIVE_MEMBER = 'lib/armeabi/libshs09.so'
NATIVE_SHA256 = 'b17aa4c71bc46666d414cafae6fac92bbcd755f3dcccd73975cf05f4a119665b'
MAX_PAYLOAD = 64 * 1024 * 1024


class ContentError(ValueError):
    """Missing, incompatible, or malformed user content."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_bundled(record: dict) -> bool:
    return 'apk_member' in record or record.get('builtin') == 'football-star'


def file_digest(path: Path) -> str:
    with path.open('rb') as stream:
        result = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
        return result.hexdigest()


@dataclass(frozen=True)
class Metadata:
    pack_id: int
    episode_id: int
    titles: tuple[str, ...]

    @property
    def title(self):
        return self.titles[0]


class ExpArchive:
    """Validated, exact-ID CSPUD reader; native grouped fallback is unsupported."""

    def __init__(self, data: bytes):
        self.data = data
        if len(data) < 9 or data[:5] != b'CSPUD':
            raise ContentError('Not a CSPUD EXP archive')
        count, = struct.unpack_from('>I', data, 5)
        index_end = 9 + 6 * count
        if not count or index_end > len(data):
            raise ContentError('Invalid EXP index extent')
        self.entries = {}
        extents = {}
        for i in range(count):
            resource_id, offset = struct.unpack_from('>HI', data, 9 + 6 * i)
            if resource_id in self.entries:
                raise ContentError(f'Duplicate EXP resource ID {resource_id}')
            if offset < index_end or offset + 12 > len(data):
                raise ContentError(f'Invalid record offset for resource {resource_id}')
            stored, raw, flags = struct.unpack_from('>III', data, offset)
            end = offset + 12 + stored
            if end > len(data) or raw > MAX_PAYLOAD or stored > MAX_PAYLOAD:
                raise ContentError(f'Invalid record size for resource {resource_id}')
            if flags & ~1:
                raise ContentError(f'Unsupported EXP flags 0x{flags:x}')
            if not flags & 1 and stored != raw:
                raise ContentError('Literal EXP record has conflicting sizes')
            self.entries[resource_id] = offset
            extents[offset] = end
        last_end = index_end
        for start, end in sorted(extents.items()):
            if start < last_end:
                raise ContentError('Partially overlapping EXP records')
            last_end = end

    @lru_cache(maxsize=32)
    def read(self, resource_id: int) -> bytes:
        try:
            offset = self.entries[resource_id]
        except KeyError:
            raise ContentError(f'EXP resource {resource_id} is absent; grouped lookup is unsupported') from None
        stored, raw, flags = struct.unpack_from('>III', self.data, offset)
        payload = self.data[offset + 12:offset + 12 + stored]
        if not flags & 1:
            return payload
        if len(payload) < 13:
            raise ContentError('Truncated EXP LZMA wrapper')
        prop, dictionary, size1, size2 = struct.unpack_from('<BIII', payload)
        if prop >= 225 or dictionary > MAX_PAYLOAD or size1 != raw or size2 != raw:
            raise ContentError('Inconsistent or unsupported EXP LZMA header')
        try:
            decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
            result = decoder.decompress(struct.pack('<BIQ', prop, max(4096, dictionary), raw)
                                        + payload[13:], max_length=raw + 1)
        except lzma.LZMAError as error:
            raise ContentError(f'Invalid EXP LZMA stream: {error}') from error
        if len(result) != raw:
            raise ContentError('Truncated or oversized decoded EXP payload')
        return result

    def metadata(self) -> Metadata:
        data = self.read(1)
        if len(data) < 4:
            raise ContentError('Truncated episode metadata')
        pack, episode = struct.unpack_from('>HH', data)
        pos, titles = 4, []
        try:
            for _ in range(5):
                length, = struct.unpack_from('>H', data, pos)
                pos += 2
                if pos + length > len(data):
                    raise ContentError('Truncated localized title')
                titles.append(data[pos:pos + length].decode('utf-8'))
                pos += length
        except (struct.error, UnicodeError) as error:
            raise ContentError('Invalid localized episode metadata') from error
        if pos != len(data):
            raise ContentError('Unsupported trailing episode metadata')
        return Metadata(pack, episode, tuple(titles))

    def programs(self):
        programs = {}
        for resource_id in self.entries:
            data = self.read(resource_id)
            if data.startswith(b'kiwi'):
                try:
                    programs[resource_id] = decode_program(data)
                except ValueError as error:
                    raise ContentError(f'Invalid KiWi resource {resource_id}: {error}') from error
        return programs


def _zip_read(apk: ZipFile, name: str) -> bytes:
    try:
        info = apk.getinfo(name)
        if info.file_size > MAX_PAYLOAD:
            raise ContentError(f'APK member exceeds supported size: {name}')
        return apk.read(info)
    except KeyError:
        raise ContentError(f'APK is missing {name}') from None
    except (BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ContentError(f'Cannot read APK member {name}: {error}') from error


def _inspect_apk(apk: ZipFile):
    names = apk.namelist()
    if len(names) != len(set(names)):
        raise ContentError('APK contains ambiguous duplicate member names')
    actual = digest(_zip_read(apk, NATIVE_MEMBER))
    if actual != NATIVE_SHA256:
        raise ContentError(f'Unsupported game APK native library ({actual}); '
                           'the currently supported profile is SHS Android 1.0.9')
    return actual


def _episode_inputs(paths):
    """Collect EXPs and optional native category sidecars as one import batch."""
    from .episode_catalog import EpisodeCatalog, MAX_CATALOG_BYTES, read_options_catalog
    episodes, sidecars, checked = {}, {}, set()
    for candidate in paths:
        path = Path(candidate)
        if path.is_dir():
            candidates = sorted(p for p in path.rglob('*') if p.is_file())
        elif path.is_file() and (path.suffix.lower() == '.exp' or path.name.lower() == 'shs_options.sav'):
            candidates = [path]
        else:
            raise ContentError(f'Choose an EXP file, episode folder, or shs_options.sav: {path}')
        for item in candidates:
            if item.suffix.lower() == '.exp':
                episodes[item.resolve()] = item
                parent = item.parent.resolve()
                if parent not in checked:
                    checked.add(parent)
                    for sibling in parent.glob('*'):
                        if sibling.is_file() and sibling.name.lower() == 'shs_options.sav':
                            sidecars[sibling.resolve()] = sibling
            elif item.name.lower() == 'shs_options.sav':
                sidecars[item.resolve()] = item
    catalog = EpisodeCatalog()
    for path in sidecars.values():
        with path.open('rb') as stream:
            data = stream.read(MAX_CATALOG_BYTES + 1)
        catalog = catalog.merge(read_options_catalog(data))
    return list(episodes.values()), catalog


def import_game(apk_path: Path, episode_paths: list[Path], destination: Path) -> dict:
    """Create a relocatable library atomically; keep original inputs untouched.

    A failed import leaves no partly usable library. Additional episodes are
    optional because the supplied APK itself includes playable episode data.
    """
    apk_path, destination = Path(apk_path), Path(destination)
    if destination.exists():
        raise ContentError(f'Library already exists: {destination}; choose a new directory')
    external, catalog = _episode_inputs(episode_paths)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.shs-import-', dir=destination.parent) as temporary:
        staged = Path(temporary) / 'library'
        (staged / 'content').mkdir(parents=True)
        # Validate the private copy, so source changes during import cannot
        # leave a manifest describing different bytes from those we retain.
        copied_apk = staged / 'content' / 'input.apk'
        shutil.copyfile(apk_path, copied_apk)
        apk_hash = file_digest(copied_apk)
        final_apk = copied_apk.with_name(apk_hash + '.apk')
        copied_apk.rename(final_apk)
        records = {}

        def episode_record(data, name, location):
            archive = ExpArchive(data)
            meta = archive.metadata()
            programs = archive.programs()
            if not programs:
                raise ContentError(f'No KiWi scripts in {name}')
            sha = digest(data)
            if sha not in records:
                records[sha] = dict(id=sha, sha256=sha, name=name,
                                    pack_id=meta.pack_id, episode_id=meta.episode_id,
                                    titles=list(meta.titles), scripts=sorted(programs), **location)
            return sha

        try:
            with ZipFile(final_apk) as apk:
                native_hash = _inspect_apk(apk)
                from .builtin_episode import FOOTBALL_NAME, extract_football, football_source
                built_in = extract_football(apk)
                if built_in is not None:
                    sha = digest(built_in)
                    location = dict(file=f'content/{sha}.exp', **football_source())
                    episode_record(built_in, FOOTBALL_NAME, location)
                    (staged / location['file']).write_bytes(built_in)
                for name in sorted(apk.namelist()):
                    rest = name.removeprefix('assets/Assets/')
                    if name.startswith('assets/Assets/') and '/' not in rest and rest.lower().endswith('.exp'):
                        episode_record(_zip_read(apk, name), rest, dict(apk_member=name))
        except BadZipFile as error:
            raise ContentError('The supplied APK is not a valid ZIP archive') from error
        for path in external:
            data = path.read_bytes()
            sha = digest(data)
            episode_record(data, path.name, dict(file=f'content/{sha}.exp'))
            if 'file' in records[sha]:
                (staged / records[sha]['file']).write_bytes(data)
        if not records:
            raise ContentError('No episodes found; supply episode EXP files')
        manifest = dict(format='shs-content-library', version=1, profile=PROFILE,
                        apk=dict(file=f'content/{apk_hash}.apk', sha256=apk_hash,
                                 native_sha256=native_hash), episodes=list(records.values()))
        if catalog.entries:
            manifest['episode_catalog'] = catalog.to_data()
        (staged / 'library.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        staged.rename(destination)
    return manifest


class ContentLibrary:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        try:
            self.manifest = json.loads((self.directory / 'library.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise ContentError(f'Cannot open content library: {error}') from error
        m = self.manifest
        if not isinstance(m, dict) or m.get('format') != 'shs-content-library' or m.get('version') != 1 or m.get('profile') != PROFILE:
            raise ContentError('Unsupported content library format or game profile')
        if not isinstance(m.get('apk'), dict) or not isinstance(m.get('episodes'), list) or not m['episodes']:
            raise ContentError('Invalid content library manifest')
        seen = set()
        for record in m['episodes']:
            if (not isinstance(record, dict) or not isinstance(record.get('sha256'), str)
                    or not re.fullmatch('[0-9a-f]{64}', record['sha256'])
                    or record.get('id') != record['sha256'] or record['id'] in seen
                    or not isinstance(record.get('name'), str)
                    or not isinstance(record.get('titles'), list) or len(record['titles']) != 5
                    or not all(isinstance(title, str) for title in record['titles'])
                    or any(type(record.get(key)) is not int or not 0 <= record[key] <= 65535
                           for key in ('pack_id', 'episode_id'))
                    or ('file' in record) == ('apk_member' in record)
                    or ('builtin' in record and (record['builtin'] != 'football-star' or 'file' not in record))
                    or not isinstance(record.get('aliases', []), list)
                    or not all(isinstance(alias, str) for alias in record.get('aliases', []))
                    or ('apk_member' in record and not isinstance(record['apk_member'], str))):
                raise ContentError('Invalid episode entry in content library manifest')
            seen.add(record['id'])
        from .episode_catalog import EpisodeCatalog
        self.catalog = EpisodeCatalog.from_data(m.get('episode_catalog', []))
        path = self._content_file(m['apk'], '.apk')
        try:
            self.apk = ZipFile(path)
            if _inspect_apk(self.apk) != m['apk'].get('native_sha256'):
                raise ContentError('Native profile hash does not match the library manifest')
        except (BadZipFile, ContentError) as error:
            if hasattr(self, 'apk'):
                self.apk.close()
            raise ContentError(f'Invalid imported APK: {error}') from error
        self.episodes = m['episodes']
        self.base_members = {}
        # Only native resource locations participate. UI atlas names such as
        # images/1.png are not aliases of global resource 1.
        for name in self.apk.namelist():
            relative = name.removeprefix('assets/Assets/')
            if name.startswith('assets/Assets/') and re.fullmatch(r'(0|[1-9][0-9]*)', relative):
                self.base_members[int(relative)] = name
        for name in self.apk.namelist():
            if re.fullmatch(r'assets/Assets/audio/(music/[1-9][0-9]*\.mp3|sfx/[1-9][0-9]*\.wav)', name):
                stem = Path(name).stem
                self.base_members.setdefault(int(stem), name)
        # FUN_0004b4fc appends .mp3 to these six resource names. The suffix
        # does not identify an audio stream: resource 16 is an image pack.
        for resource_id in (16, 290, 446, 496, 499, 502):
            name = f'assets/Assets/{resource_id}.mp3'
            if name in self.apk.namelist():
                self.base_members[resource_id] = name

    def _content_file(self, record: dict, suffix: str) -> Path:
        sha = record.get('sha256')
        if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha):
            raise ContentError('Invalid content hash in library')
        expected = f'content/{sha}{suffix}'
        if record.get('file') != expected:
            raise ContentError('Invalid content path in library')
        path = self.directory / expected
        try:
            actual = file_digest(path)
        except OSError as error:
            raise ContentError(f'Cannot read imported content: {error}') from error
        if actual != sha:
            raise ContentError(f'Imported content changed: {path.name}')
        return path

    def select(self, selector: str) -> dict:
        matches = [e for e in self.episodes if e['id'].startswith(selector)
                   or e['name'] == selector or e['titles'][0] == selector
                   or selector.casefold() in [alias.casefold() for alias in e.get('aliases', [])]]
        if len(matches) != 1:
            raise ContentError(f'Episode selector {selector!r} matched {len(matches)} episodes; use a unique ID from list')
        return matches[0]

    def open_episode(self, selector: str):
        record = self.select(selector)
        if 'apk_member' in record:
            data = _zip_read(self.apk, record['apk_member'])
        else:
            data = self._content_file(record, '.exp').read_bytes()
        if digest(data) != record['sha256']:
            raise ContentError('Episode content does not match its imported hash')
        return EpisodeResources(self, record, ExpArchive(data))

    def read_ui_asset(self, name: str) -> bytes:
        """Read an exact named UI asset, separately from numeric EXP resources.

        Descriptors refer to atlases by filename. Keep those references in
        their APK namespace; never resolve them against the host filesystem.
        """
        if (not isinstance(name, str)
                or not re.fullmatch(r'(fonts|images)/[A-Za-z0-9_][A-Za-z0-9_.-]*', name)):
            raise ContentError(f'Invalid named UI asset: {name!r}')
        return _zip_read(self.apk, 'assets/Assets/' + name)

    def read_asset(self, resource_id: int) -> bytes:
        """The menu reads only the APK bank, without opening an episode."""
        try:
            return _zip_read(self.apk, self.base_members[resource_id])
        except KeyError:
            raise ContentError(f'APK resource {resource_id} is missing') from None

    def add_episodes(self, paths: list[Path]) -> int:
        """Validate a batch before atomically publishing an expanded manifest.

        Content is copied under its hash; existing episodes and saves are never
        replaced. A failed validation leaves the entire library unchanged.
        """
        candidates, catalog = _episode_inputs(paths)
        if not candidates and not catalog.entries:
            raise ContentError('No EXP episodes found in the selected files or folders')
        return self._install_episodes(((path.read_bytes(), path.name, {}) for path in candidates), catalog=catalog)

    def ensure_builtin_episodes(self) -> int:
        """Upgrade an existing library using its retained APK, once per story."""
        from .builtin_episode import FOOTBALL_NAME, FOOTBALL_SOURCE, extract_football, football_source
        if any(e.get('builtin') == FOOTBALL_SOURCE for e in self.episodes):
            return 0
        data = extract_football(self.apk)
        if data is None:
            return 0
        return self._install_episodes([(data, FOOTBALL_NAME, football_source())])

    def _install_episodes(self, episodes, *, catalog=None) -> int:
        records = {e['id']: e for e in self.episodes}
        catalog = self.catalog.merge(catalog) if catalog is not None else self.catalog
        with tempfile.TemporaryDirectory(prefix='.shs-import-', dir=self.directory) as temporary:
            stage = Path(temporary)
            additions = []
            for data, name, source in episodes:
                sha = digest(data)
                if sha in records:
                    continue
                archive = ExpArchive(data)
                meta, programs = archive.metadata(), archive.programs()
                if not programs:
                    raise ContentError(f'No KiWi scripts in {name}')
                record = dict(id=sha, sha256=sha, name=name, pack_id=meta.pack_id,
                              episode_id=meta.episode_id, titles=list(meta.titles),
                              scripts=sorted(programs), file=f'content/{sha}.exp', **source)
                (stage / (sha + '.exp')).write_bytes(data)
                records[sha] = record
                additions.append(record)
            if not additions and catalog.entries == self.catalog.entries:
                return 0
            # Refuse to lose additions made by another importer since we opened.
            current = json.loads((self.directory / 'library.json').read_text(encoding='utf-8'))
            if current != self.manifest:
                raise ContentError('The library changed during import; reopen it and try again')
            updated = dict(self.manifest, episodes=list(records.values()))
            if catalog.entries:
                updated['episode_catalog'] = catalog.to_data()
            manifest_path = stage / 'library.json'
            manifest_path.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            for record in additions:
                (stage / (record['id'] + '.exp')).replace(self.directory / record['file'])
            manifest_path.replace(self.directory / 'library.json')
            self.manifest, self.episodes = updated, updated['episodes']
            self.catalog = catalog
            return len(additions)

    def close(self):
        self.apk.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class EpisodeResources:
    def __init__(self, library: ContentLibrary, record: dict, archive: ExpArchive):
        self.library, self.record, self.archive = library, record, archive
        self.programs = archive.programs()

    @property
    def identity(self):
        return dict(profile=PROFILE, apk_sha256=self.library.manifest['apk']['sha256'],
                    episode_sha256=self.record['sha256'])

    def exists(self, resource_id: int) -> bool:
        # FUN_00082bc0 selects the episode bank at 26000 for art resources.
        return resource_id in (self.archive.entries if resource_id >= 26000
                               else self.library.base_members)

    def read_asset(self, resource_id: int) -> bytes:
        if resource_id >= 26000:
            return self.archive.read(resource_id)
        return self.library.read_asset(resource_id)

    def program(self, resource_id: int):
        if resource_id not in self.programs:
            # Engine script loading and image-bank selection are different
            # paths: episode scripts in the 25000 range take precedence here.
            try:
                self.programs[resource_id] = decode_program(self.read_asset(resource_id))
            except ValueError as error:
                raise ContentError(f'Cannot load script {resource_id}: {error}') from error
        return self.programs[resource_id]

    @lru_cache(maxsize=1)
    def dialogue_layout(self):
        from .dialogue import DialogueLayout
        return DialogueLayout(self)
