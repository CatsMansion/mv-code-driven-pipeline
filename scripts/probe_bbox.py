#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_bbox.py — 量角色立绘的可用几何：bbox / 留白列 / 与背景的明度差

为什么需要它：分镜里写的是「脸落在 x=700」，但引擎画的是 sprite（锚点=图像中心）。
两者不等价，中间要靠实测 bbox 换算（见 snap_cx.py）。手写 bbox 一定错。

输出 bbox.json，供 qc_scan.py / snap_cx.py 直接读。

用法:
    python probe_bbox.py --dir assets/char --out bbox.json
    python probe_bbox.py --dir assets/char --thresh 42 --min-free 60

判定口径:
    背景色 = 四角+四边中点共 9 个 patch 里标准差最低的那个的均值
    前景   = 与背景色的 RGB 距离 > --thresh 的像素
    bbox   = 前景像素的紧致包围盒（不是 alpha 通道；立绘是不透明 PNG）
    留白列 = 非前景像素占比 < 8% 的最长连续列区间（放字幕用）
    Δlum   = |前景均色亮度 − 背景色亮度|，做描边/压暗时的可读性下限
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

SUPPORTED = (".png", ".webp", ".jpg", ".jpeg")


def _lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _bg_color(a):
    """扫 9 个边缘 patch，取标准差最低者作为背景色。"""
    h, w = a.shape[:2]
    ps = []
    for fy in (0.02, 0.5, 0.98):
        for fx in (0.02, 0.5, 0.98):
            y0, x0 = int(h * fy) - 12, int(w * fx) - 12
            patch = a[max(0, y0):y0 + 24, max(0, x0):x0 + 24].reshape(-1, 3)
            if len(patch):
                ps.append((float(patch.std()), patch.mean(0)))
    ps.sort(key=lambda x: x[0])
    return ps[0][1]


def _longest_free_run(free):
    best, cur = (0, 0), None
    for i, v in enumerate(free):
        if v:
            cur = i if cur is None else cur
        else:
            if cur is not None and i - cur > best[1] - best[0]:
                best = (cur, i)
            cur = None
    if cur is not None and len(free) - cur > best[1] - best[0]:
        best = (cur, len(free))
    return best


def probe(path, thresh=42.0, min_free=60, free_ratio=0.08):
    """返回单张图的几何字典；检测失败返回 None。"""
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    h, w = a.shape[:2]
    bg = _bg_color(a)
    mask = np.linalg.norm(a - bg[None, None, :], axis=2) > thresh
    ys, xs = np.nonzero(mask)
    if len(xs) < 500:
        return None
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    colfg = mask.mean(axis=0)
    fx0, fx1 = _longest_free_run(colfg < free_ratio)
    if fx1 - fx0 < min_free:
        fx0, fx1 = -1, -1          # 留白不足，等于「放不下字幕」
    fg = a[mask].mean(0)
    return {
        "file": os.path.basename(path),
        "size": [w, h],
        "box": [cx, cy, x1 - x0, y1 - y0],   # bbox 中心 + 宽高（qc_scan 口径）
        "bounds": [x0, y0, x1, y1],
        "bg": "#%02X%02X%02X" % tuple(int(v) for v in bg),
        "free_cols": [fx0, fx1],
        "free_width": max(0, fx1 - fx0),
        "dlum": round(float(abs(_lum(fg) - _lum(bg))), 1),
        "coverage": round(float(mask.mean()) * 100, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="立绘目录")
    ap.add_argument("--out", default="bbox.json")
    ap.add_argument("--thresh", type=float, default=42.0, help="前景判定 RGB 距离阈值")
    ap.add_argument("--min-free", type=int, default=60, help="可放字幕的最小留白宽度(px)")
    ap.add_argument("--min-dlum", type=float, default=76.0, help="Δlum 低于此值给告警")
    a = ap.parse_args()

    files = []
    for ext in SUPPORTED:
        files += glob.glob(os.path.join(a.dir, "*" + ext))
        files += glob.glob(os.path.join(a.dir, "*" + ext.upper()))
    files = sorted(set(files))
    if not files:
        print(f"⛔ {a.dir} 下没有找到图片")
        sys.exit(1)

    print(f"{'file':<30}{'bg':<10}{'bbox(cx,cy)':<16}{'w×h':<13}"
          f"{'留白列':<18}{'Δlum':<8}{'覆盖%'}")
    print("-" * 108)
    out, warn = {}, []
    for f in files:
        r = probe(f, a.thresh, a.min_free)
        if r is None:
            print(f"{os.path.basename(f):<30}检测失败（前景像素 < 500，检查阈值）")
            warn.append((os.path.basename(f), "检测失败"))
            continue
        key = os.path.splitext(os.path.basename(f))[0]
        out[key] = r
        free = "[-, -]" if r["free_width"] == 0 else f"[{r['free_cols'][0]}, {r['free_cols'][1]}]"
        print(f"{r['file']:<30}{r['bg']:<10}"
              f"({r['box'][0]:4d},{r['box'][1]:4d})  "
              f"{r['box'][2]:4d}×{r['box'][3]:<6d}{free:<18}"
              f"{float(r['dlum']):<8.1f}{r['coverage']}")
        if r["dlum"] < a.min_dlum:
            warn.append((key, f"Δlum {r['dlum']} < {a.min_dlum}，深色背景上会糊"))
        if r["free_width"] == 0:
            warn.append((key, f"留白 < {a.min_free}px，这一张放不下字幕（别硬塞）"))

    with open(a.out, "w", encoding="utf-8") as fp:
        json.dump({
            "note": "由 probe_bbox.py 生成；box = [bbox_cx, bbox_cy, w, h]",
            "thresh": a.thresh,
            "images": out,
        }, fp, ensure_ascii=False, indent=2, default=float)   # numpy 标量统一转 float
    print(f"\n→ {a.out}（{len(out)} 张）")

    if warn:
        print("\n⚠ 需要按分镜处理：")
        for k, msg in warn:
            print(f"   {k}: {msg}")
    else:
        print("✅ 全部素材可放字幕、明度差达标")


if __name__ == "__main__":
    main()
