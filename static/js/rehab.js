import { toast, openModal, closeModal, escapeHtml, fmtDate, fmtTime, me } from "./app.js";
import { api } from "./api.js";

let trendChart = null;
function killChart() {
  if (trendChart) { trendChart.destroy && trendChart.destroy(); trendChart = null; }
}

const STAGE_TAG = { 急性期: "red", 恢复期: "warn", 强化期: "green", 维持期: "gray" };
const STATUS_LABEL = { active: "进行中", paused: "已暂停", closed: "已结案" };
const TYPE_LABEL = { 骨科术后: "骨科术后", 运动损伤: "运动损伤", 慢性疼痛: "慢性疼痛", 神经康复: "神经康复", 体态矫正: "体态矫正" };

/* ================= 康复档案 ================= */
export async function viewRehabCases(el) {
  killChart();
  const user = me();
  const canEdit = user.role === "coach" || user.role === "admin";
  const cases = await api("/api/rehab/cases");

  el.innerHTML = `
    <div class="flex between wrap mb-16" style="align-items:center">
      <div class="section-title" style="margin:0">🗂 康复档案</div>
      ${canEdit ? '<button class="btn warn" id="new-case">＋ 新建康复档案</button>' : ""}
    </div>
    <div class="grid cols-2" style="gap:14px">
      ${cases.length ? cases.map((c) => `
        <div class="card">
          <div class="flex between" style="margin-bottom:10px;align-items:flex-start">
            <div>
              <b style="font-size:16px">${escapeHtml(c.condition_name)}</b>
              <div style="color:var(--text-2);font-size:12px;margin-top:4px">
                ${escapeHtml(c.patient_name || c.patient_username || "")} ·
                ${escapeHtml(TYPE_LABEL[c.condition_type] || c.condition_type)} ·
                ${escapeHtml(c.injured_side || "")}侧
              </div>
            </div>
            <span class="tag ${STAGE_TAG[c.stage] || "gray"}">${escapeHtml(c.stage || "")}</span>
          </div>
          <div style="font-size:13px;line-height:1.8;color:var(--text-2)">
            <div><b style="color:var(--text-1)">主诉：</b>${escapeHtml(c.chief_complaint || "-")}</div>
            <div><b style="color:var(--text-1)">评估诊断：</b>${escapeHtml(c.diagnosis || "-")}</div>
            <div><b style="color:var(--text-1)">康复目标：</b>${escapeHtml(c.goal || "-")}</div>
          </div>
          <div class="flex between" style="margin-top:12px;font-size:12px;color:var(--text-2)">
            <span>治疗师：${escapeHtml(c.therapist_name || "-")} · 发病 ${fmtDate(c.onset_date)}</span>
            <span class="tag ${c.status === "active" ? "green" : "gray"}">${STATUS_LABEL[c.status] || c.status}</span>
          </div>
        </div>`).join("") : '<div class="card"><div class="empty">暂无康复档案</div></div>'}
    </div>`;

  const btn = el.querySelector("#new-case");
  if (btn) {
    btn.onclick = async () => {
      const patients = await api("/api/rehab/patients");
      openModal({
        title: "新建康复档案",
        wide: true,
        content: `
          <div class="grid cols-2" style="gap:12px">
            <div class="field"><label>患者</label>
              <select id="c-patient">${patients.map((p) => `<option value="${p.id}">${escapeHtml(p.nickname || p.username)}</option>`).join("")}</select>
            </div>
            <div class="field"><label>病症 / 损伤名称</label><input id="c-name" placeholder="如：肩袖损伤修复术后"></div>
            <div class="field"><label>类型</label>
              <select id="c-type">${Object.keys(TYPE_LABEL).map((t) => `<option>${t}</option>`).join("")}</select>
            </div>
            <div class="field"><label>患侧</label>
              <select id="c-side"><option>左</option><option>右</option><option>双侧</option></select>
            </div>
            <div class="field"><label>发病 / 手术日期</label><input id="c-onset" type="date"></div>
            <div class="field"><label>康复阶段</label>
              <select id="c-stage"><option>急性期</option><option selected>恢复期</option><option>强化期</option><option>维持期</option></select>
            </div>
          </div>
          <div class="field"><label>主诉</label><input id="c-complaint" placeholder="如：右肩外展疼痛伴活动受限"></div>
          <div class="field"><label>评估诊断</label><input id="c-diagnosis" placeholder="如：肩关节活动度受限，冈上肌肌力4级"></div>
          <div class="field"><label>康复目标</label><input id="c-goal" placeholder="如：12周恢复全范围活动度，VAS≤2"></div>`,
        footer: `<button class="btn ghost" id="c-cancel">取消</button><button class="btn warn" id="c-save">保存</button>`,
        onMount(modal) {
          modal.querySelector("#c-cancel").onclick = closeModal;
          modal.querySelector("#c-save").onclick = async () => {
            const body = {
              patient_id: +modal.querySelector("#c-patient").value,
              condition_name: modal.querySelector("#c-name").value.trim(),
              condition_type: modal.querySelector("#c-type").value,
              injured_side: modal.querySelector("#c-side").value,
              onset_date: modal.querySelector("#c-onset").value || null,
              stage: modal.querySelector("#c-stage").value,
              chief_complaint: modal.querySelector("#c-complaint").value.trim(),
              diagnosis: modal.querySelector("#c-diagnosis").value.trim(),
              goal: modal.querySelector("#c-goal").value.trim(),
            };
            if (!body.condition_name) return toast("请填写病症名称", "error");
            try {
              await api("/api/rehab/cases", { method: "POST", body });
              closeModal();
              toast("康复档案已建立", "success");
              viewRehabCases(el);
            } catch (err) { toast(err.message, "error"); }
          };
        },
      });
    };
  }
}

/* ================= 康复评估 ================= */
function parseKV(text) {
  const out = {};
  (text || "").split(/\n|,/).forEach((line) => {
    const [k, v] = line.split(/[:：]/);
    if (k && v && !isNaN(parseFloat(v))) out[k.trim()] = parseFloat(v);
  });
  return out;
}

const assessState = { patientId: null, caseId: null };

export function focusAssessment(patientId) {
  assessState.patientId = +patientId;
  assessState.caseId = null;
}

export async function viewAssessments(el) {
  killChart();
  const user = me();
  const canEdit = user.role === "coach" || user.role === "admin";
  let patients = [];
  if (canEdit) {
    patients = await api("/api/rehab/patients");
    if (patients.length && !assessState.patientId) assessState.patientId = patients[0].id;
  }
  const patientId = canEdit ? assessState.patientId : user.id;

  const allCases = (await api("/api/rehab/cases")).filter((c) => +c.patient_id === +patientId);
  if (assessState.caseId && !allCases.some((c) => +c.id === +assessState.caseId)) assessState.caseId = null;
  if (!assessState.caseId && allCases.length) assessState.caseId = allCases[0].id;
  const caseId = assessState.caseId;

  const qs = `patient_id=${patientId}${caseId ? `&case_id=${caseId}` : ""}`;
  const [list, trend, screenings] = await Promise.all([
    api(`/api/rehab/assessments?${qs}`),
    api(`/api/rehab/assessments/trend?${qs}`),
    api(`/api/rehab/screenings?patient_id=${patientId}${caseId ? `&case_id=${caseId}` : ""}&limit=5`),
  ]);
  const last = list.length ? list[list.length - 1] : null;
  const prev = list.length > 1 ? list[list.length - 2] : null;
  const screening = screenings.length ? screenings[0] : null;

  const delta = (cur, old, lowerBetter, unit = "") => {
    if (cur === null || cur === undefined || old === null || old === undefined) return "";
    const d = +(cur - old).toFixed(1);
    if (d === 0) return `<span style="color:var(--text-2);font-size:12px">持平</span>`;
    const good = lowerBetter ? d < 0 : d > 0;
    return `<span style="color:${good ? "var(--success)" : "var(--danger)"};font-size:12px;font-weight:700">${d > 0 ? "↑" : "↓"} ${Math.abs(d)}${unit}</span>`;
  };
  const scaleCards = last ? [
    ["Berg 平衡", last.berg_score, "/56", last.berg_score >= 45 ? "var(--success)" : last.berg_score >= 35 ? "var(--warning)" : "var(--danger)", false],
    ["TUG 起立行走", last.tug_sec, " 秒", last.tug_sec <= 12 ? "var(--success)" : last.tug_sec <= 20 ? "var(--warning)" : "var(--danger)", true],
    ["10 米步行", last.walk10m_sec, " 秒", last.walk10m_sec <= 10 ? "var(--success)" : "var(--warning)", true],
    ["ODI 功能障碍", last.odi_score, "%", last.odi_score <= 20 ? "var(--success)" : last.odi_score <= 40 ? "var(--warning)" : "var(--danger)", true],
    ["WOMAC 指数", last.womac_score, "", last.womac_score <= 25 ? "var(--success)" : last.womac_score <= 50 ? "var(--warning)" : "var(--danger)", true],
  ].filter((c) => c[1] !== null && c[1] !== undefined && c[1] !== "") : [];

  el.innerHTML = `
    <div class="flex between wrap mb-16" style="align-items:center">
      <div class="section-title" style="margin:0">📈 康复评估</div>
      <div class="flex" style="gap:10px;align-items:flex-end">
        ${canEdit ? `<div class="field" style="margin:0"><label>患者</label>
          <select id="a-patient">${patients.map((p) => `<option value="${p.id}" ${p.id === patientId ? "selected" : ""}>${escapeHtml(p.nickname || p.username)}</option>`).join("")}</select></div>` : ""}
        <div class="field" style="margin:0"><label>康复档案</label>
          <select id="a-case">${allCases.map((c) => `<option value="${c.id}" ${+c.id === +caseId ? "selected" : ""}>${escapeHtml(c.condition_name)}</option>`).join("") || '<option value="">暂无档案</option>'}</select></div>
        ${canEdit ? '<button class="btn ghost" id="red-flag">🚩 红旗征筛查</button>' : ""}
        <button class="btn ghost" id="rehab-report">🖨️ 康复报告</button>
        ${canEdit ? '<button class="btn warn" id="new-assess">＋ 录入评估</button>' : ""}
      </div>
    </div>
    ${screening && screening.has_red_flag ? `
    <div class="card mb-16" style="border-left:4px solid var(--danger);background:#FEF2F2">
      <div style="font-weight:800;color:var(--danger);margin-bottom:4px">🚩 最近筛查命中红旗征（${fmtDate(screening.created_at.slice(0, 10))}）</div>
      <div style="font-size:13px;color:var(--text-2)">${screening.positive_labels.map((s) => escapeHtml(s)).join("；")}</div>
      <div style="font-size:12px;color:var(--danger);margin-top:6px">建议暂停高强度训练并尽快就医/转诊进一步检查。</div>
    </div>` : ""}
    ${last ? `
    <div class="grid cols-4 mb-16" style="gap:12px">
      <div class="card"><div style="color:var(--text-2);font-size:13px">疼痛 VAS</div>
        <div style="font-size:28px;font-weight:800;color:${last.pain_vas <= 3 ? "var(--success)" : last.pain_vas <= 6 ? "var(--warning)" : "var(--danger)"}">${last.pain_vas}<span style="font-size:14px;color:var(--text-2)">/10</span></div>
        <div style="color:var(--text-2);font-size:12px">${fmtDate(last.assess_date)}</div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">平衡能力</div>
        <div style="font-size:28px;font-weight:800;color:var(--primary)">${last.balance_score}</div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">步态评分</div>
        <div style="font-size:28px;font-weight:800;color:var(--accent)">${last.gait_score}</div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">日常生活能力</div>
        <div style="font-size:28px;font-weight:800;color:var(--success)">${last.adl_score}</div></div>
    </div>
    ${scaleCards.length ? `
    <div class="grid cols-4 mb-16" style="gap:12px">
      ${scaleCards.map(([label, val, unit, color]) => `
      <div class="card"><div style="color:var(--text-2);font-size:13px">${label}</div>
        <div style="font-size:26px;font-weight:800;color:${color}">${val}<span style="font-size:13px;color:var(--text-2)">${unit}</span></div>
        <div style="color:var(--text-2);font-size:11px">标准量表</div></div>`).join("")}
    </div>` : ""}
    ${prev ? `
    <div class="card mb-16">
      <div class="section-title">🔁 复评对比 <span class="tag">${fmtDate(prev.assess_date)} → ${fmtDate(last.assess_date)}</span></div>
      <div class="grid cols-4" style="gap:12px">
        ${[["疼痛 VAS", last.pain_vas, prev.pain_vas, true, ""],
           ["Berg 平衡", last.berg_score, prev.berg_score, false, ""],
           ["TUG", last.tug_sec, prev.tug_sec, true, "秒"],
           ["10 米步行", last.walk10m_sec, prev.walk10m_sec, true, "秒"],
           ["ODI", last.odi_score, prev.odi_score, true, "%"],
           ["WOMAC", last.womac_score, prev.womac_score, true, ""],
           ["平衡评分", last.balance_score, prev.balance_score, false, ""],
           ["ADL", last.adl_score, prev.adl_score, false, ""]]
          .filter((row) => row[1] !== null && row[1] !== undefined && row[2] !== null && row[2] !== undefined)
          .map(([label, cur, old, lower, unit]) => `
          <div class="card" style="padding:12px"><div style="color:var(--text-2);font-size:12px">${label}</div>
            <div class="flex between" style="align-items:baseline"><span style="font-size:20px;font-weight:800">${cur}${unit}</span>${delta(cur, old, lower, unit)}</div>
            <div style="color:var(--text-2);font-size:11px">上次 ${old}${unit}</div></div>`).join("")}
      </div>
    </div>` : ""}` : ""}
    <div class="card mb-16">
      <div class="section-title">🧠 评估推荐动作 <span class="tag green">按部位 · VAS · 阶段自动匹配</span></div>
      <div id="rec-body"><span style="color:var(--text-2);font-size:13px">加载中…</span></div>
    </div>
    <div class="card mb-16">
      <div class="section-title">疼痛与功能趋势</div>
      <div style="height:300px;position:relative"><canvas id="assess-chart"></canvas></div>
      ${!trend.length ? '<div class="empty">暂无评估数据</div>' : ""}
    </div>
    <div class="card">
      <div class="section-title">📋 评估记录</div>
      ${list.length ? `
      <div style="overflow-x:auto">
      <table><thead><tr><th>日期</th><th>VAS</th><th>Berg</th><th>TUG</th><th>10m步行</th><th>ODI</th><th>WOMAC</th><th>平衡</th><th>步态</th><th>姿势</th><th>ADL</th><th>关节活动度</th><th>肌力(MMT)</th><th>备注</th></tr></thead>
      <tbody>${list.slice().reverse().map((a) => `<tr>
        <td>${fmtDate(a.assess_date)}</td>
        <td class="num">${a.pain_vas}</td>
        <td class="num">${a.berg_score ?? "-"}</td>
        <td class="num">${a.tug_sec ?? "-"}</td>
        <td class="num">${a.walk10m_sec ?? "-"}</td>
        <td class="num">${a.odi_score ?? "-"}</td>
        <td class="num">${a.womac_score ?? "-"}</td>
        <td class="num">${a.balance_score}</td>
        <td class="num">${a.gait_score}</td>
        <td class="num">${a.posture_score}</td>
        <td class="num">${a.adl_score}</td>
        <td style="font-size:12px">${a.rom && Object.keys(a.rom).length ? Object.entries(a.rom).map(([k, v]) => `${escapeHtml(k)} ${v}°`).join(" / ") : "-"}</td>
        <td style="font-size:12px">${a.mmt && Object.keys(a.mmt).length ? Object.entries(a.mmt).map(([k, v]) => `${escapeHtml(k)} ${v}级`).join(" / ") : "-"}</td>
        <td style="font-size:12px;color:var(--text-2)">${escapeHtml(a.notes || "-")}</td>
      </tr>`).join("")}</tbody></table></div>` : '<div class="empty">暂无评估记录</div>'}
    </div>`;

  const recBody = el.querySelector("#rec-body");
  if (recBody) {
    const diffMap = { 1: "早期", 2: "中期", 3: "后期" };
    api(`/api/rehab/exercise-recommendations?patient_id=${patientId}${caseId ? `&case_id=${caseId}` : ""}`)
      .then((rec) => {
        const b = rec.basis || {};
        recBody.innerHTML = `
          <div style="color:var(--text-2);font-size:12px;margin-bottom:10px">
            依据：${escapeHtml(b.condition_name || "未建立康复档案")} · ${escapeHtml(b.stage || "-")} · 疼痛 VAS ${b.pain_vas ?? "-"} · 可执行难度 ${(b.difficulty_labels || []).join(" / ") || "-"}
          </div>
          ${b.note ? `<div style="color:var(--warning);font-size:12px;margin-bottom:10px">⚠️ ${escapeHtml(b.note)}</div>` : ""}
          <div class="flex wrap" style="gap:8px">
            ${rec.items && rec.items.length ? rec.items.map((i) =>
              `<span class="tag ${i.matched ? "green" : ""}" title="${escapeHtml(i.intro || "")}">${escapeHtml(i.name)} · ${escapeHtml(i.category)} · ${diffMap[i.difficulty] || ""}</span>`).join("")
              : '<span style="color:var(--text-2);font-size:13px">暂无匹配动作</span>'}
          </div>`;
      })
      .catch(() => { recBody.innerHTML = '<span style="color:var(--text-2);font-size:13px">暂无推荐数据</span>'; });
  }

  if (trend.length && window.Chart) {
    const ctx = el.querySelector("#assess-chart");
    trendChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: trend.map((t) => t.date.slice(5)),
        datasets: [
          { label: "疼痛VAS", data: trend.map((t) => t.pain_vas), borderColor: "#EF4444", backgroundColor: "rgba(239,68,68,0.12)", tension: 0.35, yAxisID: "y" },
          { label: "ADL", data: trend.map((t) => t.adl), borderColor: "#22C55E", backgroundColor: "rgba(34,197,94,0.10)", tension: 0.35, yAxisID: "y1" },
          { label: "平衡", data: trend.map((t) => t.balance), borderColor: "#3B82F6", backgroundColor: "rgba(59,130,246,0.10)", tension: 0.35, yAxisID: "y1" },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          y: { position: "left", min: 0, max: 10, title: { display: true, text: "VAS" } },
          y1: { position: "right", min: 0, max: 100, grid: { drawOnChartArea: false }, title: { display: true, text: "功能评分" } },
        },
      },
    });
  }

  const caseSel = el.querySelector("#a-case");
  if (caseSel) {
    caseSel.onchange = (e) => {
      assessState.caseId = +e.target.value || null;
      viewAssessments(el);
    };
  }

  if (canEdit) {
    el.querySelector("#a-patient").onchange = (e) => {
      assessState.patientId = +e.target.value;
      assessState.caseId = null;
      viewAssessments(el);
    };
    const btn = el.querySelector("#new-assess");
    if (btn) {
      btn.onclick = () => {
        if (!caseId) return toast("请先为该患者建立康复档案", "warn");
        openModal({
          title: "录入康复评估",
          wide: true,
          content: `
            <div class="grid cols-3" style="gap:12px">
              <div class="field"><label>评估日期</label><input id="as-date" type="date"></div>
              <div class="field"><label>疼痛 VAS (0-10)</label><input id="as-vas" type="number" min="0" max="10" value="3"></div>
              <div class="field"><label>平衡 (0-100)</label><input id="as-balance" type="number" min="0" max="100" value="70"></div>
              <div class="field"><label>步态 (0-100)</label><input id="as-gait" type="number" min="0" max="100" value="75"></div>
              <div class="field"><label>姿势 (0-100)</label><input id="as-posture" type="number" min="0" max="100" value="70"></div>
              <div class="field"><label>日常生活能力 (0-100)</label><input id="as-adl" type="number" min="0" max="100" value="80"></div>
            </div>
            <div class="grid cols-3" style="gap:12px">
              <div class="field"><label>Berg 平衡量表 (0-56)</label><input id="as-berg" type="number" min="0" max="56" placeholder="可选"></div>
              <div class="field"><label>TUG 起立行走（秒）</label><input id="as-tug" type="number" min="0" step="0.1" placeholder="可选"></div>
              <div class="field"><label>10 米步行（秒）</label><input id="as-walk" type="number" min="0" step="0.1" placeholder="可选"></div>
              <div class="field"><label>ODI 功能障碍指数 (0-100%)</label><input id="as-odi" type="number" min="0" max="100" placeholder="可选"></div>
              <div class="field"><label>WOMAC 指数 (0-100)</label><input id="as-womac" type="number" min="0" max="100" placeholder="可选"></div>
            </div>
            <div class="field"><label>关节活动度 ROM（每行一个，如：肩前屈:120）</label>
              <textarea id="as-rom" rows="3" placeholder="肩前屈:120&#10;肩外展:90"></textarea></div>
            <div class="field"><label>徒手肌力 MMT（每行一个，如：冈上肌:4）</label>
              <textarea id="as-mmt" rows="3" placeholder="冈上肌:4&#10;三角肌中束:3"></textarea></div>
            <div class="field"><label>备注</label><input id="as-notes" placeholder="评估结论与注意事项"></div>`,
          footer: `<button class="btn ghost" id="as-cancel">取消</button><button class="btn warn" id="as-save">保存</button>`,
          onMount(modal) {
            modal.querySelector("#as-date").value = new Date().toISOString().slice(0, 10);
            modal.querySelector("#as-cancel").onclick = closeModal;
            modal.querySelector("#as-save").onclick = async () => {
              const body = {
                patient_id: patientId,
                case_id: caseId,
                assess_date: modal.querySelector("#as-date").value || null,
                pain_vas: +modal.querySelector("#as-vas").value || 0,
                balance_score: +modal.querySelector("#as-balance").value || 0,
                gait_score: +modal.querySelector("#as-gait").value || 0,
                posture_score: +modal.querySelector("#as-posture").value || 0,
                adl_score: +modal.querySelector("#as-adl").value || 0,
                rom: parseKV(modal.querySelector("#as-rom").value),
                mmt: parseKV(modal.querySelector("#as-mmt").value),
                berg_score: modal.querySelector("#as-berg").value === "" ? null : +modal.querySelector("#as-berg").value,
                tug_sec: modal.querySelector("#as-tug").value === "" ? null : +modal.querySelector("#as-tug").value,
                walk10m_sec: modal.querySelector("#as-walk").value === "" ? null : +modal.querySelector("#as-walk").value,
                odi_score: modal.querySelector("#as-odi").value === "" ? null : +modal.querySelector("#as-odi").value,
                womac_score: modal.querySelector("#as-womac").value === "" ? null : +modal.querySelector("#as-womac").value,
                notes: modal.querySelector("#as-notes").value.trim(),
              };
              try {
                await api("/api/rehab/assessments", { method: "POST", body });
                closeModal();
                toast("评估已保存", "success");
                viewAssessments(el);
              } catch (err) { toast(err.message, "error"); }
            };
          },
        });
      };
    }
  }

  const redBtn = el.querySelector("#red-flag");
  if (redBtn) redBtn.onclick = () => openRedFlagScreen(patientId, caseId, () => viewAssessments(el));
  const reportBtn = el.querySelector("#rehab-report");
  if (reportBtn) reportBtn.onclick = () => openRehabReport(patientId, caseId);
}

/* ---------- 红旗征筛查 ---------- */
const RED_FLAG_ITEMS = [
  ["fever", "不明原因发热、盗汗或体重明显下降"],
  ["night_pain", "夜间静息痛或疼痛进行性加重"],
  ["saddle", "鞍区麻木、大小便功能障碍"],
  ["weakness", "双下肢进行性无力或行走困难"],
  ["trauma", "近期严重外伤，疑似骨折/脱位"],
  ["cardiopulmonary", "胸痛、胸闷、静息气促或心悸"],
  ["wound", "术后伤口红肿、渗液或持续发热"],
  ["dizziness", "眩晕伴恶心呕吐、复视或言语不清"],
];

export function openRedFlagScreen(patientId, caseId, onSaved) {
  openModal({
    title: "🚩 红旗征筛查",
    content: `
      <div style="font-size:13px;color:var(--text-2);margin-bottom:12px">请如实勾选以下情况，命中任一项将提示暂停高强度训练并就医。</div>
      ${RED_FLAG_ITEMS.map(([key, label], i) => `
        <label class="flex" style="gap:8px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--border)">
          <input type="checkbox" data-key="${key}" style="margin-top:3px">
          <span style="font-size:13px">${i + 1}. ${label}</span>
        </label>`).join("")}
      <div class="field" style="margin-top:12px"><label>补充说明</label>
        <input id="rf-notes" placeholder="如：症状持续时间、诱因等"></div>
      <div id="rf-result"></div>`,
    footer: `<button class="btn ghost" id="rf-cancel">取消</button><button class="btn warn" id="rf-save">保存筛查</button>`,
    onMount(modal) {
      modal.querySelector("#rf-cancel").onclick = closeModal;
      modal.querySelector("#rf-save").onclick = async () => {
        const items = {};
        modal.querySelectorAll("input[data-key]").forEach((cb) => { items[cb.dataset.key] = cb.checked; });
        try {
          const res = await api("/api/rehab/screenings", {
            method: "POST",
            body: { patient_id: patientId, case_id: caseId, items, notes: modal.querySelector("#rf-notes").value.trim() },
          });
          toast(res.has_red_flag ? "已记录：命中红旗征，请及时转诊" : "筛查已保存：未命中红旗征", res.has_red_flag ? "warn" : "success");
          closeModal();
          onSaved && onSaved();
        } catch (err) { toast(err.message, "error"); }
      };
    },
  });
}

/* ---------- 康复报告 ---------- */
export async function openRehabReport(patientId, caseId) {
  try {
    const r = await api(`/api/rehab/report?patient_id=${patientId}${caseId ? `&case_id=${caseId}` : ""}`);
    const p = r.patient || {}, c = r.case || {}, first = r.first_assessment, last = r.latest_assessment;
    const rows = (key, label, unit = "") => {
      if (!first || !last) return "";
      const a = first[key], b = last[key];
      if (a === null || a === undefined || b === null || b === undefined) return "";
      return `<tr><td>${label}</td><td class="num">${a}${unit}</td><td class="num">${b}${unit}</td><td class="num" style="font-weight:700">${(b - a).toFixed(1)}${unit}</td></tr>`;
    };
    const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
      <title>康复报告 - ${escapeHtml(p.nickname || "")}</title>
      <style>
        body{font-family:"Microsoft YaHei",system-ui,sans-serif;color:#1f2937;margin:36px;line-height:1.7}
        h1{font-size:24px;margin:0 0 4px} h2{font-size:16px;margin:22px 0 8px;color:#2E8B84;border-left:4px solid #2E8B84;padding-left:8px}
        .muted{color:#6b7280;font-size:12px} table{width:100%;border-collapse:collapse;font-size:13px}
        th,td{border:1px solid #e5e7eb;padding:7px 9px;text-align:left} th{background:#f0fdfa}
        .num{text-align:right;font-variant-numeric:tabular-nums}
        .box{border:1px solid #e5e7eb;border-radius:8px;padding:12px 14px;margin-bottom:10px}
        .grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
        .tag{display:inline-block;background:#ecfdf5;color:#047857;border-radius:4px;padding:1px 6px;font-size:12px;margin-right:6px}
        .red{color:#b91c1c;font-weight:700}
        @media print{body{margin:14mm} .noprint{display:none}}
      </style></head><body>
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div><h1>康衡康复中心 · 康复评估报告</h1>
          <div class="muted">报告生成时间：${escapeHtml(r.generated_at)}</div></div>
        <div class="muted">康复治疗师签名：______________</div>
      </div>
      <h2>一、基本信息</h2>
      <div class="box">
        <div class="grid">
          <div>姓名：<b>${escapeHtml(p.nickname || "-")}</b></div>
          <div>性别：${escapeHtml(p.gender || "-")} &nbsp; 联系电话：${escapeHtml(p.phone || "-")}</div>
          <div>诊断/问题：<b>${escapeHtml(c.condition_name || "-")}</b></div>
          <div>类型/阶段：${escapeHtml(c.condition_type || "-")} · ${escapeHtml(c.stage || "-")}</div>
          <div>主诉：${escapeHtml(c.chief_complaint || "-")}</div>
          <div>建档日期：${escapeHtml((c.created_at || "").slice(0, 10) || "-")}</div>
        </div>
      </div>
      <h2>二、评估结果对比（首次 → 最近）</h2>
      <table><thead><tr><th>指标</th><th class="num">首次</th><th class="num">最近</th><th class="num">变化</th></tr></thead><tbody>
        ${rows("pain_vas", "疼痛 VAS")}${rows("berg_score", "Berg 平衡")}${rows("tug_sec", "TUG 起立行走", " 秒")}
        ${rows("walk10m_sec", "10 米步行", " 秒")}${rows("odi_score", "ODI 功能障碍", "%")}
        ${rows("womac_score", "WOMAC 指数")}${rows("balance_score", "平衡评分")}${rows("adl_score", "日常生活能力")}
      </tbody></table>
      <h2>三、训练依从性</h2>
      <div class="box">近 ${r.adherence.days} 天应训练 <b>${r.adherence.target_days}</b> 天，实际记录 <b>${r.adherence.logged_days}</b> 天，
        依从率 <b>${r.adherence.rate}%</b>（周期 ${escapeHtml(r.adherence.start_date)} ~ ${escapeHtml(r.adherence.end_date)}）。</div>
      <h2>四、红旗征筛查</h2>
      <div class="box">${r.screening
        ? (r.screening.has_red_flag
          ? `<span class="red">命中红旗征：${r.screening.positive_labels.map(escapeHtml).join("；")}</span><br><span class="muted">建议暂停高强度训练并尽快就医/转诊。</span>`
          : `<span class="tag">未命中红旗征</span>可按康复方案循序渐进训练。`)
        : "暂无筛查记录。"}</div>
      <h2>五、当前康复方案</h2>
      <div class="box">${r.plans.length ? r.plans.map((x) => `<div>• ${escapeHtml(x.title)}（${escapeHtml(x.start_date)} ~ ${escapeHtml(x.end_date)}）</div>`).join("") : "暂无进行中的方案。"}</div>
      <h2>六、疗程与预约</h2>
      <div class="box">${r.treatment_cards.length ? r.treatment_cards.map((x) => `<div>• ${escapeHtml(x.title)}：剩余 <b>${x.remaining}</b> / ${x.total_sessions} 次</div>`).join("") : "暂无疗程卡。"}
        ${r.appointments.length ? `<div style="margin-top:6px">下次预约：${escapeHtml(r.appointments[0].appt_date)} ${escapeHtml(r.appointments[0].start_time)} · ${escapeHtml(r.appointments[0].coach_name)}</div>` : ""}</div>
      <h2>七、近期训练记录</h2>
      <table><thead><tr><th>日期</th><th class="num">时长(分)</th><th class="num">强度</th><th class="num">练前VAS</th><th class="num">练后VAS</th></tr></thead><tbody>
        ${r.recent_logs.length ? r.recent_logs.map((l) => `<tr><td>${escapeHtml(l.checkin_date)}</td><td class="num">${l.duration_min ?? "-"}</td><td class="num">${l.intensity ?? "-"}</td><td class="num">${l.vas_before ?? "-"}</td><td class="num">${l.vas_after ?? "-"}</td></tr>`).join("") : '<tr><td colspan="5">暂无记录</td></tr>'}
      </tbody></table>
      <div class="muted" style="margin-top:18px">本报告由康衡康复中心康复管理系统生成，仅供康复评估与治疗参考。</div>
      <div class="noprint" style="margin-top:22px"><button onclick="window.print()" style="padding:8px 18px;background:#2E8B84;color:#fff;border:0;border-radius:6px;cursor:pointer">打印 / 导出 PDF</button></div>
      </body></html>`;
    const w = window.open("", "_blank");
    if (!w) return toast("浏览器拦截了新窗口，请允许弹窗后重试", "warn");
    w.document.write(html);
    w.document.close();
  } catch (err) { toast(err.message, "error"); }
}

/* ================= 中医体质辨识 ================= */
const TCM_TYPES = ["平和质", "气虚质", "阳虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质"];
const TCM_DESC = {
  平和质: "阴阳气血调和", 气虚质: "易疲乏、气短", 阳虚质: "畏寒肢冷", 阴虚质: "手足心热、口干",
  痰湿质: "形体偏胖、困重", 湿热质: "口苦、易长痘", 血瘀质: "痛有定处、易瘀青",
  气郁质: "情绪低落、胸胁胀", 特禀质: "过敏体质",
};

export async function viewTcmConstitution(el) {
  killChart();
  const latest = await api("/api/rehab/tcm/latest");
  const scores = latest.has_data ? latest.scores : {};

  el.innerHTML = `
    <div class="section-title mb-16">🩺 中医体质辨识</div>
    <div class="card mb-16" style="background:linear-gradient(135deg,rgba(46,139,132,0.08),rgba(99,184,174,0.08));border-color:rgba(46,139,132,0.28)">
      <div style="font-size:13px;color:var(--text-2);line-height:1.8">
        中医体质辨识用于辅助个体化康复：结合体质特点调整训练强度、保暖与经络调理方式。
      </div>
      ${latest.has_data ? `
      <div class="flex between wrap" style="margin-top:14px;gap:12px;align-items:center">
        <div>
          <div style="color:var(--text-2);font-size:12px">最近辨识结果</div>
          <div style="font-size:26px;font-weight:800;color:var(--warning)">${escapeHtml(latest.primary_type)}</div>
          <div style="color:var(--text-2);font-size:12px">${fmtTime(latest.assessed_at)}</div>
        </div>
      </div>
      <div style="margin-top:12px;padding:12px;background:rgba(0,0,0,0.18);border-radius:8px;font-size:13px;line-height:1.9">
        ${escapeHtml(latest.advice || "")}
      </div>` : '<div class="empty" style="margin-top:12px">尚未进行体质辨识</div>'}
    </div>

    <div class="card mb-16">
      <div class="section-title">九种体质自评（拖动分值后提交）</div>
      <div class="grid cols-3" style="gap:14px;margin-top:12px">
        ${TCM_TYPES.map((t) => `
          <div>
            <div class="flex between" style="font-size:13px;margin-bottom:6px">
              <span><b>${t}</b><span style="color:var(--text-2);font-size:12px"> · ${TCM_DESC[t]}</span></span>
              <span id="val-${t}" style="color:var(--warning);font-weight:700">${scores[t] ?? 30}</span>
            </div>
            <input type="range" min="0" max="100" value="${scores[t] ?? 30}" data-tcm="${t}" style="width:100%">
          </div>`).join("")}
      </div>
      <div class="flex" style="gap:10px;margin-top:16px">
        <button class="btn warn" id="tcm-submit">提交辨识</button>
        <button class="btn ghost" id="tcm-reset">重置</button>
      </div>
      <div style="color:var(--text-2);font-size:12px;margin-top:8px">* 演示版采用 9 维度自评分值；正式版可替换为标准 60 题体质问卷量表。</div>
    </div>

    <div class="card">
      <div class="section-title">体质得分分布</div>
      <div style="height:280px;position:relative"><canvas id="tcm-chart"></canvas></div>
    </div>`;

  const renderChart = () => {
    if (!window.Chart) return;
    killChart();
    const vals = TCM_TYPES.map((t) => +el.querySelector(`[data-tcm="${t}"]`).value);
    trendChart = new Chart(el.querySelector("#tcm-chart"), {
      type: "bar",
      data: {
        labels: TCM_TYPES,
        datasets: [{ label: "体质得分", data: vals, backgroundColor: vals.map((v) => v >= 60 ? "rgba(46,139,132,0.85)" : "rgba(59,130,246,0.55)"), borderRadius: 6 }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { min: 0, max: 100 } } },
    });
  };

  el.querySelectorAll("[data-tcm]").forEach((input) => {
    input.oninput = () => {
      el.querySelector(`#val-${input.dataset.tcm}`).textContent = input.value;
      renderChart();
    };
  });
  renderChart();

  el.querySelector("#tcm-reset").onclick = () => {
    el.querySelectorAll("[data-tcm]").forEach((i) => {
      i.value = 30;
      el.querySelector(`#val-${i.dataset.tcm}`).textContent = 30;
    });
    renderChart();
  };

  el.querySelector("#tcm-submit").onclick = async () => {
    const payload = {};
    el.querySelectorAll("[data-tcm]").forEach((i) => { payload[i.dataset.tcm] = +i.value; });
    try {
      const res = await api("/api/rehab/tcm/assess", { method: "POST", body: { scores: payload } });
      toast(`辨识完成：${res.primary_type}`, "success");
      viewTcmConstitution(el);
    } catch (err) { toast(err.message, "error"); }
  };
}
