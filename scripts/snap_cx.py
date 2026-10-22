#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""snap_cx.py — 把「脸要落在哪」换算成 sprite 的 cx / cy

⛔ 这是整条管线最容易错的一步，且肉眼几乎发现不了：
   sprite 的锚点是**图像中心**，而 probe_bbox.py 量的是**人物 bbox 中心**。
   直接把 bbox_cx 填进 cx，人物会整体偏移 sx = (bbox_cx − img_w/2) × k，
   实测偏移 90–300px —— 表现是「人被切没了」「贴边」「只剩一片背景」。

正解（k = sprite_w / img_w）：
    face_x = cx − sprite_w/2 + bbox_cx × k
    cx     = face_x + (0.5 − bbox_cx / img_w) × sprite_w

用法:
    # 我要脸落在 x=700，hFrac=1.00，求 cx
    python snap_cx.py --bbox bbox.json --img 05 --hfrac 1.00 --target-x 700

    # 已知 cx=1120，反查脸落在哪
    python snap_cx.py --bbox bbox.json --img 05 --hfrac 1.00 --cx 1120

    # 批量审计：每一镜的脸落点 + 出界告警
    python snap_cx.py --bbox bbox.json --shots qc.json
"""
import argparse
import json
import sys


def load_images(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("images", d)


def face_x(cx, sw, bcx, img_w):
    return cx - sw / 2 + bcx * (sw / img_w)


def face_y(cy, sh, bcy, img_h):
    return cy - sh / 2 + bcy * (sh / img_h)


def cx_for(target_x, sw, bcx, img_w):
    return target_x + (0.5 - bcx / img_w) * sw


def cy_for(target_y, sh, bcy, img_h):
    return target_y + (0.5 - bcy / img_h) * sh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="probe_bbox.py 产出的 bbox.json")
    ap.add_argument("--canvas", default="1920x1080")
    ap.add_argument("--img", help="bbox.json 里的图 key")
    ap.add_argument("--hfrac", type=float, help="人物高 = 画布高 × 此值")
    ap.add_argument("--cx", type=float, help="已知 sprite cx，反查脸位置")
    ap.add_argument("--cy", type=float)
    ap.add_argument("--target-x", type=float, help="想要的脸 x → 求 cx")
    ap.add_argument("--target-y", type=float, help="想要的脸 y → 求 cy")
    ap.add_argument("--shots", help="批量审计 qc.json")
    ap.add_argument("--margin", type=float, default=180.0, help="距画布边缘安全距离")
    a = ap.parse_args()

    W, H = (int(v) for v in a.canvas.lower().split("x"))
    images = load_images(a.bbox)

    def make(img, hfrac):
        if img not in images:
            print(f"⛔ bbox.json 里没有 {img}；可用：{', '.join(sorted(images))}")
            sys.exit(1)
        img_w, img_h = images[img]["size"]
        bcx, bcy = images[img]["box"][0], images[img]["box"][1]
        sh = hfrac * H
        k = sh / img_h
        return img_w, img_h, bcx, bcy, img_w * k, sh

    # ---------- 批量审计 ----------
    if a.shots:
        with open(a.shots, encoding="utf-8") as f:
            spec = json.load(f)
        bbox_override = spec.get("bbox")
        print(f"{'镜':<6}{'图':<8}{'hFrac':>7}{'sprite_w':>10}{'cx':>7}{'脸 x':>8}"
              f"{'脸 y':>8}{'距边':>8}  判定")
        print("-" * 74)
        bad = 0
        for s in spec["shots"]:
            key = s["img"]
            if bbox_override and key in bbox_override:
                images[key] = bbox_override[key]
            img_w, img_h, bcx, bcy, sw, sh = make(key, s["hFrac"])
            fx = face_x(s["cx"], sw, bcx, img_w)
            fy = face_y(s["cy"], sh, bcy, img_h)
            edge = min(fx, W - fx)
            flag = ""
            if fx < 0 or fx > W:
                flag = "⛔ 脸在画布外"
            elif edge < a.margin:
                flag = "⚠ 贴边"
            if flag:
                bad += 1
            print(f"{s['id']:<6}{key:<8}{s['hFrac']:>7.2f}{sw:>10.0f}{s['cx']:>7.0f}"
                  f"{fx:>8.0f}{fy:>8.0f}{edge:>8.0f}  {flag}")
        print()
        if bad:
            print(f"⚠ {bad} 个镜头需要改 cx：用 --target-x <设计位置> 求出正确值")
        else:
            print("✅ 所有镜头脸都在安全区内")
        return

    # ---------- 单张换算 ----------
    if not a.img or a.hfrac is None:
        ap.error("单张模式需要 --img 与 --hfrac")
    img_w, img_h, bcx, bcy, sw, sh = make(a.img, a.hfrac)

    print(f"图        : {a.img}（{img_w}×{img_h}）  bbox 中心 = ({bcx}, {bcy})")
    print(f"sprite_w  : {sw:.1f}   sprite_h: {sh:.1f}   k = {sw / img_w:.4f}")
    print()

    if a.target_x is not None:
        need = cx_for(a.target_x, sw, bcx, img_w)
        print(f"目标脸 x={a.target_x:.0f} → cx = {need:.1f}")
        print(f"   校验：face_x({need:.1f}) = {face_x(need, sw, bcx, img_w):.1f}")
    if a.target_y is not None:
        need_y = cy_for(a.target_y, sh, bcy, img_h)
        print(f"目标脸 y={a.target_y:.0f} → cy = {need_y:.1f}")
        print(f"   校验：face_y({need_y:.1f}) = {face_y(need_y, sh, bcy, img_h):.1f}")
    if a.cx is not None:
        fx = face_x(a.cx, sw, bcx, img_w)
        print(f"cx={a.cx:.0f} → 脸落在 x = {fx:.0f}（距边 {min(fx, W - fx):.0f}px）")
        if 0 <= fx <= W and min(fx, W - fx) < a.margin:
            print(f"   ⚠ 低于安全边距 {a.margin:.0f}px")
        elif not (0 <= fx <= W):
            print("   ⛔ 脸在画布外")
    if a.cy is not None and a.target_y is None:
        print(f"cy={a.cy:.0f} → 脸落在 y = {face_y(a.cy, sh, bcy, img_h):.0f}")
    if a.cx is None and a.target_x is None and a.target_y is None:
        print("（只给了 --cy；补 --cx 或 --target-x 才能验证落点）")

    # 反向提示：直接拿 bbox 中心当 cx 会偏多少
    print()
    print("参考：如果直接把 bbox_cx 当 cx，脸会落在 "
          f"x = {face_x(bcx, sw, bcx, img_w):.0f}（偏 {face_x(bcx, sw, bcx, img_w) - bcx:.0f}px）")


if __name__ == "__main__":
    main()
