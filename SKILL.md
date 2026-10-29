---
name: mv-code-driven-pipeline
slug: mv-code-driven-pipeline
displayName: Code-Driven MV Pipeline
display_name: "代码驱动 MV 制作管线"
description: Produce a music video as a deterministic code timeline instead of an edit — thesis → measured beats → shot list → masked scene code → geometric precheck → render → A/B contact sheet → verified handover pack. Ships four zero-dependency tools (bbox probe, sprite-anchor solver, render-time geometry QC with dual controls, handover packer with rebuild verification) plus a masked-band scene template and shot-list/audio-alignment contracts. Use when the user asks to make an MV, lyric video, music visualization, beat-synced animation, or asks why characters get cut off / why a cut feels static / how to make a second chorus hit harder.
description_zh: 用「代码时间轴」而不是剪辑做 MV：thesis → 实测节拍 → 分镜 → 遮罩场景代码 → 渲染前几何预检 → 渲染 → 对照板 → 带重建验证的交接包。附 4 个零依赖工具（bbox 探测 / sprite 锚点反解 / 几何 QC 双对照 / 打包重建校验）与场景、分镜模板。另含「整片色块预演」——花生成积分之前先把全片跑成成片时长的低保真片。
category: creative
version: 1.1.0
author: CatsMansion
agent_created: true
visibility: public
---

# 代码驱动 MV 制作管线

把一支 MV 做成**确定性代码时间轴**：每一帧都是 `f(歌曲时间)` 的纯函数，可以审查、可以并行渲染、可以 4 分钟重渲一遍。

核心不是"用程序画图"，是**用代码实现手绘动画的语法**（コマ打ち / line boil / 文字作为画面主体 / 克制与爆发）。

## 何时用

- 要做 MV / 歌词视频 / 音乐可视化，要求**卡拍**、精确到帧、可重渲
- 已有静态立绘，但"动起来是死的"
- 要解释或修「人物被切没了」「某一镜贴边」「第二遍副歌不够狠」
- 要交付一份对方**能接手跑起来**的工程包

**不用**：纯剪辑（素材是视频）、纯生成式视频、单张海报。

## 七条铁律

1. **先 thesis，后画面。** 一句话视觉机制说不出来，就不要打开引擎。机制 ≠ 氛围（`docs/principles.md` §2）。
2. **节拍一律实测。** ⛔ 不抄文档 BPM。实测与文档差 0.4s 是常态，错一个强拍整支片就假。
3. **人物落点用 `snap_cx.py` 算。** ⛔ 不能拿 bbox 中心当 sprite cx —— 实测会偏 90–300px，肉眼发现不了。
4. **遮罩镜头之间只能硬切。** 用 xfade/wipe 会让两条反向遮罩同时存在，画面出现「十字」。
5. **递进改「质」不改「量」。** 带宽 ±8%、字号 +14 这种量变，观众看不见（`docs/pitfalls.md` §6）。
6. **渲染前必跑 `qc_scan.py`。** ⛔ 不要肉眼逐帧看 700 帧找"人在哪一帧消失"。
7. **花生成积分之前，先把整片跑成色块预演。** ⛔ 不要等到素材烧完才发现顺序/景别不对。
   做法见 `docs/previz-blockout.md`：已有立绘做单色剪影 + 代码渲的色块场景，按分镜表逐帧跑到成片时长、带原声。
   它只证明顺序 / 景别 / 节奏 / 亮度，**不证明好不好看**。

## 九阶段与闸门

| # | 阶段 | 关键动作 | 闸门（不过不许往下） |
|---|---|---|---|
| 0 | 拆参考片 | 量化切镜数 / 镜头时长 / 事件率 | 能说出目标事件率与理由 |
| 1 | 听音频 | librosa：beats / downbeats / sections / impacts / 包络 | 段落长 ÷ 拍长 = 整数 |
| 2 | 定 thesis | `templates/concept.md` | 一句话机制，且在歌词里有依据 |
| 3 | 出素材 | 角色母版 → 姿势 → 统一背景 → `probe_bbox.py` | 每张留白 ≥60px、Δlum ≥76 |
| 4 | 分镜 | `templates/storyboard.md` 12 项参数 | 遮罩形态不连用；事件率 0.8–1.1/s |
| 4.5 | **整片色块预演** | 立绘剪影 + 色块场景，逐格渲到成片时长（`docs/previz-blockout.md`） | 帧数对得上 + 每个接缝双侧抽帧核格号 + 采样 30 帧以上的中位亮度落在目标时间段 |
| 5 | 写时间轴 | `templates/timeline.example.js`，切点写 `at(beat)` | 抽 8–10 帧构图成立 |
| 6 | 几何预检 | `probe_bbox.py` → `snap_cx.py` → `qc_scan.py` | 退出码 0 + 阴阳双对照都跑过 |
| 7 | 渲染 | `--codec x264`（NVENC 常常不可用） | ffprobe 的帧数/时长/音轨与算值一致 |
| 8 | 审片 | 同一段落两次演绎做**左右对照板** | 每组能说出差在哪一层 |
| 9 | 交付 | `pack_handover.py` | 打印「可以发货」 |

详细命令与理由见 `docs/pipeline.md`。

## 脚本（零依赖，只用标准库 + numpy/PIL）

| 脚本 | 作用 | 命令 |
|---|---|---|
| `scripts/probe_bbox.py` | 量每张立绘的 bbox / 留白列 / 与背景明度差 | `python probe_bbox.py --dir assets/char --out bbox.json` |
| `scripts/snap_cx.py` | 脸位 ↔ sprite 锚点互算；批量审计每镜落点 | `python snap_cx.py --bbox bbox.json --img 01 --hfrac 0.88 --target-x 700` |
| `scripts/qc_scan.py` | 渲染前逐帧几何预检（脸是否在遮罩内 / 是否贴边） | `python qc_scan.py --spec qc.json --check-timeline engine/timeline.js` |
| `scripts/pack_handover.py` | 打包 + 解包逐文件 sha256 重建验证 + 跑一次真实命令 | `python pack_handover.py --dir pack --out pack.zip --manifest 文件清单.txt` |

**必须成对使用**（否则判据不可信）：
- `probe_bbox.py` 产出 bbox → 粘进 `qc.json`（⛔ 不手写 bbox）
- `snap_cx.py` 算出 cx → 填进 timeline（⛔ 不手推）
- `qc_scan.py` 的结论必须带**双对照**：阴性（已验收时间轴全绿）+ 阳性（故意挪 60px / 收窄到 360px 必须报硬伤）

`qc_scan.py` 两条常用开关：
- `--fps 10` 抽稀采样（全片 700 帧在 30fps 下也只要几秒）
- `--breathe` 把呼吸包络的最坏收窄算进去（更严格；会对遮罩张开的头几帧报边界帧，默认关闭）

## 模板

| 文件 | 用途 |
|---|---|
| `templates/scene_band.js` | 遮罩带场景（带外压暗、12fps 绘制层、强拍提亮、歌词在带外、可选 fg 层文字穿身） |
| `templates/timeline.example.js` | 7 镜覆盖 7 种遮罩形态，切点全部由 beat 推出 |
| `templates/qc.example.json` | `qc_scan.py` 的输入样例（自包含，可直接跑） |
| `templates/concept.md` | thesis / 色彩脚本 / 角色圣经 / 变化矩阵自检 |
| `templates/storyboard.md` | 12 项参数逐镜表 + 密度核算 + 砍掉的想法 |
| `templates/shotlog.md` | 实拍记录（翻车必须写根因） |

## 参考文档（按需读，不要一次全读）

| 何时读 | 文件 |
|---|---|
| 设计分镜/判断"这样够不够" | `docs/principles.md` — 十条手绘语法、递进三层、开工四条自检 |
| 遇到"人被切没 / 转场十字 / 带宽失效 / 渲染报错" | `docs/pitfalls.md` — 每条带根因与判据 |
| 第一次跑全流程 | `docs/pipeline.md` — 九阶段命令与闸门 |
| **素材还没出，要先看整片是什么样** | `docs/previz-blockout.md` — 景别 k 值表、镜头空档延展、亮度中位判读、8 个色块场景模板 |

## 交付结构

```
00_索引与跑法.md      四条命令能跑起来
01_成片/             母版（带音轨）
02_对照板/           ⭐ 最有说服力的交付物（同拍左右对照）
03_文档/             CONCEPT / STORYBOARD / SHOT-LOG / 递进设计
04_代码/             scenes / timeline / tools
05_素材/             立绘 + 音频 + analysis（省对方一次音频分析）
```

⛔ 不放 `fonts/`、`node_modules/`、工程中间产物。
✅ 打包后必须做重建验证，且包里**不许出现任何本机绝对路径**。

## 成本纪律

出图只在**角色母版**这一步花钱（15–30 积分量级），其余全部代码，0 积分。

```
thesis → 音频实测 → timeline → **整片色块预演给人看** → 点头才出素材 → 渲全片
```

⛔ 预演之前不许批量出图。实测：一套 6 张首帧返工一次就是 60–90 积分，
而整片色块预演是 0 积分、几十分钟，能提前暴露顺序和景别错误。

## 依赖

- 引擎：[vocaloid-style-mv-pipeline](https://github.com/EGSECDA/vocaloid-style-mv-pipeline)（MIT）或其等价实现，需提供 `window.Z`（`scene` / `draw.sprite` / `ease` / `quant` / `imgSync` / `env.low` / `env.onset`）
- Python 3.10+：`numpy`、`Pillow`
- Node 20+、ffmpeg/ffprobe（PATH 可用即可）
- 换引擎版本先核对 `Z` 命名空间是否同名，不对就改模板头部那一行映射
