"""serialize_segments self-check — run: uv run python tests/test_transcribe.py

Covers the word-timestamp JSON serialization that feeds wk-align:
segment objects (with .words or None) become plain dicts, text is stripped,
None word lists degrade to [].
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from lyricex_karaoke_timings.transcribe import serialize_segments  # noqa: E402

failures = 0


def eq(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f'FAIL {name}: got {got!r} want {want!r}')
    else:
        print(f'ok {name}')


def ok(name, cond):
    if not cond:
        failures += 1
        print(f'FAIL {name}')
    else:
        print(f'ok {name}')


seg0 = SimpleNamespace(id=0, start=0.0, end=1.2, text=' こんにちは ', words=[
    SimpleNamespace(word='こん', start=0.0, end=0.6),
    SimpleNamespace(word='にち', start=0.6, end=1.2),
])
seg1 = SimpleNamespace(id=1, start=2.0, end=3.0, text='せかい', words=None)
rows = serialize_segments([seg0, seg1])

eq('rows count', len(rows), 2)
eq('row0 id', rows[0]['id'], 0)
eq('row0 text stripped', rows[0]['text'], 'こんにちは')
eq('row0 start', rows[0]['start'], 0.0)
eq('row0 end', rows[0]['end'], 1.2)
eq('row0 words count', len(rows[0]['words']), 2)
eq('row0 first word text', rows[0]['words'][0]['word'], 'こん')
eq('row0 first word start', rows[0]['words'][0]['start'], 0.0)
eq('row0 second word end', rows[0]['words'][1]['end'], 1.2)
eq('row1 id', rows[1]['id'], 1)
eq('row1 words None -> empty', rows[1]['words'], [])
ok('rows are plain dicts', isinstance(rows[0], dict) and isinstance(rows[1]['words'], list))

print(failures == 0 and 'TRANSCRIBE TESTS PASSED' or f'{failures} FAILURES')
sys.exit(1 if failures else 0)
