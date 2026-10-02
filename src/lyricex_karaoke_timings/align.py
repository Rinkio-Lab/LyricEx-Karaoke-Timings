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


def align_lines(official, wh_words):
    """官方行 × whisper 词 → 逐行 words；拼接文本恒等于官方行文本。

    覆盖比例由调用方从 result 推导（有 words 的行字符 / 官方总字符）。
    """
    chars = []
    for wi, w in enumerate(wh_words):
        for ch in w['word']:
            if not ch.isspace():
                chars.append((ch, wi))
    char_stream = ''.join(c for c, _ in chars)
    word_of_char = [wi for _, wi in chars]

    result = []
    pos = 0
    for idx, line in enumerate(official):
        lt = line['text']
        sm = SequenceMatcher(None, lt, char_stream[pos:], autojunk=False)
        block = sm.find_longest_match(0, len(lt), 0, len(char_stream) - pos)
        size = block.size
        if size < max(3, int(len(lt) * 0.5)):
            start_c = pos
            end_c = min(pos + len(lt), len(char_stream))
        else:
            start_c = pos + block.b
            end_c = start_c + size

        w_lo = word_of_char[start_c] if start_c < len(word_of_char) else len(wh_words)
        w_hi = word_of_char[min(end_c - 1, len(word_of_char) - 1)] if end_c > 0 and end_c - 1 < len(word_of_char) else w_lo
        base = []
        for wi in range(w_lo, w_hi + 1):
            w = wh_words[wi]
            base.append({'start': round(w['start'], 3), 'end': round(w['end'], 3)})

        # 兜底消费把 pos 推到流尾时，后续行的 base 为空——此时不能投影，
        # 否则 cuts[-1] 在空列表上 IndexError；整首歌的输出会全部丢失。
        words = []
        line_time = line['time']
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
            line_time = words[0]['start'] - 0.05 if words else line['time']

        result.append({'lineIndex': idx, 'time': round(max(0, line_time), 3), 'text': lt, 'words': words})
        pos = end_c
    return result


def main():
    wh_path, ne_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(wh_path, encoding='utf-8') as f:
        wh = json.load(f)
    wh_words = [w for seg in wh['segments'] for w in seg['words']]

    with open(ne_path, encoding='utf-8') as f:
        ne = json.load(f)
    official = parse_official(ne['lrc']['lyric'])

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
