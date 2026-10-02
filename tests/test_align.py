"""align_lines / parse_official self-check — run: uv run python tests/test_align.py

Covers the regression from v0.1.0: weak-match fallback consuming the whole
char stream used to crash on an empty cuts list (IndexError); now the later
line degrades to words=[] with time falling back to the official value.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from lyricex_karaoke_timings.align import align_lines, norm, parse_official

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


# ---- norm ----
eq('norm strips whitespace', norm(' あ い '), 'あい')
eq('norm empty', norm(''), '')
eq('norm None', norm(None), '')

# ---- parse_official ----
LYRIC = '[00:00.00]こんにちは世界\n[00:01.00]作词: 米津玄師\n[00:02.00]編曲: 常田大希\n[02:30.00]おはようございます\n[bad]x\n'
official = parse_official(LYRIC)
eq('parse_official drops malformed line', len(official), 2)
eq('parse_official first text', official[0]['text'], 'こんにちは世界')
eq('parse_official time parse', official[1]['time'], 150.0)  # 2:30
eq('parse_official metadata filtered', official[0]['text'], 'こんにちは世界')

# ---- align_lines: main path ----
wh_words_main = [
    {'word': 'こんにちは', 'start': 0.0, 'end': 1.0},
    {'word': '世界', 'start': 1.0, 'end': 2.0},
    {'word': 'おはよう', 'start': 2.5, 'end': 3.0},
    {'word': 'ございます', 'start': 3.0, 'end': 4.0},
]
official_main = [{'time': 0.0, 'text': 'こんにちは世界'}, {'time': 2.0, 'text': 'おはようございます'}]
res_main = align_lines(official_main, wh_words_main)
eq('align main line count', len(res_main), 2)
ok('align main words concatenate to line text', all(''.join(w['text'] for w in r['words']) == r['text'] for r in res_main))
eq('align main line0 time clamped to 0', res_main[0]['time'], 0.0)
eq('align main line1 time = first word - 0.05', res_main[1]['time'], 2.45)
eq('align main full character cover', sum(len(r['text']) for r in res_main if r['words']), sum(len(r['text']) for r in res_main))

# ---- align_lines: weak-match fallback (v0.1.0 crash regression) ----
# first line has no match in the stream; fallback consumes it, leaving the
# second line (which IS in the stream) with an empty span -> must not crash
wh_words_wk = [{'word': ch, 'start': i * 0.6, 'end': (i + 1) * 0.6} for i, ch in enumerate('あいうえお')]
official_wk = [{'time': 0.0, 'text': 'かきくけこ'}, {'time': 1.5, 'text': 'あいうえお'}]
res_wk = align_lines(official_wk, wh_words_wk)
eq('align fallback line count', len(res_wk), 2)
ok('align fallback weak line projects onto words', ''.join(w['text'] for w in res_wk[0]['words']) == res_wk[0]['text'])
eq('align fallback weak line time from first word', res_wk[0]['time'], 0.0)
eq('align fallback exhausted line words empty', res_wk[1]['words'], [])
eq('align fallback exhausted line time falls back to official', res_wk[1]['time'], 1.5)
eq('align fallback cover only weak line', sum(len(r['text']) for r in res_wk if r['words']), 5)

# ---- align_lines: partially weak match stays exact ----
wh_words_pw = [
    {'word': 'こん', 'start': 0.0, 'end': 0.8},
    {'word': 'にち', 'start': 0.8, 'end': 1.6},
    {'word': 'は世界', 'start': 1.6, 'end': 3.0},
    {'word': 'さよなら', 'start': 3.2, 'end': 4.5},
]
official_pw = [{'time': 0.0, 'text': 'こんにちは世界'}, {'time': 3.0, 'text': 'さようなら'}]
res_pw = align_lines(official_pw, wh_words_pw)
ok('align partial weak lines stay text-exact', all(''.join(w['text'] for w in r['words']) == r['text'] for r in res_pw))
eq('align partial weak line2 time', res_pw[1]['time'], 3.15)

print(failures == 0 and 'ALIGN TESTS PASSED' or f'{failures} FAILURES')
sys.exit(1 if failures else 0)
