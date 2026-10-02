"""Transcribe an audio file to WORD-LEVEL timestamps with faster-whisper
(Japanese), for building karaoke word timing of songs whose platforms don't
ship word-synced lyrics.

Usage:
    wk-transcribe <audio.mp3> <out.json> [model=small]

Output JSON: { language, duration, segments:[{id,start,end,text,words:[{word,start,end}]}] }

Notes:
- av >=14 dropped the `metadata_errors` kwarg that older faster-whisper passes;
  a shim is applied so latest av works on python 3.14.
- small ~4:34 song takes a few minutes on CPU int8; use base for faster/coarser.
- Set HF_ENDPOINT=https://hf-mirror.com when model download is slow (CN).
"""
import json
import sys
from pathlib import Path

# av >=14 dropped the metadata_errors kwarg that older faster-whisper passes;
# keep av at latest (py3.14 wheel) and shim the removed kwarg.
import av as _av

_orig_open = _av.open


def _patched_open(*args, **kwargs):
    kwargs.pop('metadata_errors', None)
    return _orig_open(*args, **kwargs)


_av.open = _patched_open

from faster_whisper import WhisperModel  # noqa: E402


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit('usage: wk-transcribe <audio.mp3> <out.json> [model=small]')
    audio, out = sys.argv[1], sys.argv[2]
    model_name = sys.argv[3] if len(sys.argv) > 3 else 'small'

    if not Path(audio).is_file():
        sys.exit(f'error: no such file: {audio}')

    model = WhisperModel(model_name, device='cpu', compute_type='int8')
    segments, info = model.transcribe(
        audio,
        language='ja',
        word_timestamps=True,
        vad_filter=False,
        condition_on_previous_text=False,
        beam_size=5,
    )

    result = []
    for seg in segments:
        words = [
            {'word': w.word, 'start': w.start, 'end': w.end}
            for w in (seg.words or [])
        ]
        result.append({
            'id': seg.id,
            'start': seg.start,
            'end': seg.end,
            'text': seg.text.strip(),
            'words': words,
        })

    with open(out, 'w', encoding='utf-8') as f:
        json.dump(
            {'language': info.language, 'duration': info.duration, 'segments': result},
            f, ensure_ascii=False, indent=1,
        )

    print(f'segments={len(result)} total_words={sum(len(s["words"]) for s in result)} -> {out}')


if __name__ == '__main__':
    main()
