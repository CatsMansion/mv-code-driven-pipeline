#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qc_scan.py — 渲染前几何预检：全片逐帧算「人物还在不在画面该在的位置」

为什么必须有这个工具：
    「第 8 秒人物被切没了」这类问题，肉眼逐帧看 700 帧是看不出来的 ——
    你会盯着画面中心，而人在画面边缘消失。
    纯几何（sprite bbox ∩ 遮罩矩形）算全片，秒级出报告，渲染前就拦住。

⭐ 判据（第一版写错过，别再犯）：
    ⛔ 不要用「可见面积占比」。窄遮罩是设计（只露半张脸），按面积报会把设计全报成 bug。
    ✅ 主判据 = **脸是否在遮罩内**。面积小 ≠ bug。
    例外：遮罩被刻意闭到 < --min-slit 时跳过（呼吸停止/闭合的设计）；
          每镜开头 warmup 秒跳过（遮罩从 0 张开）。

输入 qc.json（唯一事实源；bbox 由 probe_bbox.py 生成，不要手写）:
{
  "canvas": [1920, 1080],
  "criteria": {"min_slit": 120, "warmup": 0.25, "edge_margin": 180, "fps": 30},
  "bbox": {"01": {"size": [1536, 1024], "box": [364, 511, 728, 1023]}},
  "shots": [{
    "id": "S1", "t0": 42.72, "t1": 45.65, "img": "01",
    "hFrac": 0.88, "cx": 700, "cy": 470,
    "face": [0.5, 0.5],
    "slit": {"dir": "v", "segs": [
      {"at": [0.0, 1.1], "from": 180, "to": 420, "center": 326, "ease": "outExpo"}]},
    "breatheSlit": 26
  }]
}

用法:
    python qc_scan.py --spec qc.json
    python qc_scan.py --spec qc.json --fps 10 --json report.json
    python qc_scan.py --spec qc.json --check-timeline engine/timeline.js

退出码: 0 = 无硬伤；1 = 有「人物出遮罩」硬伤；2 = 输入不同步/不可读（fail-closed）。
"""
import argparse
import json
import math
import re
import sys


def _clamp01(k):
    return 0.0 if k < 0 else 1.0 if k > 1 else k


EASE = {
    "linear": lambda k: k,
    "outExpo": lambda k: 1 if k >= 1 else 1 - 2 ** (-10 * k),
    "inExpo": lambda k: 0 if k <= 0 else 2 ** (10 * (k - 1)),
    "inOutExpo": lambda k: (k if k in (0.0, 1.0) else
                            (2 ** (20 * k - 10) / 2 if k < 0.5 else (2 - 2 ** (-20 * k + 10)) / 2)),
    "inOutSine": lambda k: -(math.cos(math.pi * k) - 1) / 2,
    "outSine": lambda k: math.sin(math.pi * k / 2),
    "outCubic": lambda k: 1 - (1 - k) ** 3,
    "inOutCubic": lambda k: 4 * k ** 3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2,
    "inOutQuad": lambda k: 2 * k * k if k < 0.5 else 1 - (-2 * k + 2) ** 2 / 2,
    "outQuad": lambda k: 1 - (1 - k) ** 2,
    "smoothstep": lambda k: k * k * (3 - 2 * k),
}


def get_ease(name):
    if name not in EASE:
        raise KeyError(f"未知 ease: {name}（可用：{', '.join(sorted(EASE))}）")
    return EASE[name]


# ---------- 几何 ----------
def slit_rect(lt, slit, W, H):
    """返回遮罩矩形 (x0,y0,x1,y1)；dir=none 返回全屏。"""
    d = slit.get("dir", "none")
    segs = slit.get("segs") or []
    if d == "none" or not segs:
        return 0.0, 0.0, float(W), float(H)
    seg = segs[0]
    for s in segs:                        # 倒序取第一个已生效的段
        if lt >= s["at"][0]:
            seg = s
    a0, a1 = seg["at"]
    k = get_ease(seg.get("ease", "outExpo"))(_clamp01((lt - a0) / max(a1 - a0, 1e-9)))
    v = seg["from"] + (seg["to"] - seg["from"]) * k
    dflt = W / 2 if d == "v" else H / 2
    c0 = seg.get("c0", seg.get("center", dflt))
    c1 = seg.get("c1", seg.get("center", dflt))
    c = c0 + (c1 - c0) * k
    if d == "v":
        return c - v / 2, 0.0, c + v / 2, float(H)
    return 0.0, c - v / 2, float(W), c + v / 2


def _sprite(entry, hfrac, cx, cy, H):
    img_w, img_h = entry["size"]
    sh = hfrac * H
    k = sh / img_h
    sw = img_w * k
    return sw, sh, k, cx - sw / 2, cy - sh / 2, img_w, img_h


def char_rect(entry, hfrac, cx, cy, H):
    """人物 bbox 在画布上的矩形。sprite 锚点 = 图像中心。"""
    sw, sh, k, sx, sy, _, _ = _sprite(entry, hfrac, cx, cy, H)
    bcx, bcy, bw, bh = entry["box"]
    return (sx + (bcx - bw / 2) * k, sy + (bcy - bh / 2) * k,
            sx + (bcx + bw / 2) * k, sy + (bcy + bh / 2) * k)


def face_point(entry, hfrac, cx, cy, H, frac):
    """脸在画布上的坐标。frac 是 bbox 内的相对位置（默认 bbox 中心）。"""
    _, _, k, sx, sy, _, _ = _sprite(entry, hfrac, cx, cy, H)
    bcx, bcy, bw, bh = entry["box"]
    return (sx + (bcx - bw / 2 + bw * frac[0]) * k,
            sy + (bcy - bh / 2 + bh * frac[1]) * k)


def inter_area(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def shrink(rect, dirn, px):
    """按呼吸幅度收窄遮罩（最坏情况）。"""
    if px <= 0:
        return rect
    x0, y0, x1, y1 = rect
    if dirn == "v":
        return x0 + px, y0, x1 - px, y1
    if dirn == "h":
        return x0, y0 + px, x1, y1 - px
    return rect


# ---------- 主流程 ----------
def scan(spec, fps=None, use_breathe=False):
    W, H = spec.get("canvas", [1920, 1080])
    cr = spec.get("criteria", {})
    min_slit = cr.get("min_slit", 120)
    warmup = cr.get("warmup", 0.25)
    margin = cr.get("edge_margin", 180)
    fps = fps or cr.get("fps", 30)
    bbox = spec["bbox"]
    step = 1.0 / fps

    flagged = []
    per_shot = []
    for s in spec["shots"]:
        key = s["img"]
        if key not in bbox:
            raise KeyError(f"shot {s['id']} 引用了 bbox 里没有的图：{key}")
        entry = bbox[key]
        dirn = s.get("slit", {}).get("dir", "none")
        # 呼吸最坏情况是遮罩「收窄」：v += amp*(low-0.28)*2.2，low=0 时窄 0.28*2.2*amp
        # ⛔ 默认不启用：它会把「遮罩正在张开的头几帧」也判成出界（实测 1 帧误报），
        #    需要极限严格时再 --breathe。
        amp = abs(s.get("breatheSlit", 0)) * 2.2 * 0.28 if use_breathe else 0.0
        n = int(round((s["t1"] - s["t0"]) / step))
        worst = None
        for i in range(n + 1):
            lt = i * step
            r = slit_rect(lt, s.get("slit", {}), W, H)
            rn = shrink(r, dirn, amp)
            cb = char_rect(entry, s["hFrac"], s["cx"], s["cy"], H)
            area = max(1e-6, (cb[2] - cb[0]) * (cb[3] - cb[1]))
            vis = inter_area(cb, r) / area * 100
            fx, fy = face_point(entry, s["hFrac"], s["cx"], s["cy"], H,
                                s.get("face", [0.5, 0.5]))
            in_mask = rn[0] <= fx <= rn[2] and rn[1] <= fy <= rn[3]
            edge = min(fx, W - fx)
            narrow = (r[2] - r[0]) < min_slit or (r[3] - r[1]) < min_slit
            flag = ""
            if lt > warmup and not narrow:
                if not in_mask:
                    flag = "⛔ 人物出遮罩"
                elif edge < margin:
                    flag = "⚠ 贴边"
                elif vis < 25 and (r[2] - r[0]) > 900 and (r[3] - r[1]) > 600:
                    flag = "⚠ 遮罩够宽人物却看不见"
            row = {"shot": s["id"], "t": round(s["t0"] + lt, 2), "lt": round(lt, 3),
                   "vis": round(vis, 1), "face_x": round(fx), "face_y": round(fy),
                   "edge": round(edge), "flag": flag}
            if flag:
                flagged.append(row)
            # 最差帧：优先取「被标记且可见率最低」的那一帧；全程正常才按可见率取
            if worst is None:
                worst = row
            elif (bool(flag), -row["vis"]) > (bool(worst["flag"]), -worst["vis"]):
                worst = row
        per_shot.append({
            "id": s["id"], "img": key, "frames": n + 1,
            "worst_t": worst["t"] if worst else None,
            "worst_vis": worst["vis"] if worst else None,
            "face_x": worst["face_x"] if worst else None,
            "edge": worst["edge"] if worst else None,
            "status": ("ok" if not [f for f in flagged if f["shot"] == s["id"]]
                       else ("bad" if [f for f in flagged
                                       if f["shot"] == s["id"] and f["flag"].startswith("⛔")]
                             else "warn")),
            "flagged": len([f for f in flagged if f["shot"] == s["id"]]),
        })
    return {"canvas": [W, H], "fps": fps, "flagged": flagged, "per_shot": per_shot}


def check_timeline(spec, path):
    """与 timeline.js 交叉核对 cx/cy/hFrac，防止两处数字不同步。

    兼容两种写法：`shot('S1', ...)` 的调用点，或 `{id: 'S1', ...}` 的对象字面量。
    这是启发式检查，只覆盖参考引擎的 hFrac/cx/cy 键名。
    """
    with open(path, encoding="utf-8") as f:
        src = f.read()
    bad = []
    for s in spec["shots"]:
        sid = re.escape(s["id"])
        pat = (r"(?:shot\(\s*['\"]" + sid + r"['\"]|id:\s*['\"]" + sid + r"['\"])"
               r".*?hFrac:\s*([\d.]+)\s*,\s*cx:\s*([\d.]+)\s*,\s*cy:\s*([\d.]+)")
        m = re.search(pat, src, re.S)
        if not m:
            bad.append(f"{s['id']}：timeline 里找不到（键名不是 hFrac/cx/cy？）")
            continue
        h2, x2, y2 = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if abs(h2 - s["hFrac"]) > 1e-6 or abs(x2 - s["cx"]) > 1e-6 or abs(y2 - s["cy"]) > 1e-6:
            bad.append(f"{s['id']}: spec hFrac={s['hFrac']} cx={s['cx']} cy={s['cy']} "
                       f"/ timeline hFrac={h2} cx={x2} cy={y2}")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="qc.json")
    ap.add_argument("--fps", type=int, help="抽稀采样（默认读 spec.criteria.fps）")
    ap.add_argument("--json", help="把完整报告写成 json")
    ap.add_argument("--check-timeline", help="与引擎 timeline.js 交叉核对参数")
    ap.add_argument("--breathe", action="store_true",
                    help="把呼吸包络的最坏收窄算进判据（更严格，会对遮罩张开瞬间报边界帧）")
    a = ap.parse_args()

    try:
        with open(a.spec, encoding="utf-8") as f:
            spec = json.load(f)
    except Exception as e:
        print(f"⛔ 读不了 {a.spec}: {e}")
        sys.exit(2)

    if a.check_timeline:
        bad = check_timeline(spec, a.check_timeline)
        if bad:
            print("⛔ spec 与 timeline.js 不同步（先修，否则预检结论无效）：")
            for b in bad:
                print("   ", b)
            sys.exit(2)
        print("✓ spec 与 timeline.js 参数一致\n")

    try:
        rep = scan(spec, a.fps, a.breathe)
    except KeyError as e:
        print(f"⛔ {e}")
        sys.exit(2)

    print(f"{'镜':<6}{'图':<7}{'最差时刻':>10}{'可见%':>8}{'脸 x':>7}{'距边':>7}  判定")
    print("-" * 64)
    for r in rep["per_shot"]:
        if not r["flagged"]:
            print(f"{r['id']:<6}{r['img']:<7}{'—':>10}{'(全程正常)':>14}")
        else:
            print(f"{r['id']:<6}{r['img']:<7}{r['worst_t']:>9.2f}s{r['worst_vis']:>8.1f}"
                  f"{r['face_x']:>7}{r['edge']:>7}  {r['status']} ({r['flagged']} 帧)")
    print()

    hard = [r for r in rep["flagged"] if r["flag"].startswith("⛔")]
    warn = [r for r in rep["flagged"] if r["flag"].startswith("⚠")]
    if not rep["flagged"]:
        print("✅ 全片没有一帧人物跑出遮罩、也没有贴边")
    else:
        print(f"合计 {len(rep['flagged'])} 帧有问题：硬伤 {len(hard)} / 警告 {len(warn)}")
        for r in (hard + warn)[:10]:
            print(f"   {r['flag']}  {r['shot']}  t={r['t']:.2f}s (lt={r['lt']:.2f}) "
                  f"可见 {r['vis']:.1f}%  脸 x={r['face_x']}  距边 {r['edge']}px")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        print(f"\n→ {a.json}")

    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
