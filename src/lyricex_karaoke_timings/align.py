"""LyricEx karaoke toolkit - align faster-whisper word timestamps to official
NetEase lyric lines, producing per-line word-level karaoke timing.

Timing comes from real audio transcription (faster-whisper); word text is
re-projected onto the official line characters by time proportion, so the
concatenated word texts always equal the official line text exactly.

Usage:
    wk-align <whisper.json> <netease-raw.json> <out.json>

    whisper.json     output of wk-transcribe (word timestamps)
    netease-raw.json NetEase song/lyric JSON (lrc.lyric official lines)
    out.json         [{ lineIndex, time, text, words:[{text,start,end}] }]

Output lines: official lines minus metadata (作词/作曲/编曲/制作/作詞/编曲),
each with time = first word start - 0.05s so line scrolling matches karaoke.

Core logic lives in align_lines() / parse_official() (testable pure-ish
functions); main() only does IO. Run: uv run python tests/test_align.py
"""
import json
import re
import sys

from difflib import SequenceMatcher

_LINE_RE = re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)')
# 元数据行无演唱；前缀覆盖冒号写法（作词 → 作词:），含简体/繁体/日文汉字
_META_PREFIXES = ('作词', '作曲', '编曲', '制作', '作詞', '編曲')
# 词级时间输出精度（秒）；行首提前量：首词 start - _LINE_LEAD，保证行滚动与卡拉OK逐字高亮同步
_TIME_PRECISION = 3
_LINE_LEAD = 0.05
# 行匹配弱于该比例（且不足该字符数）时按等长顺序消费兜底——经验值，见 README「已知限制」
_WEAK_MATCH_RATIO = 0.5
_MIN_MATCH_CHARS = 3
# 时间窗对齐：每行按官方 time 在词流开窗独立定位（窗=行区间±缓冲），
# 重复副歌各行落到各自音频段，不受前序行消费漂移影响；失败才回退顺序消费
_WINDOW_LOOKBACK = 0.5
_WINDOW_LOOKAHEAD = 2.0


def norm(s):
    return re.sub(r'\s+', '', s or '')


def parse_official(lyric_text):
    """lrc.lyric 文本 → [{time, text}]，跳过时间戳格式错的行与元数据行。"""
    official = []
    for line in lyric_text.splitlines():
        m = _LINE_RE.match(line.strip())
        if not m:
            continue
        text = norm(m.group(3))
        if not text or text.startswith(_META_PREFIXES):
            continue
        secs = int(m.group(1)) * 60 + float(m.group(2))
        official.append({'time': secs, 'text': text})
    return official


def _project_words(lt, wh_words, w_lo, w_hi):
    """官方行字符按时间比例投影到 whisper 词 [w_lo, w_hi] → (words, line_time)。

    words 拼接恒等于 lt；line_time = 首词 start - _LINE_LEAD，无词时 None。
    """
    base = []
    for wi in range(w_lo, w_hi + 1):
        w = wh_words[wi]
        base.append({'start': round(w['start'], _TIME_PRECISION), 'end': round(w['end'], _TIME_PRECISION)})
    words = []
    line_time = None
    if base:
        # project official line chars onto word spans by time proportion
        total = max(0.001, sum(b['end'] - b['start'] for b in base))
        cum = 0.0
        cuts = []
        for b in base:
            cum += (b['end'] - b['start']) / total
            cuts.append(int(round(cum * len(lt))))
        cuts[-1] = len(lt)
        s = 0
        for j, b in enumerate(base):
            e = cuts[j]
            seg = lt[s:e]
            s = e
            if seg:
                words.append({'text': seg, 'start': b['start'], 'end': b['end']})
        line_time = words[0]['start'] - _LINE_LEAD if words else None
    return words, line_time


def align_lines(official, wh_words):
    """官方行 × whisper 词 → 逐行 words；拼接文本恒等于官方行文本。

    每行优先在官方 time 的时间窗内独立匹配（见 _WINDOW_* 注释），
    窗口匹配弱于阈值时回退顺序消费（v0.1.0 行为），保证输出不退化。
    覆盖比例由调用方从 result 推导（有 words 的行字符 / 官方总字符）。
    """
    chars = []
    for wi, w in enumerate(wh_words):
        for ch in w['word']:
            if not ch.isspace():
                chars.append((ch, wi))
    char_stream = ''.join(c for c, _ in chars)
    word_of_char = [wi for _, wi in chars]
    # 词 wi 在全流中的字符区间 [start, end)，供窗口匹配成功后推进 pos
    word_char_range = {}
    cpos = 0
    for wi, w in enumerate(wh_words):
        n = sum(1 for ch in w['word'] if not ch.isspace())
        if n:
            word_char_range[wi] = (cpos, cpos + n)
            cpos += n

    result = []
    pos = 0
    for idx, line in enumerate(official):
        lt = line['text']
        t = line['time']
        next_t = official[idx + 1]['time'] if idx + 1 < len(official) else (
            wh_words[-1]['end'] + _WINDOW_LOOKAHEAD if wh_words else t + 4.0)

        words = []
        line_time = t
        # 时间窗优先：窗口内词的字符流匹配，成功则独立定位、不推进 pos
        win_idx = [wi for wi, w in enumerate(wh_words)
                   if t - _WINDOW_LOOKBACK <= w['start'] < next_t + _WINDOW_LOOKAHEAD]
        win_chars = []
        win_of_char = []
        for wi in win_idx:
            w = wh_words[wi]
            for ch in w['word']:
                if not ch.isspace():
                    win_chars.append((ch, wi))
                    win_of_char.append(wi)
        win_stream = ''.join(c for c, _ in win_chars)
        matched = False
        if win_stream:
            block = SequenceMatcher(None, lt, win_stream, autojunk=False).find_longest_match(
                0, len(lt), 0, len(win_stream))
            if block.size >= max(_MIN_MATCH_CHARS, int(len(lt) * _WEAK_MATCH_RATIO)):
                start_c = block.b
                end_c = start_c + block.size
                w_lo = win_of_char[start_c]
                w_hi = win_of_char[min(end_c - 1, len(win_of_char) - 1)]
                words, line_time = _project_words(lt, wh_words, w_lo, w_hi)
                # 同步推进 pos：后续回退行以本行消费的词区间为基准，
                # 否则回退等长消费会从歌头开始错位（实测 -151.93s 异常）
                if w_hi in word_char_range:
                    pos = word_char_range[w_hi][1]
                matched = True

        if not matched:
            # 回退顺序消费：弱匹配行按等长推进 pos；pos 推到流尾时 base 为空，
            # 此时 words=[]、time=官方 time（整首歌输出不因此丢失）
            sm = SequenceMatcher(None, lt, char_stream[pos:], autojunk=False)
            block = sm.find_longest_match(0, len(lt), 0, len(char_stream) - pos)
            size = block.size
            if size < max(_MIN_MATCH_CHARS, int(len(lt) * _WEAK_MATCH_RATIO)):
                start_c = pos
                end_c = min(pos + len(lt), len(char_stream))
            else:
                start_c = pos + block.b
                end_c = start_c + size

            w_lo = word_of_char[start_c] if start_c < len(word_of_char) else len(wh_words)
            w_hi = word_of_char[min(end_c - 1, len(word_of_char) - 1)] if end_c > 0 and end_c - 1 < len(word_of_char) else w_lo
            words, projected_time = _project_words(lt, wh_words, w_lo, w_hi)
            if projected_time is not None:  # base 为空（流耗尽）时保留官方 time，见下方 result.append
                line_time = projected_time
            pos = end_c

        result.append({'lineIndex': idx, 'time': round(max(0, line_time), _TIME_PRECISION), 'text': lt, 'words': words})
    return result


def main():
    if len(sys.argv) != 4:
        sys.exit('usage: wk-align <whisper.json> <netease-raw.json> <out.json>')
    wh_path, ne_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        with open(wh_path, encoding='utf-8-sig') as f:  # utf-8-sig: tolerate BOM from manual saves
            wh = json.load(f)
    except OSError as e:
        sys.exit(f'error: cannot read {wh_path}: {e}')
    except json.JSONDecodeError as e:
        sys.exit(f'error: {wh_path} is not valid JSON: {e}')
    try:
        segments = wh['segments']
    except (KeyError, TypeError):
        sys.exit('error: whisper.json missing "segments"')
    wh_words = [w for seg in segments for w in seg['words']]

    try:
        with open(ne_path, encoding='utf-8-sig') as f:  # utf-8-sig: tolerate BOM from manual saves
            ne = json.load(f)
    except OSError as e:
        sys.exit(f'error: cannot read {ne_path}: {e}')
    except json.JSONDecodeError as e:
        sys.exit(f'error: {ne_path} is not valid JSON: {e}')
    try:
        lyric = ne['lrc']['lyric']
    except (KeyError, TypeError):
        sys.exit('error: netease-raw.json missing "lrc.lyric"')
    official = parse_official(lyric)

    result = align_lines(official, wh_words)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    # 覆盖口径：官方行文本中被 words 覆盖的字符比例（非字符流消费比例）
    exact = sum(1 for r in result if ''.join(w['text'] for w in r['words']) == r['text'])
    total_chars = sum(len(r['text']) for r in result)
    covered_chars = sum(len(r['text']) for r in result if r['words'])
    print(f'lines={len(result)} words_total={sum(len(r["words"]) for r in result)} '
          f'lines_with_exact_text={exact}/{len(result)} chars_covered={covered_chars}/{total_chars}')


if __name__ == '__main__':
    main()
