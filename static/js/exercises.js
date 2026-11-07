import { api } from "./api.js";
import { toast, openModal, closeModal, escapeHtml } from "./app.js";
import { muscleMapSVG, phaseChipsHTML } from "./exercise-visual.js";

const BILI_SEARCH = "https://search.bilibili.com/all?keyword=";

/* 真人教学视频（id → mp4 路径数组，可登记多个示范），后续新增视频在此登记 */
const VIDEO_EX = {
  1: ["/videos/ex_1.mp4", "/videos/ex_1_2.mp4", "/videos/ex_1_3.mp4", "/videos/ex_1_4.mp4", "/videos/ex_1_5.mp4"],
  3: ["/videos/ex_3.mp4"],
  4: ["/videos/ex_4.mp4"],
  5: ["/videos/ex_5.mp4"],
  6: ["/videos/ex_6.mp4"],
  7: ["/videos/ex_7.mp4"],
  8: ["/videos/ex_8.mp4"],
  9: ["/videos/ex_9.mp4"],
  10: ["/videos/ex_10.mp4"],
  11: ["/videos/ex_11.mp4"],
  12: ["/videos/ex_12.mp4"],
  13: ["/videos/ex_13.mp4"],
  14: ["/videos/ex_14.mp4"],
  15: ["/videos/ex_15.mp4"],
  16: ["/videos/ex_16.mp4"],
  17: ["/videos/ex_17.mp4"],
  18: ["/videos/ex_18.mp4"],
  19: ["/videos/ex_19.mp4"],
  20: ["/videos/ex_20.mp4"],
  21: ["/videos/ex_21.mp4"],
  22: ["/videos/ex_22.mp4"],
  24: ["/videos/ex_24.mp4"],
  25: ["/videos/ex_25.mp4"],
  26: ["/videos/ex_26.mp4"],
  27: ["/videos/ex_27.mp4"],
  28: ["/videos/ex_28.mp4"],
  29: ["/videos/ex_29.mp4"],
  30: ["/videos/ex_30.mp4"],
  31: ["/videos/ex_31.mp4"],
  32: ["/videos/ex_32.mp4"],
  33: ["/videos/ex_33.mp4"],
  34: ["/videos/ex_34.mp4"],
};

const CAT_ICON = {
  "肩部": "🙆", "肘腕": "🤲", "颈腰椎": "🧍", "胸背": "🧘", "核心躯干": "🎯",
  "髋部": "🦴", "膝部": "🦵", "踝足": "🦶", "平衡步态": "⚖️", "心肺全身": "🏃",
};
const CATS = ["肩部", "肘腕", "颈腰椎", "胸背", "核心躯干", "髋部", "膝部", "踝足", "平衡步态", "心肺全身"];
const DIFF = { 1: "早期", 2: "中期", 3: "后期" };
const DIFF_TAG = { 1: "green", 2: "", 3: "red" };

/* 3D 解剖肌群定位图（AI 生成） */
const MUS_ATLAS = {
  "胸大肌": "chest", "背阔肌": "lats", "肱二头肌": "biceps", "肱三头肌": "triceps",
  "三角肌": "delts", "三角肌前束": "delts_front", "三角肌后束": "delts_rear",
  "腹直肌": "abs", "腹斜肌": "obliques", "股四头肌": "quads", "腘绳肌": "hams",
  "臀大肌": "glutes", "小腿三头肌": "calves", "竖脊肌": "erector", "斜方肌": "traps", "前臂肌群": "forearms",
};

function atlasHTML(muscles) {
  if (!muscles) return "";
  const prim = muscles.primary || [];
  const sec = muscles.secondary || [];
  const cells = prim.filter((m) => MUS_ATLAS[m.label]).map((m) => `
    <div class="mus-cell">
      <img src="/images/ex3d/mus_${MUS_ATLAS[m.label]}.jpg" alt="${escapeHtml(m.label)} 3D解剖肌群定位图" loading="lazy" onerror="this.closest('.mus-cell').style.display='none'">
      <div class="mus-cap">🔴 ${escapeHtml(m.label)} · 主发力</div>
    </div>`).join("");
  const secTags = sec.length ? `<div class="mus-sec"><span>灰白显影 · 协同肌：</span>${sec.map((m) => `<span class="tag gray">${escapeHtml(m.label)}</span>`).join(" ")}</div>` : "";
  if (!cells) return muscleMapSVG(muscles) ? `<div class="card" style="box-shadow:none;padding:12px">${muscleMapSVG(muscles)}</div>` : "";
  return `<div class="mus-grid">${cells}</div>${secTags}`;
}

export async function viewExercises(el) {
  let cat = "", diff = "", q = "";

  async function load() {
    const params = new URLSearchParams();
    if (cat) params.set("category", cat);
    if (diff) params.set("difficulty", diff);
    if (q) params.set("q", q);
    let list = [], is_member = false, total_paid = 0;
    try {
      const res = await api(`/api/student/exercises?${params}`);
      if (Array.isArray(res)) { list = res; is_member = true; }
      else { ({ items: list, is_member, total_paid } = res); }
    } catch (err) {
      grid.innerHTML = `<div class="empty"><span class="ico">⚠️</span>${escapeHtml(err.message)}</div>`;
      return;
    }
    const unlock_banner = !is_member && total_paid > list.length
      ? `<div class="card mb-16" style="background:linear-gradient(135deg, rgba(46,139,132,0.15), rgba(99,184,174,0.1));border-color:rgba(46,139,132,0.4);display:flex;justify-content:space-between;align-items:center">
           <div><b>🔒 免费版仅展示 ${list.length} 个基础动作，还有 ${total_paid - list.length} 个高级动作等你解锁！</b>
           <div style="color:var(--text-2);font-size:12px;margin-top:4px">升级会员解锁全部 ${total_paid} 个动作 + B站教学视频 + AI动作点评</div></div>
           <a class="btn warn" href="#/member">升级会员 ⭐</a>
         </div>` : "";
    grid.innerHTML = unlock_banner + (list.length ? `<div class="grid cols-3">${list.map((e) => `
      <div class="card ex-card" data-ex='${JSON.stringify(e).replace(/'/g, "&#39;")}' style="cursor:pointer;padding:18px">
        <div class="flex between">
          <span style="font-size:26px">${CAT_ICON[e.category] || "🏋️"}</span>
          <div class="flex" style="gap:6px">
            ${e.video_url ? '<span class="tag purple" title="含B站教学视频">🎬 B站教学</span>' : ""}
            ${e.is_member_only ? '<span class="tag warn">会员专属</span>' : ""}
            <span class="tag ${DIFF_TAG[e.difficulty]}">${DIFF[e.difficulty]}</span>
          </div>
        </div>
        <div style="font-weight:700;font-size:16px;margin-top:10px">${escapeHtml(e.name)}</div>
        <div class="flex wrap" style="gap:6px;margin-top:6px">
          <span class="tag">${escapeHtml(e.category)}</span>
          <span class="tag gray">${escapeHtml(e.equipment || "自重")}</span>
        </div>
        <div style="color:var(--text-2);font-size:12px;margin-top:10px;line-height:1.6" class="ex-intro">
          ${escapeHtml(e.intro || "点击查看动作详解")}
        </div>
        <div style="color:var(--primary);font-size:12px;margin-top:10px">查看动作详解 →</div>
      </div>`).join("")}</div>`
      : `<div class="empty"><span class="ico">🔍</span>没有符合条件的动作，换个筛选试试</div>`);

    grid.querySelectorAll(".ex-card").forEach((c) => {
      c.onclick = () => openDetail(JSON.parse(c.dataset.ex));
    });
  }

  function openDetail(e) {
    const steps = (e.steps || "").split("\n").filter(Boolean).map((s) => s.replace(/^\d+[.、]\s*/, ""));
    const tips = (e.tips || "").split("\n").filter(Boolean).map((t) => t.replace(/^[·\s]+/, ""));
    const muscles = e.muscles && e.muscles.primary ? e.muscles : null;
    const videos = e.anim ? (VIDEO_EX[e.id] || []) : [];
    const has3d = !!e.anim;
    const atlasHtml = atlasHTML(muscles);

    openModal({
        title: `${CAT_ICON[e.category] || "🏋️"} ${e.name}`,
        wide: true,
        content: `
          <div class="flex wrap mb-16">
            <span class="tag">${escapeHtml(e.category)}</span>
            <span class="tag ${DIFF_TAG[e.difficulty]}">${DIFF[e.difficulty]}</span>
            <span class="tag gray">器械：${escapeHtml(e.equipment || "自重")}</span>
            <span class="tag purple">参考安排：${e.default_sets} 组 × ${e.default_reps} 次${Number(e.default_weight) ? ` · ${e.default_weight}kg` : ""}</span>
            ${videos.length ? `<span class="tag green">含真人教学视频${videos.length > 1 ? ` ×${videos.length}` : ""}</span>` : ""}
          </div>
          <p style="font-size:14px;line-height:1.7">${escapeHtml(e.intro || "")}</p>
          <div class="exdetail mt-16">
            <div>
              <div class="exv-tabs">
                ${has3d ? '<button class="vt active" data-v="3d">🧍 3D解剖图解</button>' : ""}
                ${videos.length ? `<button class="vt ${has3d ? "" : "active"}" data-v="video">🎬 教学视频</button>` : ""}
              </div>
              ${has3d ? `<div class="exv-pane" data-p="3d" style="--aspd:3s">
                ${phaseChipsHTML(e.anim)}
                <div class="ex3d-anim">
                  <img class="f-a" src="/images/ex3d/ex_${e.id}.jpg" alt="${escapeHtml(e.name)} 3D解剖教学图 姿态一" loading="lazy">
                  <img class="f-m" src="/images/ex3d/ex_${e.id}_m.jpg" alt="${escapeHtml(e.name)} 3D解剖教学图 过渡姿态" loading="lazy">
                  <img class="f-b" src="/images/ex3d/ex_${e.id}_b.jpg" alt="${escapeHtml(e.name)} 3D解剖教学图 姿态二" loading="lazy">
                </div>
                <div class="exanim-controls">
                  <button class="btn ghost sm" id="ex-3d-toggle">⏸ 暂停</button>
                  <button class="btn ghost sm" id="ex-3d-speed">🐢 慢速精学</button>
                </div>
                <div class="ghost-note">🎞 3D解剖人物三帧乒乓循环（起始 → 过渡 → 收缩）· 与阶段提示同步</div>
              </div>` : `<div class="ghost-note" style="margin-top:4px">🩺 康复动作以规范姿势与安全为先，请按右侧步骤练习；如有疼痛或不确定，先咨询康复治疗师。</div>`}
              ${videos.length ? `
              <div class="exv-pane" data-p="video" style="${has3d ? "display:none" : ""}">
                <video class="ex-video" src="${videos[0]}" controls preload="metadata" playsinline></video>
                ${videos.length > 1 ? `
                <div class="exv-playlist flex wrap" style="gap:6px;margin-top:10px">
                  ${videos.map((v, i) => `<button class="btn ghost sm ex-vbtn ${i === 0 ? "active-filter" : ""}" data-vsrc="${v}">示范 ${i + 1}</button>`).join("")}
                </div>` : ""}
                <div class="ghost-note">🎬 真人示范 · ${escapeHtml(e.name)} 标准动作教学视频${videos.length > 1 ? ` · 共 ${videos.length} 个示范，点击切换` : ""}</div>
              </div>` : ""}
              ${atlasHtml ? `
              <div class="section-title mt-16" style="font-size:14px">🫀 发力肌群图谱（3D解剖）</div>
              <div class="card" style="box-shadow:none;padding:12px">${atlasHtml}</div>` : ""}
            </div>
            <div>
              ${steps.length ? `
              <div class="section-title" style="font-size:14px">📖 动作分解</div>
              <div class="ex-steps-tl">${steps.map((s, i) => `<div class="ex-step-tl" data-n="${i + 1}">${escapeHtml(s)}</div>`).join("")}</div>` : ""}
              ${e.breathing ? `
              <div class="section-title mt-16" style="font-size:14px">🫁 呼吸节奏</div>
              <div class="ex-breathe">🫁 <div>${escapeHtml(e.breathing)}</div></div>` : ""}
              ${tips.length ? `
              <div class="section-title mt-16" style="font-size:14px">⚠️ 要点与常见错误</div>
              <div class="ex-tips">${tips.map((t) => `<div class="ex-tip">${escapeHtml(t)}</div>`).join("")}</div>` : ""}
              ${e.contraindications ? `
              <div class="section-title mt-16" style="font-size:14px">🚫 运动禁忌</div>
              <div class="ex-tip" style="border-color:var(--danger);color:var(--danger)">${escapeHtml(e.contraindications)}</div>` : ""}
              ${e.alternatives ? `
              <div class="section-title mt-16" style="font-size:14px">🔁 替代动作</div>
              <div class="ex-tip">${escapeHtml(e.alternatives)}</div>` : ""}
            </div>
          </div>
          <div class="flex between mt-16 wrap" style="gap:10px">
            <a class="btn ghost sm" href="${BILI_SEARCH}${encodeURIComponent(e.name + " 教学")}" target="_blank" rel="noopener noreferrer">▶️ 在 B 站看「${escapeHtml(e.name)}」教学视频</a>
            <a class="btn sm" href="#/checkin" onclick="document.getElementById('modal-root').innerHTML=''">✅ 去康复日志练习</a>
          </div>`,
        footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`,
        onMount(modal) {
          const tabs = modal.querySelectorAll(".exv-tabs .vt");
          const panes = modal.querySelectorAll(".exv-pane");
          tabs.forEach((t) => {
            t.onclick = () => {
              tabs.forEach((x) => x.classList.toggle("active", x === t));
              panes.forEach((p) => { p.style.display = p.dataset.p === t.dataset.v ? "" : "none"; });
            };
          });
          const videoEl = modal.querySelector(".exv-pane[data-p='video'] .ex-video");
          modal.querySelectorAll(".ex-vbtn").forEach((b) => {
            b.onclick = () => {
              modal.querySelectorAll(".ex-vbtn").forEach((x) => x.classList.toggle("active-filter", x === b));
              const want = new URL(b.dataset.vsrc, location.href).href;
              if (videoEl && videoEl.currentSrc !== want) {
                videoEl.src = b.dataset.vsrc;
                videoEl.play().catch(() => {});
              }
            };
          });
          const pane3d = modal.querySelector('.exv-pane[data-p="3d"]');
          const frameB = pane3d && pane3d.querySelector(".f-b");
          const frameA = pane3d && pane3d.querySelector(".f-a");
          const frameM = pane3d && pane3d.querySelector(".f-m");
          if (pane3d && frameM) {
            frameM.onerror = () => {
              pane3d.classList.add("no-m");
              frameM.remove();
            };
          }
          if (pane3d && frameB && frameA) {
            frameB.onerror = () => {
              pane3d.classList.add("static");
              frameB.remove();
              const note = pane3d.querySelector(".ghost-note");
              if (note) note.textContent = "🧍 3D解剖静态图解";
            };
            frameA.onerror = () => {
              const videoTab = modal.querySelector('.vt[data-v="video"]');
              if (videoTab) videoTab.click();
            };
          }
          const toggle3d = modal.querySelector("#ex-3d-toggle");
          const speed3d = modal.querySelector("#ex-3d-speed");
          if (pane3d && toggle3d) {
            toggle3d.onclick = () => {
              pane3d.classList.toggle("paused");
              toggle3d.textContent = pane3d.classList.contains("paused") ? "▶️ 播放" : "⏸ 暂停";
            };
          }
          if (pane3d && speed3d) {
            let slow = false;
            speed3d.onclick = () => {
              slow = !slow;
              pane3d.style.setProperty("--aspd", slow ? "5.5s" : "3s");
              speed3d.textContent = slow ? "⚡ 正常速度" : "🐢 慢速精学";
            };
          }
        },
    });
  }

  el.innerHTML = `
    <div class="card mb-16">
      <div class="section-title">🩺 康复动作库 <span class="tag">按身体部位 · 3D图解 · 安全要点</span></div>
      <div class="filter-bar">
        <button class="btn ghost sm ${cat === "" ? "active-filter" : ""}" data-cat="">全部分类</button>
        ${CATS.map((c) => `<button class="btn ghost sm ${cat === c ? "active-filter" : ""}" data-cat="${c}">${CAT_ICON[c]} ${c}</button>`).join("")}
        <select id="ex-diff"><option value="">全部难度</option>
          <option value="1" ${diff === "1" ? "selected" : ""}>早期</option>
          <option value="2" ${diff === "2" ? "selected" : ""}>中期</option>
          <option value="3" ${diff === "3" ? "selected" : ""}>后期</option>
        </select>
        <input id="ex-q" placeholder="搜索动作名 / 介绍…" style="width:200px" value="${escapeHtml(q)}">
        <button class="btn sm" id="ex-search">搜索</button>
      </div>
    </div>
    <div id="ex-grid"></div>`;
  const grid = el.querySelector("#ex-grid");

  el.querySelectorAll("[data-cat]").forEach((b) => {
    b.onclick = () => {
      cat = b.dataset.cat;
      el.querySelectorAll("[data-cat]").forEach((x) => x.classList.toggle("active-filter", x === b));
      load();
    };
  });
  el.querySelector("#ex-diff").onchange = (e) => { diff = e.target.value; load(); };
  el.querySelector("#ex-search").onclick = () => { q = el.querySelector("#ex-q").value.trim(); load(); };
  let searchTimer = null;
  el.querySelector("#ex-q").oninput = (ev) => {
    clearTimeout(searchTimer);
    const val = ev.target.value.trim();
    searchTimer = setTimeout(() => { q = val; load(); }, 300);
  };
  el.querySelector("#ex-q").onkeydown = (e) => {
    if (e.key === "Enter") { clearTimeout(searchTimer); q = e.target.value.trim(); load(); }
  };
  load();
}
