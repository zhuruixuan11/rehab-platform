/* 动作可视化系统 v3：解剖级人物 + 肌肉发光 + 阶段标注
   muscleMapSVG(muscles) —— 前后视图解剖图谱（主发力红 / 协同蓝 + 图上中文标签）
   animSVG(anim, muscles) —— 解剖人物演示：灰白肌肉体型、目标肌群橙色发光、
                              顶部阶段胶囊、空间提示、易错点提示 */
import { escapeHtml } from "./app.js";

/* ================= 肌肉解剖图谱 ================= */

const ML = {
  chest: "胸大肌", lats: "背阔肌", traps: "斜方肌", delts: "三角肌",
  delt_ant: "三角肌前束", delt_post: "三角肌后束", biceps: "肱二头肌",
  triceps: "肱三头肌", forearm: "前臂肌群", abs: "腹直肌", obliques: "腹斜肌",
  lowerback: "竖脊肌", glutes: "臀大肌", quads: "股四头肌", hams: "腘绳肌",
  calves: "小腿三头肌",
};

const FRONT = [
  ["traps", '<path d="M96,52 L78,66 L96,76 Z"/>', false, 52, 60, "end"],
  ["delts", '<ellipse cx="72" cy="74" rx="13" ry="15"/>', false, 46, 72, "end"],
  ["delt_ant", '<path d="M76,66 L86,70 L82,84 L72,80 Z"/>', false, 126, 62, "start"],
  ["chest", '<path d="M98,76 C86,74 77,80 74,90 C71,101 74,111 82,114 C90,117 97,112 99,104 Z"/>', false, 50, 96, "end"],
  ["biceps", '<ellipse cx="59" cy="97" rx="8" ry="15"/>', false, 36, 97, "end"],
  ["forearm", '<path d="M52,122 L64,124 L60,168 L52,170 Z"/>', false, 32, 148, "end"],
  ["abs", '<rect x="90" y="126" width="9" height="17" rx="3"/><rect x="101" y="126" width="9" height="17" rx="3"/>' +
          '<rect x="90" y="147" width="9" height="17" rx="3"/><rect x="101" y="147" width="9" height="17" rx="3"/>' +
          '<rect x="90" y="168" width="9" height="16" rx="3"/><rect x="101" y="168" width="9" height="16" rx="3"/>',
   false, 152, 156, "start"],
  ["obliques", '<path d="M86,128 L92,126 L90,180 L84,178 Z"/>', false, 154, 132, "start"],
  ["quads", '<path d="M80,214 C74,235 76,262 80,286 L98,286 C99,262 98,235 99,216 Z"/>', false, 46, 252, "end"],
  ["calves", '<path d="M79,296 L93,296 L91,338 L84,354 L78,340 Z"/>', false, 44, 328, "end"],
];

const BACK = [
  ["traps", '<path d="M100,54 L124,68 L114,105 L100,118 L86,105 L76,68 Z"/>', true, 148, 84, "start"],
  ["delts", '<ellipse cx="72" cy="74" rx="13" ry="15"/>', false, 46, 72, "end"],
  ["delt_post", '<path d="M74,66 L64,70 L68,84 L78,80 Z"/>', false, 126, 62, "start"],
  ["lats", '<path d="M74,80 C68,105 74,135 86,152 C92,160 97,158 99,150 C95,130 94,105 99,84 Z"/>', false, 44, 118, "end"],
  ["triceps", '<ellipse cx="57" cy="100" rx="8" ry="16"/>', false, 36, 100, "end"],
  ["forearm", '<path d="M52,122 L64,124 L60,168 L52,170 Z"/>', false, 32, 148, "end"],
  ["lowerback", '<rect x="95" y="124" width="4" height="78" rx="2"/><rect x="101" y="124" width="4" height="78" rx="2"/>',
   true, 154, 158, "start"],
  ["glutes", '<path d="M78,196 C73,210 78,224 90,227 C97,229 100,222 100,214 L100,196 Z"/>', false, 46, 210, "end"],
  ["hams", '<path d="M80,232 C75,252 77,278 81,300 L97,300 C98,278 97,252 98,234 Z"/>', false, 44, 266, "end"],
  ["calves", '<path d="M79,310 L93,310 L92,344 C90,356 83,358 79,348 Z"/>', false, 44, 330, "end"],
];

function bodySilhouette(front) {
  return `
  <circle class="sil" cx="100" cy="30" r="16"/>
  <rect class="sil-fill" x="92" y="42" width="16" height="16" rx="5"/>
  <path class="sil-fill" d="M66,66 C58,90 64,120 72,136 C74,165 70,190 68,208 L132,208 C130,190 126,165 128,136 C136,120 142,90 134,66 C120,58 80,58 66,66 Z"/>
  <path class="sil-line" d="M66,68 L54,118 L50,168"/>
  <path class="sil-line" d="M134,68 L146,118 L150,168"/>
  <path class="sil-line thick" d="M84,205 L80,282 L78,358"/>
  <path class="sil-line thick" d="M116,205 L120,282 L122,358"/>
  <ellipse class="sil-fill" cx="78" cy="366" rx="11" ry="6"/>
  <ellipse class="sil-fill" cx="122" cy="366" rx="11" ry="6"/>
  ${front
    ? '<path class="sil-detail" d="M100,78 L100,122 M87,95 Q100,103 113,95"/>'
    : '<path class="sil-detail" d="M100,124 L100,192"/>'}`;
}

const MIRROR = 'matrix(-1,0,0,1,200,0)';

function muscleGroups(defs, primary, secondary) {
  return defs.map(([key, shape, center]) => {
    const cls = primary.includes(key) ? "pri" : secondary.includes(key) ? "sec" : "";
    const body = center ? shape : `${shape}<g transform="${MIRROR}">${shape}</g>`;
    return `<g class="mg ${cls}" data-m="${key}">${body}</g>`;
  }).join("");
}

function viewLabels(defs, primary, secondary) {
  return defs
    .filter((d) => d[3] !== undefined && (primary.includes(d[0]) || secondary.includes(d[0])))
    .map((d) => `<text class="mg-label ${primary.includes(d[0]) ? "pri" : "sec"}" x="${d[3]}" y="${d[4]}" text-anchor="${d[5] || "start"}">${ML[d[0]]}</text>`)
    .join("");
}

function oneView(defs, primary, secondary, label, front) {
  return `<svg viewBox="0 0 200 440" class="mm-svg">
    <text x="100" y="432" text-anchor="middle" class="mm-label">${label}</text>
    ${bodySilhouette(front)}
    ${muscleGroups(defs, primary, secondary)}
    ${viewLabels(defs, primary, secondary)}
  </svg>`;
}

export function muscleMapSVG(muscles) {
  const pri = (muscles?.primary || []).map((m) => m.key);
  const sec = (muscles?.secondary || []).map((m) => m.key);
  const frontPri = [...pri, ...(pri.includes("delts") || pri.includes("delt_ant") ? ["delts"] : [])];
  const frontSec = [...sec, ...(sec.includes("delts") || sec.includes("delt_ant") ? ["delts"] : [])];
  const backPri = [...pri, ...(pri.includes("delts") || pri.includes("delt_post") ? ["delts"] : [])];
  const backSec = [...sec, ...(sec.includes("delts") || sec.includes("delt_post") ? ["delts"] : [])];

  const priLabels = (muscles?.primary || []).map((m) => m.label).join("、");
  const secLabels = (muscles?.secondary || []).map((m) => m.label).join("、");

  return `
  <div class="mmap">
    <div class="mmap-views">
      ${oneView(FRONT, frontPri, frontSec, "前视图", true)}
      ${oneView(BACK, backPri, backSec, "后视图", false)}
    </div>
    <div class="mmap-legend">
      <span><i class="dot pri"></i>主发力${priLabels ? `：${escapeHtml(priLabels)}` : ""}</span>
      ${secLabels ? `<span><i class="dot sec"></i>协同发力：${escapeHtml(secLabels)}</span>` : ""}
    </div>
  </div>`;
}

/* ================= 解剖人物组件系统 ================= */

const STROKE = "#5B6472";
const EQUIP = "#3f3f5c";
const BAR = "#5b8cff";

let uid = 0;

function defsFor(id) {
  return `<defs>
    <linearGradient id="sk${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#F2F4F8"/><stop offset=".55" stop-color="#C6CCD8"/><stop offset="1" stop-color="#8E96A6"/>
    </linearGradient>
    <linearGradient id="fi${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFC06E"/><stop offset=".5" stop-color="#FF7A1A"/><stop offset="1" stop-color="#D9531E"/>
    </linearGradient>
    <linearGradient id="se${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFE9A8"/><stop offset="1" stop-color="#E8B23A"/>
    </linearGradient>
    <filter id="gl${id}" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="2.2" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>`;
}

const S = (v) => v.toFixed(1);

// 头（无面部，光头解剖模型）+ 颈
function head(cx, cy, r, id) {
  return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#sk${id})" stroke="${STROKE}" stroke-width="1.2"/>
    <ellipse cx="${cx}" cy="${S(cy + r * 0.45)}" rx="${r * 0.55}" ry="${r * 0.28}" fill="rgba(107,116,132,.18)"/>`;
}

// 肢体段：近端→远端锥形 + 单侧肌肉隆起。lv: 2=主发力(橙发光) 1=协同(黄) 0=普通
function limb(sx, sy, ex, ey, w1, w2, bulge, side, lv, id) {
  const dx = ex - sx, dy = ey - sy, L = Math.hypot(dx, dy) || 1;
  const nx = -dy / L, ny = dx / L;
  const hw = (t) => (w1 + (w2 - w1) * t) / 2;
  const A = `${S(sx - nx * w1 / 2)},${S(sy - ny * w1 / 2)}`;
  const B = `${S(ex - nx * w2 / 2)},${S(ey - ny * w2 / 2)}`;
  const C = `${S(ex + nx * w2 / 2)},${S(ey + ny * w2 / 2)}`;
  const D = `${S(sx + nx * w1 / 2)},${S(sy + ny * w1 / 2)}`;
  const t = 0.42;
  const M = `${S(sx + dx * t + nx * (hw(t) + bulge) * side)},${S(sy + dy * t + ny * (hw(t) + bulge) * side)}`;
  const fill = lv === 2 ? `url(#fi${id})` : lv === 1 ? `url(#se${id})` : `url(#sk${id})`;
  const glow = lv === 2 ? ` filter="url(#gl${id})"` : "";
  const cls = lv === 2 ? " mus-fire" : lv === 1 ? " mus-sec" : "";
  return `<path class="mus${cls}" d="M${A} L${B} L${C} Q${M} ${D} Z" fill="${fill}"${glow} stroke="${STROKE}" stroke-width="1"/>`;
}

// 关节衔接圆
function joint(cx, cy, r, id) {
  return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#sk${id})" stroke="${STROKE}" stroke-width="1"/>`;
}

// 解剖躯干：肩中心→髋中心，fires 内的肌群橙色发光
// 支持：chest 胸肌 / abs 腹肌 / lats 背阔 / delts 三角肌 / obliques 腹斜 / lowerback 竖脊 / glutes 臀
function torsoA(sx, sy, hx, hy, fires, id) {
  const dx = hx - sx, dy = hy - sy;
  const L = Math.hypot(dx, dy) || 1;
  const ang = Math.atan2(dy, dx) * 180 / Math.PI;
  const has = (k) => fires.includes(k);
  const F = `url(#fi${id})`;
  const D = "rgba(107,116,132,.30)";
  const block = (x, y, w, h, on) =>
    `<rect x="${S(x)}" y="${S(y)}" width="${S(w)}" height="${S(h)}" rx="2.5" fill="${on ? F : D}"${on ? ` filter="url(#gl${id})"` : ""} stroke="rgba(91,100,114,.45)" stroke-width="0.6" class="${on ? "mus-fire" : ""}"/>`;

  const outline = `M0,-15.5 C${S(L * .3)},-14.5 ${S(L * .55)},-10.5 ${S(L)},-12 L${S(L)},12 C${S(L * .55)},10.5 ${S(L * .3)},14.5 0,15.5 Z`;
  const cx = L * 0.05, cw = L * 0.27;                      // 胸肌区
  const abx = L * 0.42, abw = L * 0.48;                    // 腹肌区
  const rows = L > 62 ? 3 : 2;
  const abh = abw / (rows * 1.35);
  let blocks = "";
  blocks += block(cx, -12.8, cw, 12.3, has("chest"));
  blocks += block(cx, 0.5, cw, 12.3, has("chest"));
  for (let r = 0; r < rows; r++) {
    blocks += block(abx + r * abh * 1.35, -6.2, abh, 6, has("abs"));
    blocks += block(abx + r * abh * 1.35, 0.2, abh, 6, has("abs"));
  }
  blocks += block(L * .18, -15.2, L * .5, 4.4, has("lats"));   // 背阔上侧带
  blocks += block(L * .18, 10.8, L * .5, 4.4, has("lats"));
  blocks += block(-2.5, -16.5, L * .13, 6.5, has("delts"));    // 三角肌（肩端）
  blocks += block(-2.5, 10, L * .13, 6.5, has("delts"));
  blocks += block(L * .52, -13.8, L * .4, 3.6, has("obliques")); // 腹斜
  blocks += block(L * .52, 10.2, L * .4, 3.6, has("obliques"));
  blocks += block(L * .3, -5.4, L * .6, 4.6, has("lowerback")); // 竖脊（腰背中带）
  blocks += block(L * .88, -12.5, L * .14, 10.5, has("glutes"));
  blocks += block(L * .88, 2, L * .14, 10.5, has("glutes"));

  return `<g transform="translate(${S(sx)},${S(sy)}) rotate(${S(ang)})">
    <path d="${outline}" fill="url(#sk${id})" stroke="${STROKE}" stroke-width="1.2"/>
    <path d="M${S(L * .36)},0 L${S(L * .4)},0" stroke="${STROKE}" stroke-width=".8" opacity=".5"/>
    ${blocks}
  </g>`;
}

// 发力点脉冲标记
function fireMark(x, y, label) {
  return `<g class="firemark" transform="translate(${x},${y})">
    <circle class="fm-ring" r="13"/>
    <circle class="fm-pulse" r="13"/>
    <circle class="fm-dot" r="4.5"/>
    <path class="fm-line" d="M4,-5 L15,-16"/>
    <text class="fm-label" x="17" y="-15">发力点 · ${escapeHtml(label)}</text>
  </g>`;
}

/* 激光对齐线（参考图2：绿色垂直基准线 + 箭头 + 标签） */
function laser(x, y1, y2, label) {
  const mid = (y1 + y2) / 2;
  return `<g class="laser">
    <line x1="${S(x)}" y1="${S(y1)}" x2="${S(x)}" y2="${S(y2)}"/>
    <circle cx="${S(x)}" cy="${S(y1)}" r="2.5"/>
    <path d="M${S(x - 3.2)},${S(y2 - 6)} L${S(x)},${S(y2)} L${S(x + 3.2)},${S(y2 - 6)}"/>
    <text x="${S(x + 6)}" y="${S(mid)}">${escapeHtml(label)}</text>
  </g>`;
}

/* ================= 23 种动作模板 ================= */

const ANIMS = {
  bench: (id) => `
    <rect x="40" y="132" width="180" height="10" rx="3" fill="${EQUIP}"/>
    <rect x="60" y="142" width="8" height="52" fill="${EQUIP}"/><rect x="192" y="142" width="8" height="52" fill="${EQUIP}"/>
    ${head(62, 118, 10, id)}
    ${torsoA(74, 126, 158, 126, ["chest"], id)}
    ${limb(158, 126, 196, 152, 11, 8, 5, 1, 0, id)}
    ${limb(196, 152, 196, 192, 8, 6, 3, 1, 0, id)}
    ${joint(196, 152, 4, id)}
    <g class="g1">
      ${limb(100, 128, 100, 106, 10, 8, 3, 1, 0, id)}
      ${limb(100, 106, 100, 86, 8, 7, 2, -1, 1, id)}
      ${joint(100, 106, 4.5, id)}
    </g>
    <g class="g2"><path stroke="${BAR}" stroke-width="9" stroke-linecap="round" fill="none" d="M78,80 L122,80"/>
      <circle cx="78" cy="80" r="11" fill="${BAR}"/><circle cx="122" cy="80" r="11" fill="${BAR}"/></g>`,

  fly: (id) => `
    <rect x="75" y="150" width="110" height="9" rx="3" fill="${EQUIP}"/>
    <rect x="90" y="159" width="7" height="40" fill="${EQUIP}"/><rect x="163" y="159" width="7" height="40" fill="${EQUIP}"/>
    ${head(130, 58, 10, id)}
    ${torsoA(130, 70, 130, 148, ["chest"], id)}
    <text x="130" y="188" text-anchor="middle" class="mm-label">仰卧位示意</text>
    <g class="g1">${limb(118, 78, 118, 54, 9, 7, 3, -1, 0, id)}${limb(118, 54, 118, 32, 7, 6, 2, -1, 0, id)}
      <rect x="110" y="20" width="16" height="9" rx="3" fill="${BAR}"/></g>
    <g class="g2">${limb(142, 78, 142, 54, 9, 7, 3, 1, 0, id)}${limb(142, 54, 142, 32, 7, 6, 2, 1, 0, id)}
      <rect x="134" y="20" width="16" height="9" rx="3" fill="${BAR}"/></g>`,

  pulldown: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M84,16 L84,192 M176,16 L176,192"/>
    <path stroke="${EQUIP}" stroke-width="9" d="M80,14 L180,14"/>
    ${head(130, 46, 10, id)}
    ${torsoA(130, 57, 130, 122, ["lats"], id)}
    ${limb(130, 122, 176, 140, 11, 8, 4, -1, 0, id)}
    ${limb(176, 140, 176, 178, 8, 6, 3, -1, 0, id)}
    <rect x="118" y="124" width="66" height="8" rx="3" fill="${EQUIP}"/>
    <g class="g1">${limb(122, 76, 110, 52, 9, 7, 3, -1, 0, id)}${limb(110, 52, 102, 30, 7, 6, 2, -1, 1, id)}</g>
    <g class="g2">${limb(138, 76, 150, 52, 9, 7, 3, 1, 0, id)}${limb(150, 52, 158, 30, 7, 6, 2, 1, 1, id)}</g>
    <g class="g3"><path stroke="${BAR}" stroke-width="9" d="M92,26 L168,26"/>
      <circle cx="106" cy="26" r="6" fill="${BAR}"/><circle cx="154" cy="26" r="6" fill="${BAR}"/></g>`,

  row: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    ${head(168, 66, 10, id)}
    ${torsoA(160, 76, 108, 112, ["lats"], id)}
    ${limb(108, 112, 116, 158, 11, 8, 4, 1, 0, id)}
    ${limb(116, 158, 112, 196, 8, 6, 3, -1, 0, id)}
    <g class="g1">${limb(152, 84, 152, 108, 9, 7, 3, 1, 1, id)}${limb(152, 108, 152, 130, 7, 6, 2, 1, 0, id)}
      <path stroke="${BAR}" stroke-width="9" d="M136,132 L168,132"/>
      <circle cx="136" cy="132" r="10" fill="${BAR}"/><circle cx="168" cy="132" r="10" fill="${BAR}"/></g>`,

  deadlift: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    ${limb(116, 118, 130, 158, 12, 9, 5, 1, 0, id)}
    ${limb(130, 158, 124, 192, 9, 6, 4, 1, 0, id)}
    ${joint(130, 158, 4.5, id)}
    <path d="M124,192 L140,196" stroke="${STROKE}" stroke-width="5" stroke-linecap="round"/>
    <g class="g1">
      ${head(160, 52, 10, id)}
      ${torsoA(152, 62, 116, 118, ["lowerback", "glutes"], id)}
      ${limb(146, 68, 146, 120, 9, 7, 2.5, -1, 1, id)}
      <path stroke="${BAR}" stroke-width="9" d="M128,122 L164,122"/>
      <circle cx="128" cy="122" r="11" fill="${BAR}"/><circle cx="164" cy="122" r="11" fill="${BAR}"/>
    </g>`,

  squat: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    <g class="g3">${limb(134, 158, 124, 192, 9, 6, 4, 1, 0, id)}${joint(134, 158, 4.5, id)}
      <path d="M124,192 L140,196" stroke="${STROKE}" stroke-width="5" stroke-linecap="round"/></g>
    <g class="g2">${limb(118, 116, 134, 158, 13, 10, 6, 1, 2, id)}</g>
    <g class="g1">
      ${head(158, 44, 10, id)}
      ${torsoA(150, 54, 118, 116, ["glutes"], id)}
      ${limb(146, 58, 140, 66, 8, 6, 2, 1, 0, id)}
      <path stroke="${BAR}" stroke-width="9" d="M128,52 L168,52"/>
      <circle cx="128" cy="52" r="11" fill="${BAR}"/><circle cx="168" cy="52" r="11" fill="${BAR}"/>
    </g>`,

  legpress: (id) => `
    <rect x="46" y="126" width="72" height="10" rx="3" fill="${EQUIP}"/>
    <path stroke="${EQUIP}" stroke-width="9" fill="none" d="M58,126 L40,74"/>
    ${head(78, 112, 10, id)}
    ${torsoA(82, 118, 112, 130, [], id)}
    ${limb(112, 130, 160, 120, 12, 9, 5, -1, 2, id)}
    <g class="g1">${limb(160, 120, 204, 122, 9, 7, 3, -1, 0, id)}${joint(160, 120, 4.5, id)}
      <rect x="202" y="106" width="10" height="32" rx="3" fill="${BAR}"/></g>`,

  ohp: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    ${head(130, 46, 10, id)}
    ${torsoA(130, 58, 130, 108, ["delts"], id)}
    ${limb(130, 108, 127, 150, 11, 8, 4, 1, 0, id)}
    ${limb(127, 150, 127, 194, 8, 6, 3, 1, 0, id)}
    <g class="g1">
      ${limb(118, 60, 118, 38, 8, 6, 2.5, -1, 1, id)}${limb(118, 38, 118, 18, 6, 5, 1.5, -1, 0, id)}
      ${limb(142, 60, 142, 38, 8, 6, 2.5, 1, 1, id)}${limb(142, 38, 142, 18, 6, 5, 1.5, 1, 0, id)}
    </g>
    <g class="g2"><path stroke="${BAR}" stroke-width="9" d="M108,12 L152,12"/>
      <circle cx="108" cy="12" r="9" fill="${BAR}"/><circle cx="152" cy="12" r="9" fill="${BAR}"/></g>`,

  curl: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    ${head(130, 44, 10, id)}
    ${torsoA(130, 56, 130, 108, [], id)}
    ${limb(130, 108, 128, 150, 11, 8, 4, 1, 0, id)}
    ${limb(128, 150, 128, 194, 8, 6, 3, 1, 0, id)}
    ${limb(130, 58, 130, 90, 9, 7, 3, -1, 2, id)}
    <g class="g1">${limb(130, 90, 130, 126, 7, 6, 2, 1, 0, id)}${joint(130, 90, 4.5, id)}
      <rect x="121" y="126" width="18" height="9" rx="3" fill="${BAR}"/></g>`,

  pushdown: (id) => `
    <circle cx="130" cy="20" r="9" fill="none" stroke="${EQUIP}" stroke-width="4"/>
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M130,29 L130,56"/>
    ${head(142, 58, 10, id)}
    ${torsoA(138, 68, 134, 108, [], id)}
    ${limb(134, 108, 132, 150, 11, 8, 4, 1, 0, id)}
    ${limb(132, 150, 132, 194, 8, 6, 3, 1, 0, id)}
    ${limb(138, 70, 138, 100, 9, 7, 3, 1, 2, id)}
    <g class="g1">${limb(138, 100, 138, 136, 7, 6, 2, 1, 0, id)}${joint(138, 100, 4.5, id)}
      <rect x="129" y="136" width="18" height="9" rx="3" fill="${BAR}"/></g>`,

  plank: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    <g class="g1">
      ${head(182, 150, 10, id)}
      ${torsoA(176, 160, 100, 160, ["abs"], id)}
      ${limb(172, 162, 168, 194, 8, 6, 2, 1, 0, id)}
      ${limb(100, 160, 92, 194, 8, 6, 2, 1, 0, id)}
      <ellipse cx="138" cy="152" rx="22" ry="9" fill="rgba(91,140,255,.35)"/>
    </g>`,

  crunch: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    ${limb(120, 178, 88, 158, 10, 8, 4, 1, 0, id)}
    ${limb(88, 158, 92, 196, 8, 6, 3, 1, 0, id)}
    <g class="g1">
      ${head(186, 170, 10, id)}
      ${torsoA(178, 176, 120, 178, ["abs"], id)}
      ${limb(176, 182, 164, 168, 6, 5, 1.5, 1, 0, id)}
    </g>`,

  run: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    ${head(130, 38, 10, id)}
    ${torsoA(130, 50, 126, 98, [], id)}
    <g class="g5">${limb(128, 56, 116, 90, 8, 6, 2.5, 1, 0, id)}</g>
    <g class="g6">${limb(128, 56, 140, 90, 8, 6, 2.5, -1, 0, id)}</g>
    <g class="g1">${limb(126, 98, 142, 136, 11, 8, 4, 1, 2, id)}${limb(142, 136, 134, 174, 8, 6, 3, 1, 0, id)}
      <path d="M134,174 L146,178" stroke="${STROKE}" stroke-width="5" stroke-linecap="round"/></g>
    <g class="g2">${limb(126, 98, 110, 136, 11, 8, 4, -1, 0, id)}${limb(110, 136, 118, 174, 8, 6, 3, -1, 2, id)}
      <path d="M118,174 L106,178" stroke="${STROKE}" stroke-width="5" stroke-linecap="round"/></g>`,

  bike: (id) => `
    <circle cx="80" cy="170" r="24" fill="none" stroke="${EQUIP}" stroke-width="6"/>
    <circle cx="178" cy="170" r="24" fill="none" stroke="${EQUIP}" stroke-width="6"/>
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M80,170 L128,140 L178,170 M128,140 L112,122 M178,170 L188,120"/>
    <rect x="98" y="112" width="28" height="8" rx="3" fill="${EQUIP}"/>
    ${head(148, 82, 10, id)}
    ${torsoA(142, 92, 112, 122, ["quads"], id)}
    <g class="g3">${limb(112, 122, 136, 150, 10, 8, 4, 1, 2, id)}${limb(136, 150, 124, 174, 7, 6, 3, 1, 0, id)}</g>
    <g class="g4">${limb(112, 122, 128, 158, 10, 8, 4, -1, 2, id)}${limb(128, 158, 142, 174, 7, 6, 3, -1, 0, id)}</g>
    <g class="g1"><path stroke="${EQUIP}" stroke-width="4" d="M80,152 L80,188 M62,170 L98,170"/></g>
    <g class="g2"><path stroke="${EQUIP}" stroke-width="4" d="M178,152 L178,188 M160,170 L196,170"/></g>`,

  elliptical: (id) => `
    <circle cx="152" cy="152" r="26" fill="none" stroke="${EQUIP}" stroke-width="7"/>
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M40,196 L200,196 M152,152 L120,110 M152,152 L184,116 M184,116 L196,96"/>
    <rect x="106" y="98" width="30" height="8" rx="3" fill="${EQUIP}"/>
    ${head(118, 52, 10, id)}
    ${torsoA(114, 62, 110, 102, ["quads"], id)}
    ${limb(110, 102, 124, 140, 11, 8, 4, 1, 2, id)}
    ${limb(124, 140, 112, 172, 8, 6, 3, 1, 0, id)}
    <g class="g5">${limb(112, 58, 128, 92, 8, 6, 2.5, 1, 0, id)}</g>
    <g class="g6">${limb(112, 58, 98, 92, 8, 6, 2.5, -1, 0, id)}</g>`,

  dips: (id) => `
    <path stroke="${EQUIP}" stroke-width="9" d="M130,56 L130,190"/>
    <g class="g1">
      ${head(130, 44, 10, id)}
      ${torsoA(130, 54, 130, 116, ["chest"], id)}
      ${limb(130, 116, 142, 146, 9, 7, 3, 1, 1, id)}
      ${limb(142, 146, 128, 168, 7, 6, 2, 1, 0, id)}
      ${joint(142, 146, 4.5, id)}
    </g>
    <circle cx="128" cy="170" r="5" fill="${BAR}"/>`,

  legcurl: (id) => `
    <rect x="40" y="118" width="150" height="9" rx="3" fill="${EQUIP}"/>
    ${head(55, 108, 10, id)}
    ${torsoA(65, 114, 140, 114, [], id)}
    ${limb(140, 114, 182, 114, 10, 8, 4, -1, 2, id)}
    <g class="g1">${limb(182, 114, 182, 158, 8, 6, 3, 1, 0, id)}
      <rect x="176" y="160" width="12" height="8" rx="3" fill="${BAR}"/></g>`,

  calfraise: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    <g class="g1">
      ${head(130, 44, 11, id)}
      ${torsoA(130, 56, 130, 108, [], id)}
      ${limb(130, 108, 128, 150, 12, 9, 5, 1, 0, id)}
      ${limb(128, 150, 128, 186, 9, 6, 4, 1, 2, id)}
      ${joint(128, 150, 4.5, id)}
    </g>
    <circle cx="142" cy="196" r="5" fill="${BAR}"/>`,

  lateral: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    ${head(130, 46, 10, id)}
    ${torsoA(130, 58, 130, 120, ["delts"], id)}
    ${limb(120, 122, 118, 160, 10, 8, 4, 1, 0, id)}${limb(118, 160, 118, 194, 8, 6, 3, 1, 0, id)}
    ${limb(140, 122, 142, 160, 10, 8, 4, -1, 0, id)}${limb(142, 160, 142, 194, 8, 6, 3, -1, 0, id)}
    <g class="g1">${limb(118, 62, 118, 102, 7, 6, 2, -1, 1, id)}
      <rect x="110" y="102" width="16" height="9" rx="3" fill="${BAR}"/></g>
    <g class="g2">${limb(142, 62, 142, 102, 7, 6, 2, 1, 1, id)}
      <rect x="134" y="102" width="16" height="9" rx="3" fill="${BAR}"/></g>`,

  skullcrusher: (id) => `
    <rect x="40" y="132" width="180" height="10" rx="3" fill="${EQUIP}"/>
    <rect x="60" y="142" width="8" height="52" fill="${EQUIP}"/><rect x="192" y="142" width="8" height="52" fill="${EQUIP}"/>
    ${head(62, 118, 10, id)}
    ${torsoA(74, 126, 158, 126, [], id)}
    ${limb(158, 126, 196, 152, 11, 8, 5, 1, 0, id)}${limb(196, 152, 196, 192, 8, 6, 3, 1, 0, id)}
    ${limb(100, 128, 100, 94, 9, 7, 3, 1, 2, id)}
    <g class="g1">${limb(100, 94, 100, 60, 7, 6, 2, 1, 0, id)}${joint(100, 94, 4.5, id)}
      <circle cx="100" cy="56" r="10" fill="${BAR}"/></g>`,

  legraise: (id) => `
    <path stroke="${EQUIP}" stroke-width="9" d="M70,26 L190,26"/>
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M84,26 L84,10 M176,26 L176,10"/>
    ${limb(105, 30, 105, 78, 7, 6, 2, -1, 0, id)}${limb(155, 30, 155, 78, 7, 6, 2, 1, 0, id)}
    ${head(130, 66, 10, id)}
    ${torsoA(130, 76, 130, 130, ["abs"], id)}
    <g class="g1">${limb(122, 130, 122, 182, 10, 8, 4, 1, 0, id)}${limb(138, 130, 138, 182, 10, 8, 4, -1, 0, id)}
      <path d="M122,182 L118,190 M138,182 L142,190" stroke="${STROKE}" stroke-width="5" stroke-linecap="round"/></g>`,

  twist: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    ${limb(120, 178, 150, 164, 10, 8, 4, 1, 0, id)}${limb(150, 164, 150, 196, 8, 6, 3, 1, 0, id)}
    <g class="g1">
      ${head(112, 118, 10, id)}
      ${torsoA(108, 128, 100, 180, ["obliques"], id)}
      ${limb(108, 130, 138, 140, 7, 6, 2, 1, 0, id)}
      <circle cx="150" cy="142" r="9" fill="${BAR}"/>
    </g>`,

  jump: (id) => `
    <path stroke="${EQUIP}" stroke-width="5" fill="none" d="M20,196 L240,196"/>
    <g class="g1">
      ${head(130, 44, 11, id)}
      ${torsoA(130, 56, 130, 108, [], id)}
      ${limb(124, 60, 116, 84, 7, 6, 2, -1, 0, id)}${limb(136, 60, 144, 84, 7, 6, 2, 1, 0, id)}
      ${limb(130, 108, 128, 150, 12, 9, 5, 1, 0, id)}
      ${limb(128, 150, 128, 188, 9, 6, 4, 1, 2, id)}
    </g>
    <g class="g2"><path stroke="${BAR}" stroke-width="5" fill="none" stroke-dasharray="5 5" d="M116,86 C90,120 90,160 128,190"/></g>
    <g class="g3"><path stroke="${BAR}" stroke-width="5" fill="none" stroke-dasharray="5 5" d="M144,86 C170,50 170,20 130,14 C100,10 96,44 116,86"/></g>`,
};

const MARKS = {
  bench: [[104, 112]], fly: [[130, 96]], pulldown: [[130, 88]], row: [[132, 94]],
  deadlift: [[122, 126]], squat: [[126, 140]], legpress: [[136, 124]], ohp: [[130, 66]],
  curl: [[122, 76]], pushdown: [[144, 86]], plank: [[140, 158]], crunch: [[150, 172]],
  run: [[134, 120]], bike: [[124, 136]], elliptical: [[116, 124]], dips: [[130, 80]],
  legcurl: [[160, 112]], calfraise: [[122, 168]], lateral: [[130, 66]],
  skullcrusher: [[100, 108]], legraise: [[130, 106]], twist: [[104, 152]],
  jump: [[124, 168]],
};

/* 相位残影：动作另一端位置的半透明定格（参考图1 双相位同屏，一目了然） */
const GHOSTS = {
  curl: (id) => `<g class="ghost" transform="rotate(-130 130 90)">${limb(130, 90, 130, 126, 7, 6, 2, 1, 0, id)}<rect x="121" y="126" width="18" height="9" rx="3" fill="${EQUIP}"/></g>`,
  pushdown: (id) => `<g class="ghost" transform="rotate(-75 138 100)">${limb(138, 100, 138, 136, 7, 6, 2, 1, 0, id)}<rect x="129" y="136" width="18" height="9" rx="3" fill="${EQUIP}"/></g>`,
  skullcrusher: (id) => `<g class="ghost" transform="rotate(-80 100 94)">${limb(100, 94, 100, 60, 7, 6, 2, 1, 0, id)}<circle cx="100" cy="56" r="10" fill="${EQUIP}"/></g>`,
  lateral: (id) => `<g class="ghost" transform="rotate(-82 118 62)">${limb(118, 62, 118, 102, 7, 6, 2, -1, 0, id)}<rect x="110" y="102" width="16" height="9" rx="3" fill="${EQUIP}"/></g><g class="ghost" transform="rotate(82 142 62)">${limb(142, 62, 142, 102, 7, 6, 2, 1, 0, id)}<rect x="134" y="102" width="16" height="9" rx="3" fill="${EQUIP}"/></g>`,
  fly: (id) => `<g class="ghost" transform="rotate(-78 118 78)">${limb(118, 78, 118, 54, 9, 7, 3, -1, 0, id)}${limb(118, 54, 118, 32, 7, 6, 2, -1, 0, id)}<rect x="110" y="20" width="16" height="9" rx="3" fill="${EQUIP}"/></g><g class="ghost" transform="rotate(78 142 78)">${limb(142, 78, 142, 54, 9, 7, 3, 1, 0, id)}${limb(142, 54, 142, 32, 7, 6, 2, 1, 0, id)}<rect x="134" y="20" width="16" height="9" rx="3" fill="${EQUIP}"/></g>`,
  legcurl: (id) => `<g class="ghost" transform="rotate(70 182 114)">${limb(182, 114, 182, 158, 8, 6, 3, 1, 0, id)}<rect x="176" y="160" width="12" height="8" rx="3" fill="${EQUIP}"/></g>`,
  pulldown: () => `<g class="ghost" transform="translate(0 64)"><path stroke="${EQUIP}" stroke-width="9" d="M92,26 L168,26"/><circle cx="106" cy="26" r="6" fill="${EQUIP}"/><circle cx="154" cy="26" r="6" fill="${EQUIP}"/></g>`,
  ohp: () => `<g class="ghost" transform="translate(0 40)"><path stroke="${EQUIP}" stroke-width="9" d="M108,12 L152,12"/><circle cx="108" cy="12" r="9" fill="${EQUIP}"/><circle cx="152" cy="12" r="9" fill="${EQUIP}"/></g>`,
  row: (id) => `<g class="ghost" transform="translate(0 -26) rotate(18 152 84)">${limb(152, 84, 152, 108, 9, 7, 3, 1, 0, id)}${limb(152, 108, 152, 130, 7, 6, 2, 1, 0, id)}<path stroke="${EQUIP}" stroke-width="9" d="M136,132 L168,132"/><circle cx="136" cy="132" r="10" fill="${EQUIP}"/><circle cx="168" cy="132" r="10" fill="${EQUIP}"/></g>`,
};

/* 激光基准线（参考图2：绿色对齐线） */
const LASERS = {
  bench: () => laser(100, 70, 108, "杠铃垂直轨迹"),
  squat: () => laser(144, 46, 188, "重心线"),
  deadlift: () => laser(140, 114, 188, "杠贴小腿"),
};

export const ANIM_META = {
  bench: "离心下放 2-3s → 触胸 → 爆发推起 1s",
  fly: "张开吸气感受拉伸 → 合拢呼气挤压",
  pulldown: "背阔肌发力下拉 → 顶峰挤压 1s → 离心回放 2-3s",
  row: "拉至下腹 → 挤压肩胛 1s → 缓慢下放",
  deadlift: "屈髋俯身 → 全身绷紧拉起 → 顶端站直呼气",
  squat: "下蹲吸气 2-3s（大腿至少平行）→ 蹬地站起呼气",
  legpress: "下放至膝约 90° 吸气 → 蹬起呼气（不锁膝）",
  ohp: "上推呼气 → 下放回锁骨位吸气",
  curl: "弯举呼气挤压 1s → 离心下放 3s",
  pushdown: "下压呼气顶峰收缩 → 回放至前臂平行地面",
  plank: "静态保持 · 自然呼吸不憋气",
  crunch: "卷起呼气挤压腹肌 → 下放吸气",
  run: "两步一吸两步一呼 · 落地脚掌中部",
  bike: "踏频 80-110rpm · 匀速深呼吸",
  elliptical: "手脚协同 · 全程匀速深呼吸",
  dips: "下降吸气 2s（大臂平行地面）→ 撑起呼气",
  legcurl: "弯起呼气顶峰收缩 → 下放吸气 3s",
  calfraise: "踮起呼气顶端停 1s → 下落吸气拉伸",
  lateral: "举至与肩同高呼气 → 离心下放 3s",
  skullcrusher: "屈肘下放吸气 → 伸直呼气（肘部固定不动）",
  legraise: "抬腿呼气卷动骨盆 → 下落吸气控制不摆动",
  twist: "左右匀速转体 · 自然呼吸不憋气",
  jump: "前脚掌弹性落地 · 匀速浅快呼吸",
};

const PHASES = {
  bench: ["离心下放 · 吸气", "爆发推起 · 呼气"],
  fly: ["外展拉伸 · 吸气", "环抱挤压 · 呼气"],
  pulldown: ["离心回放 · 吸气", "下拉挤背 · 呼气"],
  row: ["缓慢回放 · 吸气", "拉向腹部 · 呼气"],
  deadlift: ["俯身下放 · 吸气", "站直锁定 · 呼气"],
  squat: ["下蹲到底 · 吸气", "蹬地站起 · 呼气"],
  legpress: ["下放至 90° · 吸气", "蹬起不锁膝 · 呼气"],
  ohp: ["下放至锁骨 · 吸气", "上推过头 · 呼气"],
  curl: ["离心下放 · 吸气", "弯举挤压 · 呼气"],
  pushdown: ["回放拉伸 · 吸气", "下压锁定 · 呼气"],
  plank: ["自然呼吸 · 保持", "核心收紧 · 保持"],
  crunch: ["下放肩胛 · 吸气", "卷起挤压 · 呼气"],
  run: ["摆腿前蹬 · 吸气", "提拉后摆 · 呼气"],
  bike: ["下踩发力 · 吸气", "提拉回收 · 呼气"],
  elliptical: ["前推 · 吸气", "后拉 · 呼气"],
  dips: ["下降拉伸 · 吸气", "撑起挤压 · 呼气"],
  legcurl: ["离心下放 · 吸气", "弯起收缩 · 呼气"],
  calfraise: ["下落拉伸 · 吸气", "踮起顶峰 · 呼气"],
  lateral: ["离心下放 · 吸气", "侧举至肩高 · 呼气"],
  skullcrusher: ["屈肘下放 · 吸气", "伸臂锁定 · 呼气"],
  legraise: ["下落控制 · 吸气", "抬腿卷骨盆 · 呼气"],
  twist: ["转体左侧 · 呼气", "转体右侧 · 吸气"],
  jump: ["弹性落地 · 吸气", "腾空跃起 · 呼气"],
};

const TIP_META = {
  bench: "杠铃在乳头线上方，小臂始终垂直地面",
  fly: "想象环抱大树，肘部微屈锁死角度",
  pulldown: "横杠拉至上胸，身体微后仰约 10°",
  row: "杠铃贴大腿拉向下腹，肘部贴近身体",
  deadlift: "杠铃贴小腿上行，肩胛在杠铃正上方",
  squat: "膝盖对准脚尖方向，重心落在脚掌中部",
  legpress: "膝盖对准脚尖，腰部贴紧靠垫",
  ohp: "杠铃推至头顶正上方，肋骨下沉收腹",
  curl: "肘部固定贴身，只有前臂在移动",
  pushdown: "大臂夹紧身体，只有肘关节运动",
  plank: "从头到脚一条直线，收紧臀腹",
  crunch: "下巴与胸口保持一拳距离，不抱头猛拉",
  run: "身体微前倾，落地点在重心正下方",
  bike: "踏板画圆，膝盖不外八不内扣",
  elliptical: "全脚掌贴踏板，脚跟不下垂",
  dips: "身体略前倾，下降至上臂平行地面",
  legcurl: "臀部贴紧板面，骨盆稳定不动",
  calfraise: "全幅度升降，顶端停顿 1 秒",
  lateral: "肘部领先带动，举至与肩同高",
  skullcrusher: "肘部指向天花板固定不动",
  legraise: "下背贴地，靠腹力而非惯性摆动",
  twist: "转动来自胸椎，骨盆保持朝前",
  jump: "手腕发力摇绳，前脚掌落地缓冲",
};

const WARN_META = {
  bench: "腰部塌陷、杠铃弹胸借力、手腕过度后翻",
  fly: "肘部完全锁死变卧推、下放过深拉伤肩关节",
  pulldown: "身体过度后仰借力、只用二头肌拉",
  row: "弓腰、耸肩、圆背拉起",
  deadlift: "弓背起拉、杠铃离身太远、顶端过度后仰",
  squat: "膝盖内扣、脚跟离地、蹲不到大腿平行",
  legpress: "膝盖完全锁死、腰部离开靠垫",
  ohp: "腰部前顶代偿、杠铃推到头顶前方",
  curl: "甩动身体借力、肘部前后移动",
  pushdown: "肘部外飘、耸肩、用身体重量下压",
  plank: "塌腰、撅臀、憋气",
  crunch: "双手抱头猛拉颈部、靠惯性起身",
  run: "步幅过大、脚跟重砸、含胸驼背",
  bike: "座椅过高或过低、阻力过大伤膝",
  elliptical: "脚尖踮起、重心过度前倾",
  dips: "耸肩紧张、下降过深伤肩、身体远离双杠",
  legcurl: "臀部抬起借力、动作过快无控制",
  calfraise: "膝盖弯曲借力、动作幅度过小",
  lateral: "耸肩、甩动借力、举得过高超过头顶",
  skullcrusher: "肘部外飘、杠铃向面部下放过快",
  legraise: "腰部借力摆动、双腿下放过快",
  twist: "转动过快靠惯性、腰部弓起",
  jump: "全脚掌重砸落地、绳子长度不合适",
};

export function phaseChipsHTML(anim) {
  const phases = PHASES[anim] || [];
  return phases.length
    ? `<div class="stage-chips">${phases.map((p, i) => `<span class="stage-chip ${i ? "show-b" : "show-a"}">✔ ${p}</span>`).join("")}</div>`
    : "";
}

export function animSVG(anim, muscles) {
  const builder = ANIMS[anim];
  if (!builder) return "";
  const id = ++uid;
  const label = muscles?.primary?.[0]?.label;
  const m = (MARKS[anim] || [])[0];
  const mark = m ? fireMark(m[0], m[1], label || "主发力") : "";
  const chips = phaseChipsHTML(anim);
  const ghost = GHOSTS[anim] ? GHOSTS[anim](id) : "";
  const laserLine = LASERS[anim] ? LASERS[anim]() : "";
  const ghostNote = ghost ? `<div class="ghost-note">◌ 灰色虚影 = 动作另一端位置</div>` : "";
  return `
  <div class="exanim" data-anim="${anim}">
    ${chips}
    <svg viewBox="0 0 260 210">${defsFor(id)}${ghost}${builder(id)}${mark}${laserLine}</svg>
    ${ghostNote}
    <div class="exanim-tip">💡 ${TIP_META[anim] || ""}</div>
    <div class="exanim-phase">${ANIM_META[anim] || ""}</div>
    ${WARN_META[anim] ? `<div class="exanim-warn">⚠️ 易错点：${WARN_META[anim]}</div>` : ""}
  </div>`;
}
