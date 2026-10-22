/* timeline.js — 时间轴模板（把每个切点绑到实测拍子上）
 *
 * 原则：
 *   ⛔ 不许写整秒（42 / 48 / 54）。整秒一定偏，偏 0.2s 就听得出来。
 *   ✅ 先跑音频分析拿 BPM / downbeat，再用 beat 数算切点。
 *   ✅ 每镜只保留 6 个必填参数（素材/景别/落点/遮罩形态/音频驱动量/歌词），
 *      其余都是推导出来的。参数越多，越容易自欺（"我调过了"）。
 *
 * 覆盖 7 种遮罩形态（同一语法不重复自己）：
 *   竖带张开 → 横带收窄 → 竖带反向 → 极窄横带（只留一个器官） → 裂开成全屏 →
 *   无遮罩（hero，全片仅一次） → 闭合到一条线
 */
(() => {
  'use strict';
  const Z = window.Z;

  Z.TITLE = 'TITLE';
  Z.TITLE_SUB = '';
  Z.ARTIST = '';

  Z.setup = async () => {
    // 全片后处理基线：先全关，需要哪一层再逐镜开。
    // ⛔ 不要默认开 grain / bloom —— "颗粒常开"是风格，但基线必须是可控的 0
    Z.LOOK_DEFAULT = {
      boil: 0, bloom: 0, grain: 0, vignette: 0, lutMix: 0,
      ca: 0, glitch: 0, zoomBlur: 0, flash: 0, invert: 0, fade: 0, letterbox: 0,
    };

    // ---- 实测参数（换成你自己的；⛔ 别抄，一定要自己量）----
    const T0 = 40.00;        // 段落起点 = impacts 里的 downbeat，不是整秒
    const BEAT = 0.3659;     // 1 拍 = 60 / BPM（BPM 要带小数，全曲常在缓慢加速）
    const at = n => +(T0 + n * BEAT).toFixed(3);
    const END = at(64);      // 64 拍 = 16 小节

    const A = 'assets/char/';
    const BG_A = '#5C1B30';  // 主角底色
    const BG_B = '#C1637D';  // 对手戏底色（⛔ 两者明度差要够，否则切过去像没切）
    const INK = '#FBF3E6';
    const STROKE = '#68615D';
    const EDGE = '#B05672';

    const S = [];
    const shot = (id, b0, b1, args, extra = {}) =>
      S.push(Object.assign({ id, t0: at(b0), t1: at(b1), scene: 'band', args, lyric: 'none' }, extra));

    /* S1 · 0–8 拍 · 竖带从左张开：她躲着看。窄 → 中，两次缓开。 */
    shot('S1', 0, 8, {
      char: A + '01.png', bg: BG_A, hFrac: 0.88, cx: 700, cy: 470,
      band: {
        dir: 'v',
        segs: [
          { at: [0.00, 1.10], from: 180, to: 420, center: 326, ease: 'outExpo' },
          { at: [1.10, 2.75], from: 420, to: 720, c0: 326, c1: 420, ease: 'inOutSine' },
        ],
      },
      edge: EDGE, breatheBand: 26, onsetGlow: 0.5,
      lines: [
        { text: '第一句', x: 1008, y: 872, size: 110, fam: 'serif', at: [0.20, 0.65], color: INK, stroke: STROKE },
        { text: '歌词上半', x: 1008, y: 1004, size: 110, fam: 'serif', at: [0.75, 1.20], color: INK, stroke: STROKE },
      ],
    });

    /* S2 · 8–17 拍 · 横带收到胸口那一条：全片唯一「人在右」构图，字幕镜像到左。 */
    shot('S2', 8, 17, {
      char: A + '02.png', bg: BG_A, hFrac: 1.00, cx: 1101, cy: 550,
      band: {
        dir: 'h',
        segs: [
          { at: [0.00, 1.20], from: 520, to: 520, center: 700, ease: 'linear' },
          { at: [1.20, 2.60], from: 520, to: 440, center: 700, ease: 'inOutSine' },
        ],
      },
      edge: EDGE, breatheBand: 34, onsetGlow: 0.9,
      lines: [
        { text: '第二句', x: 100, y: 790, size: 180, fam: 'serif', at: [0.30, 0.85], color: INK, stroke: STROKE, strokeW: 5 },
        { text: '歌词下半', x: 100, y: 972, size: 180, fam: 'serif', at: [0.90, 1.45], color: INK, stroke: STROKE, strokeW: 5 },
      ],
    });

    /* S3 · 17–24 拍 · 竖带从右收窄并左移：同一句词，一开一合。 */
    shot('S3', 17, 24, {
      char: A + '03.png', bg: BG_A, hFrac: 0.88, cx: 1023, cy: 470,
      band: {
        dir: 'v',
        segs: [
          { at: [0.00, 0.85], from: 760, to: 700, c0: 900, c1: 700, ease: 'inOutSine' },
          { at: [0.85, 2.45], from: 700, to: 640, center: 700, ease: 'inOutSine' },
        ],
      },
      edge: EDGE, breatheBand: 26, onsetGlow: 0.5,
      lines: [{ text: '第三句', x: 96, y: 872, size: 110, fam: 'serif', at: [0.25, 0.70], color: INK, stroke: STROKE }],
    });

    /* S4 · 24–33 拍 · 极窄横带只留一个器官（180–300px），然后扩开。
     * ⛔ 窄到这个程度，qc_scan 的 min_slit 会跳过它 —— 这是设计，不是漏洞。 */
    shot('S4', 24, 33, {
      char: A + '04.png', bg: BG_A, hFrac: 1.00, cx: 1120, cy: 540,
      band: {
        dir: 'h',
        segs: [
          { at: [0.00, 1.05], from: 300, to: 300, center: 612, ease: 'linear' },
          { at: [1.05, 2.95], from: 300, to: 660, center: 612, ease: 'outExpo' },
        ],
      },
      edge: EDGE, breatheBand: 18, onsetGlow: 1.0,
      lines: [{ text: '第四句', x: 110, y: 872, size: 110, fam: 'serif', at: [0.55, 1.00], color: INK, stroke: STROKE }],
    });

    /* S5a · 33–40 拍 · 横带裂开成全屏 —— 她想说，所以门开了。
     * 全片第一次也是唯一一次接近无遮罩，必须留给情绪的顶点。 */
    shot('S5a', 33, 40, {
      char: A + '05.png', bg: BG_A, hFrac: 0.92, cx: 1090, cy: 500,
      band: {
        dir: 'h',
        segs: [
          { at: [0.00, 0.30], from: 540, to: 540, center: 540, ease: 'linear' },
          { at: [0.30, 0.95], from: 540, to: 1080, center: 540, ease: 'outExpo' },
        ],
      },
      edge: EDGE, breatheBand: 40, onsetGlow: 0.7,
      lines: [{ text: '第五句', x: 1008, y: 742, size: 180, fam: 'serif', at: [0.45, 0.95], color: INK, stroke: STROKE, strokeW: 5 }],
    }, { trans: { type: 'flash', dur: 0.2 } });

    /* S5b · 40–48 拍 · 换人：带从右推入，换一个人在带的另一边。
     * ⛔ 与 S5a 之间只能硬切（trans 不写 = 硬切）。遮罩镜头之间做 xfade，
     *    两条反向的带会同时存在 → 画面出现「十字」。这是事故，不是转场。 */
    shot('S5b', 40, 48, {
      char: A + '06.png', bg: BG_B, hFrac: 0.92, cx: 1104, cy: 500,
      band: {
        dir: 'v',
        segs: [{ at: [0.00, 1.10], from: 0, to: 1500, c0: 1920, c1: 1170, ease: 'outExpo' }],
      },
      edge: EDGE, breatheBand: 30, onsetGlow: 0.6,
      lines: [{ text: '第六句', x: 110, y: 972, size: 60, fam: 'serif', at: [0.55, 1.05], color: INK, stroke: STROKE, strokeW: 2 }],
    });

    /* S6 · 48–55 拍 · HERO：遮罩消失，她直接看向观众。
     * 破格三件事：无遮罩 + 全帧率（koma 30）+ 不呼吸（breatheBand 0）。
     * ⭐ 静止才让前面的动读得出来。这一镜是全片的"full hold"。 */
    shot('S6', 48, 55, {
      char: A + '07.png', bg: BG_A, hFrac: 1.27, cx: 943, cy: 540,
      band: { dir: 'none' },
      edge: EDGE, breatheBand: 0, onsetGlow: 0.0,
      koma: 30,
    }, { trans: { type: 'black', dur: 0.8 } });

    /* S7 · 55–64 拍 · 遮罩闭合到一条线（≈10px），最后 0.1s 淡黑。
     * 收尾必须是「减法」：把带关掉，而不是加一个更亮的画面。 */
    shot('S7', 55, 64, {
      char: A + '08.png', bg: BG_A, hFrac: 1.05, cx: 694, cy: 567,
      band: {
        dir: 'h',
        segs: [{ at: [0.10, 1.55], from: 1080, to: 10, center: 540, ease: 'inOutSine' }],
      },
      edge: EDGE, breatheBand: 12, onsetGlow: 0.8,
      lines: [
        { text: 'I CAN T', x: 100, y: 930, size: 37, fam: 'sans', weight: 300, at: [0.20, 0.55], color: INK, stroke: STROKE, strokeW: 2 },
        { text: 'BREATHE', x: 100, y: 984, size: 37, fam: 'sans', weight: 300, at: [0.57, 0.92], color: INK, stroke: STROKE, strokeW: 2 },
      ],
    }, {
      post: (Sv) => ({ fade: Z.clamp((Sv.t - (END - 0.10)) / 0.10) }),
    });

    Z.SHOTS = S;
    window.__zankoMeta.duration = END + 0.51;   // 留 0.5s 尾巴，别硬切断音频
  };
})();
