/* scenes/band.js — 遮罩带（mask band）场景模板
 *
 * 依赖：vocaloid-style-mv-pipeline 引擎（window.Z 命名空间）。
 *       换引擎版本先核对 Z.draw.sprite / Z.ease / Z.quant / Z.imgSync 是否同名。
 *
 * 语法：画面永远被一条「带」切分。带内是人物，带外是暗。
 *       带的宽度 = 情绪的量度（愿意被看见的程度 / 距离 / 呼吸）。
 *       ⭐ 带是**遮罩不是缩放** ⇒ 天然无损；配纯色背景可无限延展，
 *          人物缩放可以 <1，全片永不上采样。这是它比"推近镜头"强的唯一原因。
 *
 * args: {
 *   char:    'assets/char/01.png'   人物图
 *   bg:      '#5C1B30'              带内背景色（纯色，靠它才敢放大裁切）
 *   outside: 0.46                   带外压暗系数：bg 混黑的比例。⛔ 不要留"空"，要是"暗"
 *   hFrac:   0.88                   人物高 = 画布高 × 此值
 *   cx, cy:  860, 470               人物 bbox 中心落在画布的位置（⛔ 用 snap_cx.py 算）
 *   face:    [0.5, 0.5]             bbox 内「脸」的相对位置（默认 bbox 中心）
 *   band: {                         ⭐ 遮罩带
 *     dir:  'v' | 'h' | 'none'      竖带 / 横带 / 无遮罩（全屏，只给 hero 用一次）
 *     segs: [{ at:[lt0, lt1], from:px, to:px, center:px | c0/c1, ease:'outExpo' }]
 *   },
 *   edge:        '#B05672'          带边缘 2px 色
 *   koma:        12                 绘制层帧率（コマ打ち）。摄影机/字幕不受影响
 *   breatheBand: 26                 音频低频驱动的带宽抖动（0 = 静）
 *   onsetGlow:   0.5                强拍瞬间带内提亮（0 = 关）
 *   fgChar:      false              true = 人物进前景层 ⇒ 歌词从她身后穿过
 *   lines: [{ text, x, y, size, fam, weight, color, stroke, strokeW, align, at:[a,b] }]
 * }
 */
(() => {
  'use strict';
  const Z = window.Z, D = Z.draw, E = Z.ease, W = 1920, H = 1080;

  // 字体必须显式预热：不预热的话第 0 帧会掉回 fallback，逐帧对比时看起来像"抖动"
  const GLYPHS = '在这里放全片会用到的字 0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ';

  Z.scene('band', {
    preload: a => [a.char].filter(Boolean),

    init: async () => {
      try {
        await document.fonts.load('400 100px "Noto Serif JP"', GLYPHS);
        await document.fonts.load('300 100px "Noto Sans JP"', GLYPHS);
      } catch (e) { /* 字体缺失不该阻断渲染 */ }
    },

    draw(ctx, S) {
      const a = S.args, lt = S.lt;
      const bg = a.bg || '#5C1B30';

      // ---------- 1. 带外：暗，不是空 ----------
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; ctx.filter = 'none';
      const dk = Z.mix3(Z.hex(bg), [0, 0, 0], a.outside != null ? a.outside : 0.46);
      ctx.fillStyle = `rgb(${dk[0] | 0},${dk[1] | 0},${dk[2] | 0})`;
      ctx.fillRect(0, 0, W, H);

      // ---------- 2. 求遮罩矩形 ----------
      const bd = a.band || { dir: 'none' };
      let rx = 0, ry = 0, rw = W, rh = H;
      if (bd.dir === 'v' || bd.dir === 'h') {
        const segs = bd.segs || [{ at: [0, 1], from: 180, to: 720 }];
        let seg = segs[0];
        for (let i = segs.length - 1; i >= 0; i--) {
          if (lt >= segs[i].at[0]) { seg = segs[i]; break; }
        }
        const k = (E[seg.ease || 'outExpo'])(Z.inv(seg.at[0], seg.at[1], lt));
        let v = Z.lerp(seg.from, seg.to, k);
        // 每镜只需一个音频驱动的量：低频 → 带宽。没有作画素材时，这是唯一的"活"
        if (S.env && a.breatheBand) v += a.breatheBand * (S.env.low(S.t) - 0.28) * 2.2;
        v = Math.max(2, v);
        const dflt = bd.dir === 'v' ? W / 2 : H / 2;
        const c0 = seg.c0 != null ? seg.c0 : (seg.center != null ? seg.center : dflt);
        const c1 = seg.c1 != null ? seg.c1 : (seg.center != null ? seg.center : dflt);
        const c = Z.lerp(c0, c1, k);
        if (bd.dir === 'v') { rx = c - v / 2; rw = v; }
        else { ry = c - v / 2; rh = v; }
      }

      // ---------- 3. 带内：人物（可选进前景层） ----------
      const tgt = (a.fgChar && S.fg) ? S.fg : ctx;
      tgt.save();
      tgt.beginPath(); tgt.rect(rx, ry, rw, rh); tgt.clip();
      if (!(a.fgChar && S.fg)) { tgt.fillStyle = bg; tgt.fillRect(0, 0, W, H); }
      if (a.char) {
        const h = (a.hFrac != null ? a.hFrac : 0.88) * H;
        const cx = a.cx != null ? a.cx : W / 2;
        const cy = a.cy != null ? a.cy : H / 2;
        const img = Z.imgSync(a.char);
        if (img) {
          // ⭐ 绘制层 12fps（コマ打ち）；摄影机与光走全帧率。副歌强拍上可把本镜 koma 设 30
          const tq = Z.quant(lt, a.koma || 12);
          D.sprite(tgt, img, cx, cy + h / 2, h, { t: tq, breathe: a.breathe || 0, sway: a.sway || 0 });
        }
      }
      tgt.restore();

      // ---------- 4. 强拍提亮（只作用带内，不碰字幕） ----------
      if (S.env && a.onsetGlow) {
        const g = Math.max(0, S.env.onset(S.t) - 0.25) * a.onsetGlow;
        if (g > 0.004) {
          ctx.save();
          ctx.beginPath(); ctx.rect(rx, ry, rw, rh); ctx.clip();
          ctx.globalCompositeOperation = 'lighter';
          ctx.fillStyle = `rgba(255,240,225,${Math.min(0.22, g)})`;
          ctx.fillRect(0, 0, W, H);
          ctx.restore();
        }
      }

      // ---------- 5. 带边：2px 硬边（不加发光，发光会让"切口"变成"特效"） ----------
      if (bd.dir === 'v' || bd.dir === 'h') {
        ctx.save();
        ctx.strokeStyle = a.edge || '#B05672';
        ctx.lineWidth = 2;
        ctx.beginPath();
        if (bd.dir === 'v') {
          ctx.moveTo(rx, 0); ctx.lineTo(rx, H);
          ctx.moveTo(rx + rw, 0); ctx.lineTo(rx + rw, H);
        } else {
          ctx.moveTo(0, ry); ctx.lineTo(W, ry);
          ctx.moveTo(0, ry + rh); ctx.lineTo(W, ry + rh);
        }
        ctx.stroke();
        ctx.restore();
      }

      // ---------- 6. 歌词：永远落在带外（天然安全区） ----------
      if (a.lines) for (const L of a.lines) {
        const rv = L.at ? Z.clamp(Z.inv(L.at[0], L.at[1], lt)) : 1;
        if (rv <= 0.001) continue;
        D.htext(ctx, L.text, L.x, L.y, {
          size: L.size || 110,
          fam: L.fam || 'serif',
          weight: L.weight || 400,
          color: L.color || '#FBF3E6',
          stroke: L.stroke || '#68615D',
          strokeW: L.strokeW || 3,
          align: L.align || 'left',
          reveal: rv,
          spacing: L.spacing != null ? L.spacing : 0,
        });
      }

      // ---------- 7. 角标（可选：时间码 / 计数器） ----------
      if (a.hud) {
        ctx.save();
        ctx.globalAlpha = 0.55;
        D.htext(ctx, a.hud.text, a.hud.x, a.hud.y, {
          size: a.hud.size || 19, fam: 'dot', weight: 400, color: '#FBF3E6', align: 'left',
        });
        ctx.restore();
      }
    },
  });
})();
