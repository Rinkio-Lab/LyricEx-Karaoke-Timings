"""whisper-karaoke-timings: word-level karaoke timing for songs without
platform word-synced lyrics (NetEase klyric / QQ qrc / Kugou krc are often
missing for Japanese classics like Lemon).

Pipeline:
    audio.mp3 --wk-transcribe--> whisper.json --wk-align--> words.json
words.json rows [{lineIndex,time,text,words:[{text,start,end}]}] are ready to
inject into a LyricEx v2 pack's lyrics.json (per-line `words` field drives
the karaoke word highlight).
"""
