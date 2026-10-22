#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pack_handover.py — 打交接包，并且**当场证明它不是空包**

背景：交接包最容易出的事故不是"漏文件"，是"包能解开但对方跑不起来"——
  少一个 analysis/*.json、少一张素材、少一行映射说明。发出去之后才发现，
  代价是多一轮往返。
所以打包必须自带重建验证（rebuild check）：解包到临时目录，逐文件比 sha256，
  正反两个方向都对齐，才允许发。

用法:
    python pack_handover.py --dir handover_pack --out pack.zip
    python pack_handover.py --dir handover_pack --out pack.zip --manifest 文件清单.txt
    python pack_handover.py --dir handover_pack --out pack.zip --verify-cmd "python tools/qc_scan.py --spec qc.json"

退出码: 0 = 打包且验证通过；1 = 验证不一致（包不可发）；2 = 输入有问题。
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".idea", ".vscode"}
SKIP_FILES = {".DS_Store", "Thumbs.db", "last_run.txt"}


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def walk(root):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            if fn in SKIP_FILES:
                continue
            full = os.path.join(dp, fn)
            out.append((os.path.relpath(full, root).replace("\\", "/"), full))
    return out


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="已排好目录结构的交接包根目录")
    ap.add_argument("--out", required=True, help="输出 zip 路径")
    ap.add_argument("--manifest", help="包内生成的文件清单名（如 文件清单.txt）")
    ap.add_argument("--verify-cmd", help="在解包目录里执行的额外验证命令（重建验证）")
    ap.add_argument("--keep-temp", action="store_true", help="保留解包目录便于排查")
    a = ap.parse_args()

    root = os.path.abspath(a.dir)
    if not os.path.isdir(root):
        print(f"⛔ 目录不存在：{root}")
        sys.exit(2)

    files = walk(root)
    if not files:
        print("⛔ 目录里没有文件")
        sys.exit(2)

    # ---------- 清单 ----------
    if a.manifest:
        lines = ["路径\t字节\tsha256(前16)"]
        for rel, full in files:
            lines.append(f"{rel}\t{os.path.getsize(full)}\t{sha256(full)[:16]}")
        mf = os.path.join(root, a.manifest)
        with open(mf, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        print(f"清单 : {a.manifest}（{len(files)} 条）")
        files = walk(root)          # 清单本身也要进包

    # ---------- 打包 ----------
    total = sum(os.path.getsize(f) for _, f in files)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel, full in files:
            z.write(full, rel)
    zsize = os.path.getsize(a.out)
    print(f"打包 : {len(files)} 文件 / 原始 {human(total)} → {human(zsize)}")
    print(f"       {os.path.abspath(a.out)}")
    print(f"       zip sha256 {sha256(a.out)[:16]}")

    # ---------- 重建验证 ----------
    tmp = tempfile.mkdtemp(prefix="packcheck_")
    src_map = {rel: sha256(full) for rel, full in files}
    ok = True
    try:
        with zipfile.ZipFile(a.out) as z:
            z.extractall(tmp)
        dst_map = {rel: sha256(full) for rel, full in walk(tmp)}
        missing = sorted(set(src_map) - set(dst_map))
        extra = sorted(set(dst_map) - set(src_map))
        diff = sorted(k for k in set(src_map) & set(dst_map) if src_map[k] != dst_map[k])
        print()
        print(f"重建 : 解出 {len(dst_map)} 文件")
        if missing or extra or diff:
            ok = False
            print(f"⛔ 不一致：缺 {len(missing)} / 多 {len(extra)} / 内容不同 {len(diff)}")
            for k in (missing + extra + diff)[:10]:
                print("   ", k)
        else:
            print(f"✅ 逐字节一致 {len(dst_map)} / {len(src_map)}")

        if a.verify_cmd:
            print(f"\n验证命令：{a.verify_cmd}")
            r = subprocess.run(a.verify_cmd, shell=True, cwd=tmp,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            tail = (r.stdout or "").strip().splitlines()[-12:]
            for line in tail:
                print("   ", line)
            if r.returncode != 0:
                ok = False
                print(f"⛔ 验证命令 rc={r.returncode}")
                for line in (r.stderr or "").strip().splitlines()[-6:]:
                    print("   ", line)
            else:
                print("✅ 验证命令 rc=0")
    finally:
        if a.keep_temp:
            print(f"\n解包目录保留在：{tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("可以发货" if ok else "⛔ 不要发：包不完整或跑不起来")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
