"""LyricEx karaoke toolkit - fetch NetEase lyric JSON.

Mirrors the LyricEx main project's scripts/fetch-netease-lyrics.mjs API:
search (/api/cloudsearch/pc) + lyric (/api/song/lyric?id=..&lv=-1&kv=-1&tv=-1)
with a browser UA + Referer. Saves the raw song JSON (lrc.lyric) so wk-align
can consume it directly as netease-raw.json.

Usage:
    wk-fetch <song-id> <out.json>                # exact song id
    wk-fetch "歌名 歌手" <out.json> [--pick N]    # search, pick N-th (1-based)
"""
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120'
_REFERER = 'https://music.163.com/'
_TIMEOUT_MS = 8  # 秒；国内网络/风控下宁可超时报错，不无限挂起


def is_song_id(query):
    return re.fullmatch(r'\d+', query) is not None


def search_url(query, limit=5):
    return ('https://music.163.com/api/cloudsearch/pc?s='
            + urllib.parse.quote(query) + '&type=1&limit=' + str(limit))


def lyric_url(song_id):
    return f'https://music.163.com/api/song/lyric?id={song_id}&lv=-1&kv=-1&tv=-1'


def pick_song(data, pick=1):
    """cloudsearch 响应 → (id, name, artist)；无结果/越界抛 ValueError。"""
    songs = (data or {}).get('result', {}).get('songs') or []
    if not songs:
        raise ValueError('no search results')
    i = pick - 1
    if i < 0 or i >= len(songs):
        raise ValueError(f'--pick {pick} out of range (1..{len(songs)})')
    s = songs[i]
    artist = (s.get('ar') or [{}])[0].get('name', '')
    return s['id'], s['name'], artist


def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': _UA, 'Referer': _REFERER})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_MS) as res:
        if res.status != 200:
            raise OSError(f'HTTP {res.status}')
        return json.load(res)


def main():
    if len(sys.argv) < 3:
        sys.exit('usage: wk-fetch <song-id | "歌名 歌手"> <out.json> [--pick N]')
    query, out_path = sys.argv[1], sys.argv[2]
    pick = 1
    if '--pick' in sys.argv:
        i = sys.argv.index('--pick')
        try:
            pick = int(sys.argv[i + 1])
        except (IndexError, ValueError):
            sys.exit('error: --pick needs an integer')

    try:
        if is_song_id(query):
            song_id, name, artist = int(query), f'id {query}', ''
        else:
            data = fetch_json(search_url(query))
            song_id, name, artist = pick_song(data, pick)
            print(f'search: #{pick} -> {song_id} | {name} | {artist}')

        lyr = fetch_json(lyric_url(song_id))
        if lyr.get('code') != 200:
            sys.exit(f'error: lyric API code {lyr.get("code")}')
        has_lrc = bool((lyr.get('lrc') or {}).get('lyric', '').strip())
        if not has_lrc:
            sys.exit('error: song has no lrc lyrics on NetEase (伴奏/未收录)')

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(lyr, f, ensure_ascii=False, indent=2)
        lines = lyr['lrc']['lyric'].strip().splitlines()
        print(f'saved raw JSON -> {out_path} ({len(lines)} lrc lines)')
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as e:
        sys.exit(f'error: {e}')


if __name__ == '__main__':
    main()
