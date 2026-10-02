# LyricEx Karaoke Timings

LyricEx 专用工具：把「任意没有逐字卡拉OK歌词的歌」变成有词级时间轴的 JSON，
供 LyricEx 包（`lyrics.json` 每行的 `words` 字段）做卡拉OK逐字高亮。

背景：Lemon（米津玄師）这类日语老歌在 网易云/QQ/酷狗/LRCLIB 都**没有词级逐字**
收录（已多平台多接口验证：klyric/qrc/krc/hasWordSync 全为空）。本工具从音频本身
测量词级时间——**真实数据，不是编造**。

## 流程

```
audio.mp3 (原唱/卡拉OK版, 越高码率越好)
    │  wk-transcribe  (faster-whisper 词级转写)
    ▼
whisper.json   { language, duration, segments:[{id,start,end,text,words:[{word,start,end}]}] }
    │  wk-align  (SequenceMatcher 字符流对齐 + 时间比例投影)
    ▼
words.json     [{ lineIndex, time, text, words:[{text,start,end}] }]
    │  LyricEx 制包流程 (build-pack.mjs / 软件内导入)
    ▼
Lemon.lxp.zip  46 行 / 42 行逐字 / 309 词级时间戳
```

## 安装（uv）

```powershell
git clone https://github.com/Rinkio-Lab/LyricEx-Karaoke-Timings.git
cd "LyricEx Karaoke Timings"
uv sync          # 建 venv、装 faster-whisper（自动带 av；已内置 av>=14 shim）
```

## 用法

```powershell
# 国内拉模型走镜像（首次转写自动下载 small 模型 ~460MB）
$env:HF_ENDPOINT = 'https://hf-mirror.com'

# 1) 转写：音频 → 词级时间戳
uv run wk-transcribe lemon-onvocal.mp3 whisper-lemon.json small

# 2) 对齐：词级时间戳 + 网易云原始 JSON（含 lrc.lyric）→ 逐行 words
uv run wk-align whisper-lemon.json netease-lemon.json lemon-words.json
```

模型：默认 `small`（日语质量/速度均衡，CPU int8 转写 4:34 歌曲约几分钟）；
可选 `base`（更快、略粗）或 `medium`（更准、更慢）。

## align 算法要点

1. 把 whisper 词拼成字符流（每字符记录所属词）。
2. 官方歌词行逐行在剩余字符流中做 `SequenceMatcher.find_longest_match`
   找最佳匹配块（匹配弱于 50% 时按等长消费兜底）。
3. 行内：官方行字符按 whisper 词的时间长度比例投影到各词
   ——**words 拼接文本与官方行文本 100% 一致**，时间 100% 来自音频。
4. 行 `time` = 首词 start − 0.05s，保证行级滚动与卡拉OK高亮同步。

## 输入 / 输出

| 文件 | 说明 |
|---|---|
| `whisper.json` | faster-whisper 词级输出，`words[{word,start,end}]` 秒级 |
| `netease-raw.json` | 网易云歌词接口原始返回（`lrc.lyric` 为官方行文本） |
| `words.json` | `[{lineIndex,time,text,words:[{text,start,end}]}]`，可直接注入 LyricEx 包 |

## 已知限制

- whisper 分词是音节级（如 `夢/な/ら`），卡拉OK高亮比词级更细，视觉更密。
- 行文本与音频的字符覆盖一般 ≥80%；弱匹配行由时间窗兜底，时间仍为真实测量。
- 元数据行（作词/作曲/编曲/制作）无演唱，不带 words。
