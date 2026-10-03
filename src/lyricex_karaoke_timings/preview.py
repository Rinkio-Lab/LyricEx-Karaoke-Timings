"""LyricEx karaoke toolkit - word-timing visual proofreading.

Renders words.json (wk-align output) into a self-contained HTML page: per-line
word-span bars proportional to (end-start)/duration, click-to-seek playback,
and live highlight of the word currently sung. Open the HTML in a browser
next to the audio file to proofread timings visually.

Usage:
    wk-preview <words.json> <audio.mp3> <out.html>   # with playback
    wk-preview <words.json> <out.html>               # bars only, no audio
"""
import json
import sys

_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · 词级时间校对</title>
<style>
  :root {{
    --ink: #22252a; --mut: #8a919c; --line: #e3e6ea; --bg: #f7f8fa;
    --bar: #4a7bd8; --bar-hi: #ff6b4a; --probe: #ff3b30;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font: 14px/1.5 system-ui, "Segoe UI", sans-serif; color: var(--ink); background: var(--bg); }}
  header {{ position: sticky; top: 0; background: #fff; border-bottom: 1px solid var(--line); padding: 12px 18px; display: flex; align-items: center; gap: 14px; z-index: 5; }}
  header h1 {{ margin: 0; font-size: 15px; }}
  .stats {{ color: var(--mut); font-size: 12px; }}
  button {{ border: 1px solid var(--line); background: #fff; border-radius: 6px; padding: 5px 12px; cursor: pointer; font: inherit; }}
  button:hover {{ background: #f0f2f5; }}
  .time {{ font-variant-numeric: tabular-nums; color: var(--mut); }}
  main {{ max-width: 980px; margin: 0 auto; padding: 18px; }}
  .row {{ background: #fff; border: 1px solid var(--line); border-radius: 8px; margin-bottom: 10px; padding: 10px 14px; }}
  .row .meta {{ display: flex; gap: 10px; align-items: baseline; color: var(--mut); font-size: 12px; }}
  .row .meta .idx {{ color: var(--ink); font-weight: 600; }}
  .row .meta .delta {{ font-size: 11px; }}
  .row .meta .delta.warn {{ color: var(--bar-hi); }}
  .row .text {{ margin: 6px 0 8px; font-size: 15px; }}
  .bars {{ position: relative; height: 26px; display: flex; gap: 2px; }}
  .bar {{ flex: none; height: 100%; border-radius: 3px; background: var(--bar); cursor: pointer; opacity: 0.85; transition: opacity .12s; }}
  .bar:hover {{ opacity: 1; }}
  .bar.cur {{ background: var(--bar-hi); }}
  .probe {{ position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--probe); pointer-events: none; }}
  .empty {{ color: var(--mut); font-size: 12px; }}
  footer {{ color: var(--mut); font-size: 12px; text-align: center; padding: 18px; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <span class="stats">{rows} 行 · {words} 词 · 逐字 {exact}/{rows} · 覆盖 {covered}/{chars}</span>
  <span class="time" id="clock">0.000s / {duration:.1f}s</span>
  <button id="play">▶ 播放</button>
</header>
<main id="main"></main>
<footer>点击词条跳转播放；播放中当前词高亮为红色。时间 = 首词 start − 0.05s（行滚动同步）。</footer>
<script>
  const W = {data};
  const audioEl = {audio};
  const main = document.getElementById('main');
  const clock = document.getElementById('clock');
  const playBtn = document.getElementById('play');

  function fmt(s) {{ return s.toFixed(3) + 's'; }}

  for (const row of W.rows) {{
    const sec = document.createElement('section');
    sec.className = 'row';
    const meta = document.createElement('div');
    meta.className = 'meta';
    const idx = document.createElement('span'); idx.className = 'idx'; idx.textContent = '#' + row.lineIndex;
    const t = document.createElement('span'); t.className = 'time'; t.textContent = 'time ' + fmt(row.time);
    meta.append(idx, t);
    if (row.words.length) {{
      const d = row.words[0].start - 0.05 - row.time;
      const dn = document.createElement('span');
      dn.className = 'delta' + (Math.abs(d) > 0.5 ? ' warn' : '');
      dn.textContent = '首词偏差 ' + (d >= 0 ? '+' : '') + d.toFixed(2) + 's';
      meta.append(dn);
    }}
    const text = document.createElement('div'); text.className = 'text'; text.textContent = row.text;
    sec.append(meta, text);
    if (row.words.length) {{
      const bars = document.createElement('div'); bars.className = 'bars';
      const span = (row.words[row.words.length - 1].end - row.words[0].start) || 0.05;
      for (const w of row.words) {{
        const b = document.createElement('div');
        b.className = 'bar';
        b.style.width = ((w.end - w.start) / span * 100) + '%';
        b.title = w.text + '  ' + fmt(w.start) + ' – ' + fmt(w.end);
        b.dataset.start = w.start; b.dataset.end = w.end;
        b.addEventListener('click', () => {{ if (audioEl) {{ audioEl.currentTime = w.start; if (audioEl.paused) audioEl.play(); }} }});
        bars.append(b);
      }}
      sec.append(bars);
    }} else {{
      const e = document.createElement('div'); e.className = 'empty'; e.textContent = '（该行未对齐到词：whisper 未转写此段，或弱匹配后流耗尽）';
      sec.append(e);
    }}
    main.append(sec);
  }}

  const allBars = [...document.querySelectorAll('.bar')].map(b => ({{ el: b, s: +b.dataset.start, e: +b.dataset.end }}));
  let raf = null;
  function tick() {{
    if (audioEl) {{
      const ct = audioEl.currentTime;
      clock.textContent = ct.toFixed(3) + 's / ' + W.duration.toFixed(1) + 's';
      for (const b of allBars) b.el.classList.toggle('cur', ct >= b.s && ct < b.e);
    }}
    raf = requestAnimationFrame(tick);
  }}
  tick();
  playBtn.addEventListener('click', () => {{
    if (!audioEl) return;
    if (audioEl.paused) audioEl.play(); else audioEl.pause();
  }});
  if (audioEl) audioEl.addEventListener('play', () => (playBtn.textContent = '⏸ 暂停'));
  if (audioEl) audioEl.addEventListener('pause', () => (playBtn.textContent = '▶ 播放'));
</script>
</body>
</html>
"""


def render_preview(rows, duration, audio_rel):
    """words.json 行列表 → 自包含 HTML 校对页。audio_rel 为空时不带音频。"""
    exact = sum(1 for r in rows if ''.join(w['text'] for w in r['words']) == r['text'])
    covered = sum(len(r['text']) for r in rows if r['words'])
    total_chars = sum(len(r['text']) for r in rows)
    data = {'duration': duration, 'rows': rows}
    audio = 'new Audio("{}")'.format(audio_rel) if audio_rel else 'null'
    return _PAGE.format(
        title='词级时间校对',
        rows=len(rows), words=sum(len(r['words']) for r in rows),
        exact=exact, covered=covered, chars=total_chars,
        duration=duration, data=json.dumps(data, ensure_ascii=False),
        audio=audio,
    )


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit('usage: wk-preview <words.json> <audio.mp3> <out.html>   (audio optional: wk-preview <words.json> <out.html>)')
    words_path = sys.argv[1]
    audio_rel = sys.argv[2] if len(sys.argv) == 4 else ''
    out_path = sys.argv[3] if len(sys.argv) == 4 else sys.argv[2]

    try:
        with open(words_path, encoding='utf-8-sig') as f:
            rows = json.load(f)
    except OSError as e:
        sys.exit(f'error: cannot read {words_path}: {e}')
    except json.JSONDecodeError as e:
        sys.exit(f'error: {words_path} is not valid JSON: {e}')

    duration = max((w['end'] for r in rows for w in r['words']), default=0.0)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(render_preview(rows, duration, audio_rel))
    print(f'wrote {out_path} ({len(rows)} rows)')


if __name__ == '__main__':
    main()
