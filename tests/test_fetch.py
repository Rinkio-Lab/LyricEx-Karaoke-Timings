"""fetch module self-check — run: uv run python tests/test_fetch.py

Pure-function assertions (URL construction, song picking, id detection).
Network calls are exercised as a manual smoke run, not pinned here (they
depend on NetEase availability).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from lyricex_karaoke_timings.fetch import is_song_id, lyric_url, pick_song, search_url  # noqa: E402

failures = 0


def eq(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f'FAIL {name}: got {got!r} want {want!r}')
    else:
        print(f'ok {name}')


def ok(name, cond):
    global failures
    if not cond:
        failures += 1
        print(f'FAIL {name}')
    else:
        print(f'ok {name}')


eq('id detection digits', is_song_id('536622304'), True)
eq('id detection mixed', is_song_id('Lemon 米津玄師'), False)

u = search_url('Lemon 米津玄師', 5)
ok('search url encoded', 'type=1&limit=5' in u and 'Lemon' in u and '%E7%B1%B3%E6%B4%A5' in u)
eq('lyric url shape', lyric_url(536622304),
   'https://music.163.com/api/song/lyric?id=536622304&lv=-1&kv=-1&tv=-1')

data = {'result': {'songs': [
    {'id': 11, 'name': 'A', 'ar': [{'name': 'X'}]},
    {'id': 22, 'name': 'B', 'ar': []},
]}}
eq('pick default', pick_song(data), (11, 'A', 'X'))
eq('pick second', pick_song(data, 2), (22, 'B', ''))
try:
    pick_song(data, 3)
    ok('pick out of range raises', False)
except ValueError:
    ok('pick out of range raises', True)
try:
    pick_song({}, 1)
    ok('empty results raises', False)
except ValueError:
    ok('empty results raises', True)

print(failures == 0 and 'FETCH TESTS PASSED' or f'{failures} FAILURES')
sys.exit(1 if failures else 0)
