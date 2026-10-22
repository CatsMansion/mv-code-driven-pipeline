# 代码驱动 MV 制作管线

把一支 MV 做成**确定性代码时间轴**——不是剪辑、不是生成式视频，是 `f(歌曲时间)` 的纯函数。

```
歌曲 + 歌词 → 实测节拍 → 视觉机制(thesis) → 分镜 → 场景代码 → 几何预检 → 渲染 → 对照板 → 交接包
```

每一帧可审查、可重渲、可并行。素材只在「角色母版」一步花钱，其余全部代码。

---

## 为什么需要它

做 MV 最容易死在四个地方，这个仓库就是这四件事的工具化和成文：

| 症状 | 真因 | 这里怎么解 |
|---|---|---|
| 人物在某几帧被切没了、某镜贴边 | sprite 锚点是**图像中心**，不是 bbox 中心，实测偏 90–300px | `snap_cx.py` 反解 + `qc_scan.py` 渲染前逐帧判 |
| 转场中间出现「十字」怪图 | 两条反向遮罩被 xfade 叠加 | 硬规矩：遮罩镜头之间只能硬切 |
| 第二遍副歌"不够狠"，但改了一堆参数看不出差别 | 做的是**量变**（±8% 宽度、+14 字号），8bit 大画面下不可见 | `docs/principles.md` 的递进三层：景别 / 色彩 / 反向动作 |
| 交接包发出去对方跑不起来 | 只验证了"能解压"，没验证"能跑" | `pack_handover.py` 解包后逐文件 sha256 + 跑一次真实命令 |

---

## 实测数据（不是估计）

在 1920×1080、静态立绘、8 镜 / 64 拍 / 23.4 秒的副歌上实测：

| 项 | 数值 |
|---|---|
| 场景绘制 | **0.4 ms/帧** |
| 像素读回（真瓶颈） | **~45 ms/帧** |
| 701 帧全片 | **35 秒** |
| 音频对齐 | 42.72–66.09 = **64 拍 = 16 小节**，切点全部落真实 beat |
| 几何预检 | 全片 701 帧，**秒级**出报告 |
| 阳性对照灵敏度 | 遮罩中心偏 **60px** → 抓出 **38 帧**「人物出遮罩」（肉眼完全看不出） |
| 递进可辨识度 | 带宽 ±8% → 8 拍里 **6 拍无差别**；景别 +15% → 每拍都能看出 |

---

## 快速开始

```bash
git clone https://github.com/CatsMansion/mv-code-driven-pipeline
cd mv-code-driven-pipeline

# 1) 量素材几何（每张立绘的 bbox / 留白列 / 明度差）
python scripts/probe_bbox.py --dir assets/char --out bbox.json

# 2) 算人物落点：我要脸落在 x=700，hFrac=1.00，求 cx
python scripts/snap_cx.py --bbox bbox.json --img 01 --hfrac 1.00 --target-x 700

# 3) 渲染前几何预检（把 bbox 粘进 qc.json 的 bbox 字段）
python scripts/qc_scan.py --spec qc.json --check-timeline engine/timeline.js --json report.json

# 4) 打包交接，并证明它不是空包
python scripts/pack_handover.py --dir pack --out pack.zip --manifest 文件清单.txt \
       --verify-cmd "python scripts/qc_scan.py --spec qc.json"
```

依赖：Python 3.10+（`numpy`、`Pillow`）。其余零依赖，不装包、不联网。

---

## 四个工具

| 脚本 | 输入 | 输出 | 关键行为 |
|---|---|---|---|
| `probe_bbox.py` | 立绘目录 | `bbox.json` | 9 patch 取背景色 → 前景距离 → bbox / 留白列 / Δlum，留白不足直接告警「放不下字幕」 |
| `snap_cx.py` | `bbox.json` | 正确 `cx,cy` | 正算反算双向校验；批量模式一次审全部镜头的脸位与距边 |
| `qc_scan.py` | `qc.json` | 人读报告 + JSON | 判据是**脸是否在遮罩内**（不是可见面积）；窄遮罩与张开瞬间跳过；支持 `--breathe` 严格模式；`--check-timeline` 防两处参数不同步 |
| `pack_handover.py` | 排好结构的包目录 | zip + 验证报告 | 解包后逐文件 sha256 正反两向对齐，再在解包目录跑一次真实命令 |

---

## 目录

```
SKILL.md                      给 agent 用的主文件（何时用 / 铁律 / 九阶段闸门）
docs/pipeline.md              九阶段命令与闸门（第一次跑看这个）
docs/principles.md            十条手绘语法 + 递进三层 + 开工四条自检
docs/pitfalls.md              每条坑都带根因与判据
templates/scene_band.js       遮罩带场景（带外压暗 / 12fps 绘制层 / 歌词在带外）
templates/timeline.example.js 7 镜覆盖 7 种遮罩形态，切点由 beat 推出
templates/qc.example.json     qc_scan 的自包含输入样例
templates/{concept,storyboard,shotlog}.md   三份必填文档模板
scripts/*.py                  四个零依赖工具
```

---

## 适用边界

**能做**：2D 立绘 + 遮罩 / 排版 / 音频驱动的 MV；需精确卡拍、可重渲、可交接的项目。

**不能做**：把静态立绘变成"会动"的角色。全片只有静立绘时，12fps コマ打ち 只作用于呼吸/摇摆这类微参，
屏幕上几乎看不出——要真正"动起来"必须有序列帧素材（眨眼 / 头发 / 手指），这是美术端的活，不是代码能补的。

**没做**：3D 角色（降级 2.5D）、9:16 原生竖版重排、字体级别的字面引擎。

---

## 许可

MIT。场景/时间轴模板按 [vocaloid-style-mv-pipeline](https://github.com/EGSECDA/vocaloid-style-mv-pipeline)（MIT, NikusonP）的 `window.Z` API 编写；
本仓库只包含方法与工具，不含任何角色立绘、音频或歌词。
