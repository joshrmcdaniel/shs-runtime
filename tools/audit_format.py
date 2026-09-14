"""Audit the EXP specification against local archives; never modify inputs.

Run: python tools/audit_format.py Episodes extract/assets/Assets
Requires only the standard library. JSON goes to stdout; failures exit nonzero.
Counts are per logical index entry unless explicitly called physical records.
"""
import collections
import hashlib
import json
import lzma
from pathlib import Path
import struct
import sys


def unpack(fmt, data, offset):
    if offset < 0 or offset + struct.calcsize(fmt) > len(data):
        raise ValueError(f'truncated {fmt} at byte {offset}')
    return struct.unpack_from(fmt, data, offset)


def metadata(data):
    pack, episode = unpack('>HH', data, 0)
    pos, titles = 4, []
    for _ in range(5):
        length, = unpack('>H', data, pos)
        pos += 2
        if pos + length > len(data):
            raise ValueError('truncated localized title')
        text = data[pos:pos + length]
        if b'\0' in text:
            raise ValueError('NUL in localized title')
        titles.append(text.decode('utf-8'))
        pos += length
    if pos != len(data):
        raise ValueError('metadata does not end after five titles')
    return dict(pack_id=pack, episode_id=episode, titles=titles)


def audit(paths):
    counts = collections.Counter()
    flags, properties, types = (collections.Counter() for _ in range(3))
    aliases, tails, issues, manifest, metadata_examples, opaque_examples = [], [], [], [], [], []
    for path in paths:
        data = path.read_bytes()
        manifest.append(dict(path=str(path), bytes=len(data),
                             sha256=hashlib.sha256(data).hexdigest()))
        counts['archives'] += 1
        counts['archive_bytes'] += len(data)
        try:
            if data[:5] != b'CSPUD':
                raise ValueError('invalid magic')
            n, = unpack('>I', data, 5)
            index_end = 9 + 6 * n
            if index_end > len(data):
                raise ValueError('truncated index')
            entries = [unpack('>HI', data, 9 + 6 * i) for i in range(n)]
            ids = [fid for fid, _ in entries]
            counts['ids_sorted'] += ids == sorted(ids)
            counts['ids_unique'] += len(ids) == len(set(ids))
            counts['first_id_is_one'] += bool(ids) and ids[0] == 1
            records = collections.defaultdict(list)
            for fid, offset in entries:
                records[offset].append(fid)
            counts['logical_entries'] += n
            counts['physical_records'] += len(records)
            counts['alias_entries'] += n - len(records)
            previous_end = index_end
            for offset, fids in sorted(records.items()):
                if offset != previous_end:
                    raise ValueError(f'records not contiguous at {offset}, expected {previous_end}')
                stored, raw_size, flag = unpack('>III', data, offset)
                end = offset + 12 + stored
                if end > len(data):
                    raise ValueError(f'truncated payload at {offset}')
                previous_end = end
                payload = data[offset + 12:end]
                weight = len(fids)
                flags[str(flag)] += weight
                if weight > 1:
                    counts['aliased_records'] += 1
                    if len(aliases) < 12:
                        aliases.append(dict(path=str(path), offset=offset, ids=fids))
                if flag & 1:
                    if len(payload) < 13:
                        raise ValueError('truncated LZMA wrapper')
                    prop, dictionary, size1, size2 = unpack('<BIII', payload, 0)
                    properties[payload[:5].hex()] += weight
                    if size1 != raw_size or size2 != raw_size:
                        raise ValueError('inner/outer decoded sizes disagree')
                    if prop >= 225:
                        raise ValueError('invalid LZMA properties')
                    body = payload[13:]
                    decoded = lzma.decompress(struct.pack('<BIQ', prop, dictionary, raw_size)
                                              + body, format=lzma.FORMAT_ALONE)
                    legacy_dictionary = int.from_bytes(payload[1:5], 'big')
                    legacy = lzma.decompress(struct.pack('<BIQ', prop, legacy_dictionary, raw_size)
                                             + body, format=lzma.FORMAT_ALONE)
                    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[dict(
                        id=lzma.FILTER_LZMA1, dict_size=max(4096, dictionary),
                        lc=prop % 9, lp=(prop // 9) % 5, pb=prop // 45)])
                    bounded = decoder.decompress(body, max_length=raw_size)
                    if decoded != legacy or decoded != bounded:
                        raise ValueError('LZMA decoding strategies disagree')
                    counts['compressed_entries'] += weight
                    counts['compressed_smaller_than_raw'] += weight * (stored < raw_size)
                    counts['inner_sizes_match_outer'] += weight
                    counts['little_endian_matches_legacy'] += weight
                    counts['bounded_raw_matches_alone'] += weight
                    counts['raw_eof_at_output_size'] += weight * decoder.eof
                else:
                    decoded = payload
                    counts['uncompressed_entries'] += weight
                if len(decoded) != raw_size:
                    raise ValueError(f'decoded size {len(decoded)} != {raw_size}')
                counts['decoded_bytes'] += len(decoded) * weight
                if 1 in fids:
                    meta = metadata(decoded)
                    counts['metadata_with_five_utf8_titles'] += 1
                    counts['localized_titles'] += 5
                    if len(set(meta['titles'])) > 1 and len(metadata_examples) < 5:
                        metadata_examples.append(dict(path=str(path), **meta))
                    kind = 'episode_metadata'
                elif decoded.startswith(b'\x89PNG\r\n\x1a\n'):
                    kind = 'png'
                elif decoded.startswith(b'\xff\xd8'):
                    kind = 'jpeg'
                elif decoded.startswith(b'kiwi'):
                    kind = 'kiwi'
                    version = decoded[4]
                    counts[f'kiwi_version_{version}'] += weight
                    counts['kiwi_previous_flag_nonzero'] += weight * (decoded[5] != 0)
                    pos = 6 + (4 if decoded[5] else 0)
                    counts[f'kiwi_reserved_flag_{decoded[pos]}'] += weight
                elif decoded.startswith(b'RIFF') and decoded[8:12] == b'WAVE':
                    kind = 'riff_wave'
                elif decoded.startswith(b'ID3'):
                    kind = 'id3_tagged_audio'
                elif len(decoded) >= 2 and decoded[0] == 0xFF and decoded[1] & 0xE0 == 0xE0:
                    kind = 'mpeg_audio_candidate'
                else:
                    kind = 'other'
                    if len(opaque_examples) < 10:
                        opaque_examples.append(dict(path=str(path), ids=fids,
                                                    prefix=decoded[:32].hex()))
                types[kind] += weight
            if previous_end < len(data):
                tail = data[previous_end:]
                tails.append(dict(path=str(path), offset=previous_end, bytes=len(tail),
                                  all_zero=not any(tail)))
        except (ValueError, IndexError, struct.error, lzma.LZMAError) as error:
            issues.append(dict(path=str(path), error=str(error)))
    return dict(scope='local Surviving High School EXP corpus; counts include duplicate archives',
                counts=dict(sorted(counts.items())), flags=dict(sorted(flags.items())),
                lzma_properties=dict(properties), payload_types=dict(types),
                alias_examples=aliases, trailing_data=tails, metadata_examples=metadata_examples,
                opaque_examples=opaque_examples, issues=issues, manifest=manifest)


if __name__ == '__main__':
    paths = []
    for root in sys.argv[1:] or ['Episodes', 'extract/assets/Assets']:
        path = Path(root)
        paths.extend(sorted(path.rglob('*.exp')) if path.is_dir() else [path])
    report = audit(paths)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(bool(report['issues']))
