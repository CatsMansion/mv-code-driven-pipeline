# 九阶段管线

每个阶段都有**验收闸门**。闸门没过不许进下一阶段 —— 这条纪律比任何技巧都省时间。

```
0 拆参考片 → 1 听音频 → 2 定 thesis → 3 出素材 → 4 分镜
   → 5 写时间轴 → 6 几何预检 → 7 渲染 → 8 审片 → 9 交付
```

---

## 0. 拆参考片（量化，不靠感觉）

```bash
python mv_ref.py reference.mp4            # 见 mv-shot-audit skill
```

要拿到的数：切镜数 / 镜头时长中位数 / 每秒画面事件率 / 段密度 / 色彩曲线。

**为什么先做这步**：1.13 亿播放的参考片实测全片只有 **11 次切镜**（中位 7.87s），
靠的是「镜头不动 + 每 0.7–2.5s 换字幕 + 局部作画」。
凭直觉做会做成"每句一切"，那不是风格问题，是**语法错了**。

**闸门**：能说出"参考片的画面事件率是 X，我打算做到 Y，理由是 Z"。

---

## 1. 听音频（librosa，实测）

```bash
ffmpeg -y -i song.mp3 -ac 2 -ar 48000 -c:a pcm_s16le song.wav
python tools/analyze_audio.py     # beats / downbeats / bars / sections / stops / impacts / 逐帧包络
```

产出 `analysis/audio.json` + `envelope_30fps.json`。

**闸门**：
- 段落长度 ÷ 拍长 = 整数（对不上就是起点选错了）
- 每个切点能指到具体的 beat index
- 强拍时刻来自 `impacts` 的 strength 峰值，不是"听起来差不多"

⛔ 不要抄任何文档里的 BPM。同一首歌实测与文档差 0.4s 是常事。

---

## 2. 定 thesis（一句话视觉机制）

用 `templates/concept.md`。必须写成"机制"而不是"氛围"：

| ❌ 氛围 | ✅ 机制 |
|---|---|
| 一个关于暗恋的、忧郁的故事 | 全片只有一道缝。它先是门缝，然后是眼缝，最后是耳洞 |
| 用光影表达思念 | 光在光源消失之后还留着（留存）；一道墙把人隔在外面（阻隔） |

配套要定的：**色彩脚本**（每个段落的主色 + accent 上限）、**主形状**、**角色圣经**、
**6–10 个 signature moments**、**变化矩阵自检**。

**闸门**：一句话能说清"视觉机制"，且这个词在歌词里有依据（不是硬套的）。

---

## 3. 出素材（唯一花积分的一步）

- 先做**角色母版**（3 张候选，选 1）
- 每个姿势以母版为参考图生成 → 统一背景 → 抠图
- 素材要过 `probe_bbox.py`：bbox、留白列、Δlum

**闸门**：
- 每张图 **留白列 ≥ 60px**（否则这张图物理上放不下字幕，别硬塞）
- Δlum ≥ 76（深色背景上语义才读得出来）
- 8 张以内先跑通，不要一次做 40 张

⛔ 素材阶段没验证就往下走，等于把返工成本乘上镜头数。

---

## 4. 分镜（12 项参数逐镜填满）

用 `templates/storyboard.md`：

`镜号 / 时间窗(拍) / 素材 / 景别(hFrac) / 构图锚点(脸位) / 缩放 / 旋转 / 倾斜 /
运镜 / 入场 / 字幕 / 出场`

**闸门**：
- 每一镜的**遮罩形态**和上一镜不同（同一形态不许连着用两次）
- 每镜只有一个"主要动作"（多余的动作砍掉）
- 事件率核算到 **0.8–1.1 次/秒**（低于 0.6 太静，高于 1.2 观众读不过来）

---

## 5. 写时间轴（`timeline.js`）

用 `templates/timeline.example.js`。规则：

- 切点用 `at(beat)` 算，**不写整秒**
- 人物落点用 `snap_cx.py` 算，**不手推**
- 每镜只填 6 个必填项：素材 / hFrac / cx,cy / 遮罩段 / 音频驱动量 / 歌词
- 遮罩镜头之间**不写转场**（= 硬切）；只有 `black` / `flash` 可用

**闸门**：`node tools/stills.mjs --times ...` 抽 8–10 帧，肉眼确认构图成立。

---

## 6. 几何预检（渲染前，秒级）

```bash
python scripts/probe_bbox.py --dir assets/char --out bbox.json
python scripts/snap_cx.py --bbox bbox.json --shots qc.json
python scripts/qc_scan.py --spec qc.json --check-timeline engine/timeline.js
```

**闸门**：`qc_scan.py` 退出码 0，且**阴性/阳性双对照都跑过**
（阴性=已验收时间轴全绿；阳性=故意挪 60px 必须报硬伤）。

⛔ 这一步不做，就会在渲染 40 分钟后才发现"第 8 秒人没了"。

---

## 7. 渲染

```bash
node tools/render_frames.mjs --start <t0> --end <t1> --mode blob \
     --out render/x.mp4 --audio audio/song.wav --codec x264
```

- NVENC 不可用就 `--codec x264`，不要在这上面耗
- 瓶颈是像素读回（~45ms/帧），不是绘制（0.4ms/帧）→ 提速靠并行 worker
- 长任务一律放后台 + 落日志

**闸门**：`ffprobe` 查 nb_frames / duration / 音轨数，与时间轴算出来的值一致。

---

## 8. 审片（对照板是核心交付物）

```bash
node tools/stills.mjs --times ... --sheet check
python tools/review_sheets.py render/x.mp4 --step 1.8 --out render/review1
```

**必做**：同一段落两次演绎做成**左右对照板**（每拍左 A / 右 B）。
递进成立不成立，看板上 3 秒就能判断 —— 比看视频快 20 倍。

**闸门**：对照板上每一组都能说出"差在哪一层（景别/色彩/结尾）"。
说不出 = 递进没做出来，回去改。

---

## 9. 交付

用 `pack_handover.py`，结构固定：

```
00_索引与跑法.md      ← 四条命令能跑起来
01_成片/             ← 母版（带音轨）
02_对照板/           ← ⭐ 最有说服力的交付物
03_文档/             ← CONCEPT / STORYBOARD / SHOT-LOG / 递进设计
04_代码/             ← scenes / timeline / tools
05_素材/             ← 立绘 + 音频 + analysis（省对方 35 秒）
```

⛔ 不放 `fonts/`、`node_modules/`、中间产物。
✅ **必须**做重建验证：解包 → 逐文件 sha256 对齐 → 在解包目录跑一次真实命令。

**闸门**：`pack_handover.py` 打印「可以发货」。

---

## 成本纪律：0 积分路线

```
thesis → 音频实测 → timeline → stills 给对方看 → 点头才渲全片
```

出图只发生在**角色母版**这一步（15–30 积分量级）。其余全部代码，0 积分。

顺序建议（扩展整首歌时）：**先闭合首尾（Intro → Out），再补中间（V2），最长最难的 V1 放最后**。
首尾闭合之后，中间怎么填都不散。

---

## 参考引擎

本管线的场景/时间轴模板按 [vocaloid-style-mv-pipeline](https://github.com/EGSECDA/vocaloid-style-mv-pipeline)（MIT）的 `window.Z` API 写。
换引擎版本先核对 `Z.draw.sprite` / `Z.ease` / `Z.quant` / `Z.imgSync` 是否同名，
不对就改模板头部那一行 `const Z = window.Z, D = Z.draw, E = Z.ease` 的映射。
