import { api, uploadFile } from "./api.js";
import { toast, openModal, closeModal, confirmBox, escapeHtml, fmtNum, fmtDate, fmtTime, registerViews, me, updateAvatar, avatarHtml, isTimed } from "./app.js";
import { renderChat } from "./chat.js";
import { viewCommunity } from "./community.js";
import { viewCoachEarnings } from "./features.js";
import { viewRehabCases, viewAssessments, focusAssessment } from "./rehab.js";

const charts = [];
function killCharts() { charts.forEach((c) => c.destroy && c.destroy()); charts.length = 0; }
function afterRender(fn) { requestAnimationFrame(fn); }
Chart.defaults.color = "#6B8580";
Chart.defaults.borderColor = "#D6E6E2";

/* ================= 数据看板 ================= */
async function viewDashboard(el) {
  killCharts();
  const d = await api("/api/coach/dashboard");
  el.innerHTML = `
    <div class="stat-cards">
      <div class="stat-card clickable" id="cd-students"><div class="label">患者总数</div><div class="value">${d.total_students}</div><div class="sub">本周活跃 ${d.active_week} 人</div><div class="drill-hint">点击查看患者列表 →</div></div>
      <div class="stat-card clickable ${d.avg_rate_30 < 50 ? "warn" : "green"}" id="cd-rate"><div class="label">近30天平均康复日志率</div><div class="value">${d.avg_rate_30}%</div><div class="sub">低于50%将预警</div><div class="drill-hint">点击查看康复日志趋势/预警 →</div></div>
      <div class="stat-card purple clickable" id="cd-plans"><div class="label">进行中计划</div><div class="value">${d.active_plans}</div><div class="sub">患者正在执行</div><div class="drill-hint">点击去制定/管理计划 →</div></div>
      <div class="stat-card clickable ${d.pending_makeups ? "warn" : ""}" id="cd-makeups"><div class="label">待审批补签</div><div class="value">${d.pending_makeups}</div><div class="sub">患者提交的补签申请</div><div class="drill-hint">点击去处理补签 →</div></div>
    </div>
    <div class="grid cols-2">
      <div class="card"><div class="section-title">患者康复日志率趋势（近30天）</div><div style="height:250px"><canvas id="rate-chart"></canvas></div></div>
      <div class="card"><div class="section-title">低康复日志率患者（30天 &lt; 50%）<span class="tag red">预警</span></div>
        ${d.low_rate_students.length ? `<table><thead><tr><th>患者</th><th>30天康复日志率</th><th>连续天数</th><th>操作</th></tr></thead>
          <tbody>${d.low_rate_students.map((s) => `<tr>
            <td>${escapeHtml(s.nickname)}</td>
            <td><span class="tag red">${s.rate_30}%</span></td>
            <td class="num">${s.current_streak}天</td>
            <td>${s.urged_today
              ? '<button class="btn success sm" disabled>✔ 已催促</button>'
              : `<button class="btn warn sm" data-urge="${s.id}" data-name="${escapeHtml(s.nickname)}">催康复日志</button>`}</td>
          </tr>`).join("")}</tbody></table>` : `<div class="empty"><span class="ico">🎉</span>患者都很积极，无预警</div>`}
      </div>
    </div>`;

  el.querySelector("#cd-students").onclick = () => (location.hash = "#/students");
  el.querySelector("#cd-rate").onclick = () => {
    const trendBox = el.querySelector("#rate-chart");
    if (trendBox) trendBox.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  el.querySelector("#cd-plans").onclick = () => (location.hash = "#/plans");
  el.querySelector("#cd-makeups").onclick = () => (location.hash = "#/guide");

  el.querySelectorAll("[data-urge]").forEach((b) => {
    b.onclick = async () => {
      try {
        await api(`/api/coach/students/${b.dataset.urge}/urge`, {
          method: "POST", body: { message: `同学你好，最近康复日志率偏低，坚持训练才能看到效果哦！` },
        });
        toast(`已向 ${b.dataset.name} 发送催康复日志消息`, "success");
        b.outerHTML = '<button class="btn success sm" disabled>✔ 已催促</button>';
      } catch (err) { toast(err.message, "error"); }
    };
  });

  afterRender(() => {
    const chart = new Chart(document.getElementById("rate-chart"), {
      type: "line",
      data: {
        labels: d.checkin_trend.map((t) => t.date.slice(5)),
        datasets: [{
          label: "康复日志率%", data: d.checkin_trend.map((t) => t.rate),
          borderColor: "#2E8B84", backgroundColor: "rgba(46,139,132,0.1)", fill: true, tension: 0.35,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: { y: { min: 0, max: 100, ticks: { callback: (v) => v + "%" } } },
      },
    });
    charts.push(chart);
  });
}

/* ================= 患者管理 ================= */
async function viewStudents(el) {
  killCharts();
  let filter = "";

  async function load() {
    const list = await api(`/api/coach/students${filter ? `?filter_status=${filter}` : ""}`);
    table.innerHTML = list.length ? `
      <table><thead><tr><th>患者</th><th>今日康复日志</th><th>30天康复日志</th><th>30天训练量</th><th>连续天数</th><th>最近体重</th><th>操作</th></tr></thead>
      <tbody>${list.map((s) => `<tr>
        <td><div class="flex">${avatarHtml(s.nickname, s.avatar, "sm")}<div><b>${escapeHtml(s.nickname)}</b><div style="color:var(--text-2);font-size:12px">${escapeHtml(s.phone || "")}</div></div></div></td>
        <td>${s.checked_today ? '<span class="tag green">已康复日志</span>' : '<span class="tag red">未康复日志</span>'}</td>
        <td class="num">${s.days_30} 天 <span class="tag ${s.rate_30 < 50 ? "red" : ""}" style="font-size:11px">${s.rate_30}%</span></td>
        <td class="num">${fmtNum(s.volume_30)} kg</td>
        <td class="num">${s.current_streak} / ${s.longest_streak}</td>
        <td class="num">${s.latest_weight ?? "-"}</td>
        <td class="flex">
          <button class="btn ghost sm" data-detail="${s.id}">详情</button>
          ${s.urged_today
            ? '<button class="btn success sm" disabled>✔ 已催促</button>'
            : (s.checked_today ? "" : `<button class="btn warn sm" data-urge="${s.id}" data-name="${escapeHtml(s.nickname)}">催康复日志</button>`)}
        </td>
      </tr>`).join("")}</tbody></table>` : `<div class="empty"><span class="ico">👥</span>暂无患者（为患者创建康复方案后自动关联）</div>`;

    table.querySelectorAll("[data-urge]").forEach((b) => {
      b.onclick = async () => {
        try {
          await api(`/api/coach/students/${b.dataset.urge}/urge`, { method: "POST", body: {} });
          toast(`已催 ${b.dataset.name} 康复日志`, "success");
          b.outerHTML = '<button class="btn success sm" disabled>✔ 已催促</button>';
        } catch (err) { toast(err.message, "error"); }
      };
    });
    table.querySelectorAll("[data-detail]").forEach((b) => {
      b.onclick = () => openDetail(+b.dataset.detail);
    });
  }

  async function openDetail(id) {
    const d = await api(`/api/coach/students/${id}`);
    openModal({
      title: `患者 · ${escapeHtml(d.student.nickname)}`,
      wide: true,
      content: `
        <div class="flex wrap mb-16">
          <span class="tag">当前连续 ${d.student.current_streak} 天</span>
          <span class="tag purple">历史最长 ${d.student.longest_streak} 天</span>
          <span class="tag gray">注册于 ${fmtDate(d.student.created_at)}</span>
        </div>
        <div class="grid cols-2">
          <div>
            <div class="section-title" style="font-size:14px">最近康复日志</div>
            <div style="max-height:300px;overflow-y:auto"><table><thead><tr><th>日期</th><th>训练量</th><th>时长</th></tr></thead>
            <tbody>${d.checkins.map((c) => `<tr><td>${c.checkin_date} ${c.is_makeup ? '<span class="tag warn">补</span>' : ""}</td><td class="num">${c.train_volume}kg</td><td class="num">${c.duration_min}min</td></tr>`).join("") || `<tr><td colspan="3" class="empty">暂无康复日志</td></tr>`}</tbody></table></div>
          </div>
          <div>
            <div class="section-title" style="font-size:14px">康复指标趋势</div>
            <div style="height:220px"><canvas id="s-body"></canvas></div>
          </div>
        </div>`,
      footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`,
      onMount() {
        afterRender(() => {
          if (!d.body_records.length) return;
          const chart = new Chart(document.getElementById("s-body"), {
            type: "line",
            data: {
              labels: d.body_records.map((b) => b.record_date.slice(5)),
              datasets: [
                { label: "体重kg", data: d.body_records.map((b) => b.weight), borderColor: "#2E8B84", tension: 0.35 },
                { label: "体脂%", data: d.body_records.map((b) => b.body_fat), borderColor: "#4FA8A0", tension: 0.35 },
              ],
            },
            options: { responsive: true, maintainAspectRatio: false },
          });
          charts.push(chart);
        });
      },
    });
  }

  el.innerHTML = `
    <div class="card">
      <div class="filter-bar">
        <button class="btn ghost sm" data-f="">全部</button>
        <button class="btn ghost sm" data-f="unchecked">今日未康复日志</button>
        <button class="btn ghost sm" data-f="checked">今日已康复日志</button>
        <button class="btn ghost sm" data-f="low">低康复日志率</button>
        <span style="flex:1"></span>
        <button class="btn sm" id="export-csv">⬇ 导出 CSV</button>
      </div>
      <div id="students-table"></div>
    </div>`;

  const table = el.querySelector("#students-table");
  el.querySelectorAll("[data-f]").forEach((b) => {
    b.onclick = () => { filter = b.dataset.f; load(); };
  });
  el.querySelector("#export-csv").onclick = () => {
    window.open("/api/coach/students/export", "_blank");
  };
  load();
}

/* ================= 计划制定 ================= */
async function viewPlans(el) {
  killCharts();
  const students = await api("/api/coach/all-students");

  async function load() {
    const plans = await api("/api/coach/plans");
    list.innerHTML = plans.length ? plans.map((p) => `
      <div class="card mb-16">
        <div class="section-title">
          <span>${escapeHtml(p.title)} <span class="tag">${escapeHtml(p.student_name)}</span>
            ${p.is_recommended ? '<span class="tag purple">已推荐给患者</span>' : ""}</span>
          <span class="flex wrap">
            ${p.is_recommended
              ? `<button class="btn ghost sm" data-unrec="${p.id}">取消推荐</button>`
              : `<button class="btn purple sm" data-rec="${p.id}">⭐ 推荐给患者</button>`}
            <button class="btn ghost sm" data-edit="${p.id}">编辑</button>
            <button class="btn ghost sm" data-copy="${p.id}">复制</button>
            <button class="btn ghost sm" data-view="${p.id}">查看</button>
            <button class="btn danger sm" data-del="${p.id}">删除</button>
          </span>
        </div>
        <div class="tag gray">${p.start_date} ~ ${p.end_date} · ${p.items.length} 个动作条目</div>
        <p style="color:var(--text-2);font-size:13px;margin-top:8px">${escapeHtml(p.description || "")}</p>
      </div>`).join("") : `
      <div class="empty" style="padding:36px 0">
        <span class="ico">📋</span>
        <p style="margin:8px 0 4px;font-size:15px;font-weight:600">还没有给患者制定过计划</p>
        <p style="margin-bottom:16px;color:var(--text-2)">点击上方「创建康复方案」，为患者编排每日训练动作，保存后患者即可在康复方案页看到并按计划康复日志</p>
      </div>`;

    list.querySelectorAll("[data-view]").forEach((b) => b.onclick = () => viewPlan(+b.dataset.view));
    list.querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => openPlanForm(+b.dataset.edit));
    list.querySelectorAll("[data-rec]").forEach((b) => b.onclick = async () => {
      try {
        await api(`/api/coach/plans/${b.dataset.rec}/recommend`, { method: "POST" });
        toast("已推荐给患者，患者端将优先展示该计划", "success"); load();
      } catch (err) { toast(err.message, "error"); }
    });
    list.querySelectorAll("[data-unrec]").forEach((b) => b.onclick = async () => {
      try {
        await api(`/api/coach/plans/${b.dataset.unrec}/recommend`, { method: "DELETE" });
        toast("已取消推荐", "success"); load();
      } catch (err) { toast(err.message, "error"); }
    });
    list.querySelectorAll("[data-copy]").forEach((b) => b.onclick = async () => {
      try {
        await api(`/api/coach/plans/${b.dataset.copy}/copy`, { method: "POST" });
        toast("计划已复制到今天开始", "success"); load();
      } catch (err) { toast(err.message, "error"); }
    });
    list.querySelectorAll("[data-del]").forEach((b) => b.onclick = () =>
      confirmBox("确定删除该康复方案？", async () => {
        await api(`/api/coach/plans/${b.dataset.del}`, { method: "DELETE" });
        closeModal(); toast("已删除", "success"); load();
      }));
  }

  async function viewPlan(id) {
    const p = await api(`/api/coach/plans/${id}`);
    const days = [...new Set(p.items.map((i) => i.day_date))].sort();
    openModal({
      title: escapeHtml(p.title),
      wide: true,
      content: days.map((d) => `
        <div class="mb-16"><b style="color:var(--primary)">${d}</b>
        <table><thead><tr><th>动作</th><th>组</th><th>次</th><th>建议kg</th><th>休息</th><th>备注</th></tr></thead>
        <tbody>${p.items.filter((i) => i.day_date === d).map((i) =>
          `<tr><td>${escapeHtml(i.exercise_name)}</td><td class="num">${i.sets}</td><td class="num">${isTimed(i.exercise_name) ? i.reps + "秒" : i.reps}</td><td class="num">${isTimed(i.exercise_name) ? "-" : i.weight_suggest}</td><td class="num">${i.rest_sec}s</td><td>${escapeHtml(i.note || "-")}</td></tr>`).join("")}
        </tbody></table></div>`).join(""),
      footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`,
    });
  }

  async function openPlanForm(planId) {
    const plan = planId ? await api(`/api/coach/plans/${planId}`) : null;
    let items = plan ? plan.items.map((i) => ({ ...i })) : [];
    const today = new Date().toISOString().slice(0, 10);
    const defaultStu = plan ? students.find((s) => s.id === plan.student_id) : students[0];

    openModal({
      title: planId ? "编辑康复方案" : "给患者制定康复方案",
      wide: true,
      content: `
        <div class="grid cols-4">
          <div class="field" style="grid-column:span 2"><label>患者（全部患者可选，右侧显示所选患者信息）</label>
            <div class="flex" style="gap:10px;align-items:stretch">
              <div id="p-stu-card" class="flex" style="gap:10px;align-items:center;padding:6px 12px;border:1px solid var(--border);border-radius:8px;flex:1;min-width:0"></div>
              <select id="p-student" style="flex:1.2">
                ${students.map((s) => `<option value="${s.id}" ${plan && plan.student_id === s.id ? "selected" : ""}>${escapeHtml(s.nickname)}${s.phone ? `（${escapeHtml(s.phone)}）` : ""}</option>`).join("")}
              </select>
            </div>
          </div>
          <div class="field"><label>计划标题</label><input id="p-title" value="${plan ? escapeHtml(plan.title) : ""}" maxlength="100" placeholder="如：肩袖损伤4周康复方案"></div>
          <div class="field"><label>开始日期</label><input type="date" id="p-start" value="${plan ? plan.start_date : today}"></div>
          <div class="field"><label>结束日期</label><input type="date" id="p-end" value="${plan ? plan.end_date : today}"></div>
        </div>
        <div class="field"><label>计划说明（患者可见）</label><input id="p-desc" value="${plan ? escapeHtml(plan.description || "") : ""}" maxlength="500" placeholder="训练目标与注意事项…"></div>
        <div class="section-title" style="font-size:14px">
          <span>每日训练动作 <span class="tag gray">选动作 → 自动按开始日期排入</span></span>
          <span class="flex">
            <select id="p-exercise" style="width:200px"></select>
            <button class="btn ghost sm" id="p-add">+ 添加动作</button>
            <button class="btn ghost sm" id="p-rec">🧠 按评估推荐</button>
            <button class="btn ghost sm" id="p-stage">📚 阶段模板</button>
            <input type="date" id="p-day" value="${today}" style="width:auto" title="安排到哪一天">
          </span>
        </div>
        <div id="p-tpl" class="mb-16"></div>
        <div id="p-items"></div>`,
      footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">取消</button>
               <button class="btn" id="p-save">保存并布置给患者</button>`,
      onMount(modal) {
        const itemsBox = modal.querySelector("#p-items");
        const stuCard = modal.querySelector("#p-stu-card");
        const stuSel = modal.querySelector("#p-student");

        function renderStuCard() {
          const s = students.find((x) => x.id === +stuSel.value);
          if (!s) { stuCard.innerHTML = ""; return; }
          stuCard.innerHTML = `
            ${avatarHtml(s.nickname, s.avatar, "sm")}
            <div style="min-width:0">
              <b style="font-size:13px">${escapeHtml(s.nickname)}</b>
              <div style="color:var(--text-2);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
                🔥 连续 ${s.current_streak} 天${s.latest_weight ? ` · 体重 ${s.latest_weight}kg` : ""}${s.latest_body_fat ? ` · 体脂 ${s.latest_body_fat}%` : ""}${s.phone ? ` · ${escapeHtml(s.phone)}` : ""}
              </div>
            </div>`;
        }
        renderStuCard();
        stuSel.onchange = renderStuCard;

        api("/api/coach/exercises").then((exs) => {
          modal.querySelector("#p-exercise").innerHTML =
            exs.map((e) => `<option value="${escapeHtml(e.name)}" data-sets="${e.default_sets}" data-reps="${e.default_reps}" data-w="${e.default_weight}">${escapeHtml(e.name)}（${e.category}）</option>`).join("");
        });

        function renderRows() {
          if (!items.length) {
            itemsBox.innerHTML = `<div class="empty" style="padding:16px;text-align:center">📋 暂无动作<br><span style="font-size:12px;color:var(--text-2)">左侧选择动作 → 设置日期 → 点击「+ 添加动作」<br>每行可直接修改 日期 / 动作名 / 组数 / 次数 / 重量</span></div>`;
            return;
          }
          const groups = {};
          items.forEach((it) => { (groups[it.day_date] = groups[it.day_date] || []).push(it); });
          itemsBox.innerHTML = Object.keys(groups).sort().map((d) => `
            <div class="pi-day-group">
              <div class="pi-day-header">📅 ${d}</div>
              <div class="pi-day-items">
                ${groups[d].map((it) => {
                  const idx = items.indexOf(it);
                  const timed = isTimed(it.exercise_name);
                  return `
                  <div class="pi-row coach-row">
                    <input class="i-name" data-idx="${idx}" value="${escapeHtml(it.exercise_name)}" placeholder="动作名称" style="flex:2">
                    <div class="pi-field"><label>组数</label><input class="i-sets num" data-idx="${idx}" type="number" min="0" value="${it.sets}"></div>
                    <div class="pi-field"><label>${timed ? "秒数" : "次数"}</label><input class="i-reps num" data-idx="${idx}" type="number" min="0" value="${it.reps}" placeholder="${timed ? "秒" : "次"}"></div>
                    <div class="pi-field"><label>${timed ? "自重" : "重量kg"}</label><input class="i-weight num" data-idx="${idx}" type="number" min="0" step="0.5" value="${timed ? 0 : it.weight_suggest}" ${timed ? "disabled" : ""}></div>
                    <button class="pi-del" data-idx="${idx}" aria-label="删除" title="删除该动作">×</button>
                  </div>`;
                }).join("")}
              </div>
            </div>`).join("");

          itemsBox.querySelectorAll("input[data-idx]").forEach((inp) => {
            inp.onchange = () => {
              const i = +inp.dataset.idx;
              const key = { "i-name": "exercise_name", "i-sets": "sets", "i-reps": "reps", "i-weight": "weight_suggest" }[Array.from(inp.classList).find((c) => c.startsWith("i-"))];
              if (!key) return;
              const wasTimed = isTimed(items[i].exercise_name);
              items[i][key] = key === "exercise_name" ? inp.value : +inp.value || 0;
              if (key === "exercise_name" && wasTimed !== isTimed(items[i].exercise_name)) renderRows();
            };
          });
          itemsBox.querySelectorAll(".pi-del").forEach((b) => {
            b.onclick = () => { items.splice(+b.dataset.idx, 1); renderRows(); };
          });
        }
        renderRows();

        modal.querySelector("#p-add").onclick = () => {
          const sel = modal.querySelector("#p-exercise");
          const opt = sel.selectedOptions[0];
          items.push({
            day_date: modal.querySelector("#p-day").value || modal.querySelector("#p-start").value || today,
            exercise_name: sel.value, sets: +opt?.dataset.sets || 3,
            reps: +opt?.dataset.reps || 12, weight_suggest: +opt?.dataset.w || 0,
            rest_sec: 90, note: "", sort_order: items.length,
          });
          renderRows();
        };

        modal.querySelector("#p-rec").onclick = async () => {
          const studentId = +stuSel.value;
          try {
            const rec = await api(`/api/rehab/exercise-recommendations?patient_id=${studentId}&limit=6`);
            if (!rec.items || !rec.items.length) return toast("该患者暂无可用评估推荐，请先录入康复评估", "warn");
            const day = modal.querySelector("#p-day").value || modal.querySelector("#p-start").value || today;
            let added = 0;
            rec.items.forEach((e) => {
              if (items.some((i) => i.exercise_name === e.name && i.day_date === day)) return;
              items.push({
                day_date: day, exercise_name: e.name,
                sets: e.default_sets || 3, reps: e.default_reps || 12,
                weight_suggest: e.default_weight || 0, rest_sec: 90,
                note: e.reason || "", sort_order: items.length,
              });
              added += 1;
            });
            renderRows();
            toast(`已按${rec.basis.condition_name || "通用基础动作"}加入 ${added} 个推荐动作`, "success");
          } catch (err) { toast(err.message, "error"); }
        };

        modal.querySelector("#p-stage").onclick = async () => {
          const studentId = +stuSel.value;
          const box = modal.querySelector("#p-tpl");
          try {
            const tpl = await api(`/api/rehab/stage-templates?patient_id=${studentId}`);
            box.innerHTML = `
              <div style="font-size:12px;color:var(--text-2);margin-bottom:8px">
                按患者评估匹配部位：${tpl.matched_categories.map(escapeHtml).join(" / ")} · ${escapeHtml(tpl.condition_name || "通用")}。
                应用后以方案开始日期为第 1 天，自动排入一周训练（隔天训练）。
              </div>
              <div class="grid cols-3" style="gap:10px">
                ${tpl.stages.map((s) => `
                  <div class="card" style="padding:12px">
                    <b style="font-size:13px">${escapeHtml(s.name)}</b>
                    <div style="font-size:11px;color:var(--text-2);min-height:46px;margin:4px 0">${escapeHtml(s.description)}</div>
                    <div style="font-size:11px;line-height:1.7;margin-bottom:8px">${s.items.map((i) => `• ${escapeHtml(i.exercise_name)}（${i.sets}组×${i.reps}）`).join("<br>")}</div>
                    <button class="btn sm" data-stage="${s.key}">应用到方案</button>
                  </div>`).join("")}
              </div>`;
            box.querySelectorAll("[data-stage]").forEach((btn) => {
              btn.onclick = () => {
                const stage = tpl.stages.find((s) => s.key === btn.dataset.stage);
                const start = modal.querySelector("#p-start").value || today;
                const base = new Date(`${start}T00:00:00`);
                let added = 0;
                stage.items.forEach((it) => {
                  const d = new Date(base);
                  d.setDate(d.getDate() + it.day_offset);
                  const dayStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
                  if (items.some((i) => i.exercise_name === it.exercise_name && i.day_date === dayStr)) return;
                  items.push({
                    day_date: dayStr, exercise_name: it.exercise_name,
                    sets: it.sets || 3, reps: it.reps || 12,
                    weight_suggest: it.weight_suggest || 0, rest_sec: 90,
                    note: it.note || "", sort_order: items.length,
                  });
                  added += 1;
                });
                renderRows();
                box.innerHTML = "";
                toast(`已应用「${stage.name}」模板，新增 ${added} 个动作`, "success");
              };
            });
          } catch (err) { toast(err.message, "error"); }
        };

        modal.querySelector("#p-save").onclick = async () => {
          const payload = {
            student_id: +modal.querySelector("#p-student").value,
            title: modal.querySelector("#p-title").value.trim(),
            description: modal.querySelector("#p-desc").value,
            start_date: modal.querySelector("#p-start").value,
            end_date: modal.querySelector("#p-end").value,
            items: items.filter((i) => i.exercise_name && i.day_date).map((i, idx) => ({ ...i, sort_order: idx })),
          };
          if (!payload.title) return toast("请填写计划标题", "warn");
          if (!payload.items.length) return toast("请至少添加一个动作", "warn");
          try {
            if (planId) await api(`/api/coach/plans/${planId}`, { method: "PUT", body: payload });
            else await api("/api/coach/plans", { method: "POST", body: payload });
            closeModal(); toast("计划已保存并通知患者", "success"); load();
          } catch (err) { toast(err.message, "error"); }
        };
      },
    });
  }

  el.innerHTML = `
    <div class="card">
      <div class="filter-bar">
        <button class="btn" id="btn-new-plan">+ 创建康复方案</button>
        <button class="btn ghost sm" id="btn-new-ex">+ 自定义动作</button>
        <span style="flex:1"></span>
        <span style="color:var(--text-2);font-size:13px">保存后患者立即可见；点击「推荐给患者」可让计划在患者端优先展示</span>
      </div>
      <div id="plans-list"></div>
    </div>`;

  const list = el.querySelector("#plans-list");
  el.querySelector("#btn-new-plan").onclick = () => openPlanForm(null);
  el.querySelector("#btn-new-ex").onclick = () => {
    openModal({
      title: "自定义动作",
      content: `
        <div class="grid cols-2">
          <div class="field"><label>动作名称</label><input id="e-name" maxlength="100"></div>
          <div class="field"><label>部位分类</label><select id="e-cat">
            ${["肩部", "肘腕", "颈腰椎", "胸背", "核心躯干", "髋部", "膝部", "踝足", "平衡步态", "心肺全身", "综合"].map((c) => `<option>${c}</option>`).join("")}
          </select></div>
          <div class="field"><label>器械</label><input id="e-eq" value="自重"></div>
          <div class="field"><label>难度</label><select id="e-diff"><option value="1">早期</option><option value="2">中期</option><option value="3">后期</option></select></div>
          <div class="field"><label>默认组数</label><input id="e-sets" type="number" value="3"></div>
          <div class="field"><label>默认次数</label><input id="e-reps" type="number" value="12"></div>
          <div class="field"><label>默认建议重量kg</label><input id="e-w" type="number" value="0"></div>
        </div>`,
      footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">取消</button>
               <button class="btn" id="e-save">保存动作</button>`,
      onMount(modal) {
        modal.querySelector("#e-save").onclick = async () => {
          const name = modal.querySelector("#e-name").value.trim();
          if (!name) return toast("请填写动作名称", "warn");
          try {
            await api("/api/coach/exercises", {
              method: "POST",
              body: {
                name, category: modal.querySelector("#e-cat").value,
                equipment: modal.querySelector("#e-eq").value || "自重",
                difficulty: +modal.querySelector("#e-diff").value,
                default_sets: +modal.querySelector("#e-sets").value || 3,
                default_reps: +modal.querySelector("#e-reps").value || 12,
                default_weight: +modal.querySelector("#e-w").value || 0,
              },
            });
            closeModal(); toast("动作已加入康复动作库", "success");
          } catch (err) { toast(err.message, "error"); }
        };
      },
    });
  };
  load();
}

/* ================= 线上指导 ================= */
async function viewGuide(el) {
  killCharts();
  const [feed, makeups] = await Promise.all([
    api("/api/coach/checkin-feed?days=7"),
    api("/api/coach/makeup-requests?status=pending"),
  ]);

  function renderMakeups() {
    box.innerHTML = makeups.length ? makeups.map((m) => `
      <div class="feed-item card" style="padding:14px">
        <div class="head">
          ${avatarHtml(m.student_name, m.avatar)}
          <div><b>${escapeHtml(m.student_name)}</b>
            <div style="color:var(--text-2);font-size:12px">申请补签 ${m.checkin_date}</div></div>
          <span style="flex:1"></span>
          <button class="btn sm" data-ok="${m.id}">通过</button>
          <button class="btn danger sm" data-no="${m.id}">驳回</button>
        </div>
        <div style="font-size:13px;color:var(--text-2)">原因：${escapeHtml(m.reason || "-")}</div>
      </div>`).join("") : `<div class="empty" style="padding:16px">暂无待审批补签</div>`;
    box.querySelectorAll("[data-ok]").forEach((b) => reviewMakeup(+b.dataset.ok, true));
    box.querySelectorAll("[data-no]").forEach((b) => reviewMakeup(+b.dataset.no, false));
  }

  async function reviewMakeup(id, approve) {
    try {
      await api(`/api/coach/makeup-requests/${id}/review`, { method: "POST", body: { approve, review_note: approve ? "" : "不符合补签规则" } });
      toast(approve ? "已通过补签" : "已驳回", "success");
      const idx = makeups.findIndex((m) => m.id === id);
      if (idx >= 0) makeups.splice(idx, 1);
      renderMakeups();
    } catch (err) { toast(err.message, "error"); }
  }

  el.innerHTML = `
    <div class="card mb-16"><div class="section-title">补签审批 <span class="tag warn">${makeups.length} 待处理</span></div>
      <div id="makeup-box"></div>
    </div>
    <div class="card"><div class="section-title">患者康复日志动态（近7天）</div>
      <div class="feed">${feed.length ? feed.map((f) => `
        <div class="feed-item card">
          <div class="head">
            ${avatarHtml(f.student_name, f.student_avatar)}
            <div><b>${escapeHtml(f.student_name)}</b>
              <div style="color:var(--text-2);font-size:12px">${f.checkin_date} · 训练量 ${fmtNum(f.train_volume)}kg · ${f.duration_min}分钟${f.vas_before != null || f.vas_after != null ? ` · VAS ${f.vas_before ?? "-"}→${f.vas_after ?? "-"}` : ""} ${f.is_makeup ? "· 补签" : ""}</div></div>
            <span style="flex:1"></span>
            <span class="tag ${f.intensity >= 4 ? "green" : ""}">强度 ${f.intensity}</span>
          </div>
          <div>${escapeHtml(f.content || "")}</div>
          <div class="comments">
            ${f.comment_count ? "已有点评" : "尚未点评"}
            <div class="flex mt-16">
              <input class="cm-input" data-checkin="${f.id}" placeholder="点评这次康复日志…" maxlength="1000" style="flex:1">
              <button class="btn sm" data-send="${f.id}">发送点评</button>
            </div>
          </div>
        </div>`).join("") : `<div class="empty"><span class="ico">📭</span>近7天暂无康复日志动态</div>`}
      </div>
    </div>`;

  const box = el.querySelector("#makeup-box");
  renderMakeups();

  el.querySelectorAll("[data-send]").forEach((b) => {
    b.onclick = async () => {
      const input = el.querySelector(`.cm-input[data-checkin="${b.dataset.send}"]`);
      const content = input.value.trim();
      if (!content) return toast("请输入点评内容", "warn");
      try {
        await api(`/api/coach/checkins/${b.dataset.send}/comments`, { method: "POST", body: { content } });
        input.value = "";
        toast("点评已发送给患者", "success");
      } catch (err) { toast(err.message, "error"); }
    };
  });
}

/* ================= 消息推送 ================= */
async function viewBatch(el) {
  const students = await api("/api/coach/students");
  const templates = await api("/api/coach/templates");

  el.innerHTML = `
    <div class="grid cols-2">
      <div class="card">
        <div class="section-title">批量发送消息</div>
        <div class="field"><label>发送对象</label>
          <select id="b-target"><option value="all">全部患者</option><option value="student_ids">指定患者</option></select></div>
        <div class="field" id="b-students-box" style="display:none"><label>选择患者（按住 Ctrl 多选）</label>
          <select id="b-students" multiple size="6">
            ${students.map((s) => `<option value="${s.id}">${escapeHtml(s.nickname)}</option>`).join("")}
          </select></div>
        <div class="field"><label>消息内容</label><textarea id="b-content" maxlength="2000" placeholder="训练提醒 / 鼓励消息 / 计划变更通知…"></textarea></div>
        <button class="btn" id="b-send">📣 发送</button>

        <div class="section-title mt-16" style="font-size:14px">消息模板</div>
        <div id="tpl-list">${templates.map((t) => `
          <div class="flex between mb-16" style="border-bottom:1px dashed var(--border);padding-bottom:8px">
            <div><b>${escapeHtml(t.title)}</b> <span class="tag gray">${escapeHtml(t.category)}</span>
              <div style="color:var(--text-2);font-size:12px">${escapeHtml(t.content)}</div></div>
            <span class="flex">
              ${t.coach_id ? `<button class="btn ghost sm" data-use="${escapeHtml(t.content)}">使用</button><button class="btn danger sm" data-tpl-del="${t.id}">删</button>` : `<button class="btn ghost sm" data-use="${escapeHtml(t.content)}">使用</button>`}
            </span>
          </div>`).join("")}</div>
        <button class="btn ghost sm" id="tpl-new">+ 新建模板</button>
      </div>
      <div class="card">
        <div class="section-title">发送提示</div>
        <p style="color:var(--text-2)">· 支持向全部患者或指定患者发送训练提醒、鼓励消息、计划变更通知。</p>
        <p style="color:var(--text-2)">· 消息将通过 WebSocket 实时推送给在线患者。</p>
        <p style="color:var(--text-2)">· 系统预置模板对所有康复治疗师可见，自定义模板仅自己可见。</p>
        <p style="color:var(--text-2)">· 1 对 1 聊天请前往「聊天」页面。</p>
      </div>
    </div>`;

  el.querySelector("#b-target").onchange = (e) => {
    el.querySelector("#b-students-box").style.display = e.target.value === "student_ids" ? "block" : "none";
  };
  el.querySelectorAll("[data-use]").forEach((b) => {
    b.onclick = () => (el.querySelector("#b-content").value = b.dataset.use);
  });
  el.querySelectorAll("[data-tpl-del]").forEach((b) => {
    b.onclick = async () => {
      await api(`/api/coach/templates/${b.dataset.tplDel}`, { method: "DELETE" });
      toast("模板已删除", "success"); viewBatch(el);
    };
  });
  el.querySelector("#tpl-new").onclick = () => {
    openModal({
      title: "新建消息模板",
      content: `
        <div class="field"><label>模板标题</label><input id="t-title" maxlength="100"></div>
        <div class="field"><label>分类</label><input id="t-cat" value="通用" maxlength="50"></div>
        <div class="field"><label>内容</label><textarea id="t-content" maxlength="1000"></textarea></div>`,
      footer: `<button class="btn" id="t-save">保存</button>`,
      onMount(m) {
        m.querySelector("#t-save").onclick = async () => {
          const title = m.querySelector("#t-title").value.trim();
          const content = m.querySelector("#t-content").value.trim();
          if (!title || !content) return toast("请填写完整", "warn");
          await api("/api/coach/templates", { method: "POST", body: { title, content, category: m.querySelector("#t-cat").value } });
          closeModal(); toast("模板已保存", "success"); viewBatch(el);
        };
      },
    });
  };
  el.querySelector("#b-send").onclick = async () => {
    const target = el.querySelector("#b-target").value;
    const content = el.querySelector("#b-content").value.trim();
    if (!content) return toast("请输入消息内容", "warn");
    const student_ids = target === "student_ids"
      ? [...el.querySelector("#b-students").selectedOptions].map((o) => +o.value) : [];
    try {
      const res = await api("/api/coach/messages/batch", { method: "POST", body: { target, student_ids, msg_type: "text", content } });
      toast(`已发送给 ${res.sent} 位患者`, "success");
      el.querySelector("#b-content").value = "";
    } catch (err) { toast(err.message, "error"); }
  };
}

/* ================= 我的 ================= */
async function viewProfile(el) {
  const user = await api("/api/auth/me");
  const cp = user.coach_profile || {};
  el.innerHTML = `
    <div class="grid cols-2">
      <div class="card">
        <div class="section-title">康复治疗师资料</div>
        <div class="flex mb-16" style="gap:16px">
          <div id="avatar-box" style="width:72px;height:72px;flex-shrink:0">
            ${avatarHtml(user.nickname, user.avatar, "")}
          </div>
          <div>
            <div style="font-weight:600;font-size:15px">${escapeHtml(user.nickname)}</div>
            <div style="color:var(--text-2);font-size:12px;margin-bottom:8px">@${escapeHtml(user.username)}</div>
            <label class="btn ghost sm" style="cursor:pointer">上传头像
              <input type="file" id="avatar-input" accept="image/jpeg,image/png,image/gif,image/webp" style="display:none">
            </label>
            <span id="avatar-status" style="color:var(--text-2);font-size:12px;margin-left:8px"></span>
          </div>
        </div>
        <div class="field">
          <label>系统卡通头像（点击直接更换）</label>
          <div id="preset-box" class="flex" style="gap:10px;flex-wrap:wrap"></div>
        </div>
        <div class="mb-16">
          <span class="tag ${{ approved: "green", pending: "warn", rejected: "red", none: "gray" }[cp.review_status || "none"]}">
            ${{ approved: "✔ 已认证", pending: "审核中", rejected: "未通过", none: "未提交" }[cp.review_status || "none"]}
          </span>
        </div>
        ${cp.review_status === "approved" ? `
        <div class="mb-16" style="padding:14px;background:rgba(46,139,132,0.08);border:1px solid rgba(46,139,132,0.25);border-radius:10px">
          <div class="flex between mb-8" style="align-items:center">
            <b style="color:var(--warning)">💼 付费定制计划</b>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px">
              <input type="checkbox" id="paid-switch" ${cp.accept_paid_plan ? "checked" : ""}>
              接受患者付费定制
            </label>
          </div>
          <div style="color:var(--text-2);font-size:12px;margin-bottom:8px">开启后，患者可在会员中心购买你的定制计划（¥${cp.paid_plan_price || 49}/次，平台抽佣${cp.commission_rate || 15}%，你到手${cp.paid_plan_price ? (cp.paid_plan_price * (100 - cp.commission_rate) / 100).toFixed(0) : 41}元/次）</div>
          <div class="flex wrap" style="gap:10px">
            <div class="field" style="margin:0"><label>定价(元/次)</label><input type="number" id="paid-price" min="19" max="299" step="1" value="${cp.paid_plan_price || 49}" style="width:120px"></div>
            <div class="field" style="margin:0"><label>平台抽佣(%)</label><input type="number" id="paid-comm" min="5" max="50" step="1" value="${cp.commission_rate || 15}" style="width:120px"></div>
            <button class="btn purple" id="paid-save" style="align-self:flex-end">保存设置</button>
          </div>
        </div>` : `<div style="padding:10px;background:rgba(148,163,184,0.08);border-radius:8px;color:var(--text-2);font-size:12px;margin-bottom:16px">💼 付费定制计划：认证通过后可开启</div>`}
        <form id="coach-form">
          <div class="field"><label>昵称</label><input name="nickname" value="${escapeHtml(user.nickname)}" maxlength="50"></div>
          <div class="field"><label>擅长领域</label><input name="specialty" value="${escapeHtml(cp.specialty || "")}" maxlength="200"></div>
          <div class="field"><label>个人履历</label><textarea name="bio" maxlength="500">${escapeHtml(cp.bio || "")}</textarea></div>
          <button class="btn" type="submit">保存</button>
        </form>
      </div>
      <div>
        <div class="card mb-16">
          <div class="section-title">账号安全</div>
          <form id="pwd-form">
            <div class="field"><label>原密码</label><input type="password" name="old" required></div>
            <div class="field"><label>新密码</label><input type="password" name="new" minlength="6" required></div>
            <button class="btn warn" type="submit">修改密码</button>
          </form>
        </div>
        ${cp.review_status === "rejected" ? `<div class="card"><div class="tag red">认证未通过</div><p style="color:var(--text-2);margin-top:8px">${escapeHtml(cp.review_note || "")}</p></div>` : ""}
      </div>
    </div>`;
  el.querySelector("#avatar-input").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const status = el.querySelector("#avatar-status");
    status.textContent = "上传中…";
    try {
      const up = await uploadFile(file, "avatar");
      await api("/api/auth/me", { method: "PUT", body: { avatar: up.path } });
      updateAvatar(up.path);
      el.querySelector("#avatar-box").innerHTML = avatarHtml(user.nickname, up.path, "");
      status.textContent = "已更新";
      toast("头像已更新", "success");
    } catch (err) {
      status.textContent = "";
      toast(err.message, "error");
    }
    e.target.value = "";
  };

  const presetBox = el.querySelector("#preset-box");
  api("/api/auth/avatar-presets").then((presets) => {
    if (!presets || !presets.length) { presetBox.closest(".field").style.display = "none"; return; }
    presetBox.innerHTML = presets.map((p) => `
      <img src="${p.url}" alt="头像" title="点击使用此头像"
        data-path="${p.path}"
        style="width:56px;height:56px;border-radius:50%;cursor:pointer;object-fit:cover;border:2px solid ${user.avatar === p.path ? "var(--primary)" : "var(--border)"};transition:all .18s"
        onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform=''">`).join("");
    presetBox.querySelectorAll("img[data-path]").forEach((img) => {
      img.onclick = async () => {
        try {
          await api("/api/auth/me", { method: "PUT", body: { avatar: img.dataset.path } });
          updateAvatar(img.dataset.path);
          user.avatar = img.dataset.path;
          el.querySelector("#avatar-box").innerHTML = avatarHtml(user.nickname, img.dataset.path, "");
          presetBox.querySelectorAll("img").forEach((x) => { x.style.borderColor = "var(--border)"; });
          img.style.borderColor = "var(--primary)";
          toast("头像已更新", "success");
        } catch (err) { toast(err.message, "error"); }
      };
    });
  }).catch(() => { presetBox.closest(".field").style.display = "none"; });
  el.querySelector("#coach-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    await api("/api/auth/me", {
      method: "PUT",
      body: { nickname: fd.get("nickname"), coach_specialty: fd.get("specialty"), coach_bio: fd.get("bio") },
    });
    toast("资料已更新", "success");
  };
  el.querySelector("#pwd-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/auth/password", { method: "PUT", body: { old_password: fd.get("old"), new_password: fd.get("new") } });
      toast("密码修改成功", "success"); e.target.reset();
    } catch (err) { toast(err.message, "error"); }
  };
  // 付费定制设置
  const paidSave = el.querySelector("#paid-save");
  if (paidSave) paidSave.onclick = async () => {
    try {
      await api("/api/member/coach-paid-setting", {
        method: "PUT",
        body: {
          accept_paid_plan: el.querySelector("#paid-switch").checked,
          paid_plan_price: +el.querySelector("#paid-price").value || 49,
          commission_rate: +el.querySelector("#paid-comm").value || 15,
        },
      });
      toast("付费定制设置已保存", "success");
    } catch (err) { toast(err.message, "error"); }
  };
}

/* ================= 待办预警 ================= */
async function sendFollowupReminder(patientId, patientName, defaultText, onDone) {
  openModal({
    title: `发送康复提醒 · ${escapeHtml(patientName)}`,
    content: `
      <div class="field"><label>提醒内容</label>
        <textarea id="fu-content" rows="4" maxlength="500">${escapeHtml(defaultText || "请按时完成康复训练并记录康复日志，如有不适及时联系治疗师。")}</textarea></div>
      <div style="font-size:12px;color:var(--text-2)">将同时发送站内消息并记录一条已发送随访。</div>`,
    footer: `<button class="btn ghost" id="fu-cancel">取消</button><button class="btn" id="fu-send">发送提醒</button>`,
    onMount(modal) {
      modal.querySelector("#fu-cancel").onclick = closeModal;
      modal.querySelector("#fu-send").onclick = async () => {
        try {
          await api("/api/rehab/followups/send-reminder", {
            method: "POST",
            body: { patient_id: patientId, content: modal.querySelector("#fu-content").value.trim() },
          });
          closeModal();
          toast("提醒已发送给患者", "success");
          onDone && onDone();
        } catch (err) { toast(err.message, "error"); }
      };
    },
  });
}

async function renderFollowupList(box) {
  const rows = await api("/api/rehab/followups");
  box.innerHTML = rows.length ? rows.map((f) => `
    <div class="flex between" style="padding:9px 0;border-bottom:1px solid var(--border);gap:12px">
      <div style="min-width:0">
        <b style="font-size:13px">${escapeHtml(f.patient_name)}</b>
        <span class="tag ${f.status === "pending" ? "warn" : "green"}">${f.status === "pending" ? "待发送" : "已发送"}</span>
        <div style="font-size:12px;color:var(--text-2)">${escapeHtml(f.content)} · ${escapeHtml(f.due_date || "")}${f.sent_at ? ` · 发送于 ${escapeHtml(f.sent_at.slice(0, 16))}` : ""}</div>
      </div>
      ${f.status === "pending" ? `<button class="btn sm" data-fu-send="${f.id}">发送</button>` : ""}
    </div>`).join("") : '<div class="empty">暂无随访记录</div>';
  box.querySelectorAll("[data-fu-send]").forEach((b) => {
    b.onclick = async () => {
      try {
        await api(`/api/rehab/followups/${b.dataset.fuSend}/send`, { method: "POST" });
        toast("随访提醒已发送", "success");
        renderFollowupList(box);
      } catch (err) { toast(err.message, "error"); }
    };
  });
}

async function viewAlerts(el) {
  killCharts();
  const data = await api("/api/rehab/alerts");
  const levelTag = { high: '<span class="tag red">高危</span>', warn: '<span class="tag warn">关注</span>' };
  el.innerHTML = `
    <div class="flex between wrap mb-16" style="align-items:center">
      <div class="section-title" style="margin:0">🔔 待办预警</div>
      <div class="flex" style="gap:8px;align-items:center">
        <span class="tag red">高危 ${data.summary.high}</span>
        <span class="tag warn">关注 ${data.summary.warn}</span>
        <span class="tag">涉及患者 ${data.summary.patients}</span>
        <button class="btn ghost sm" id="alert-refresh">刷新</button>
      </div>
    </div>
    <div class="card mb-16">
      ${data.items.length ? `
      <div style="overflow-x:auto"><table><thead><tr><th>级别</th><th>患者 / 问题</th><th>类型</th><th>预警内容</th><th>操作</th></tr></thead>
      <tbody>${data.items.map((a, i) => `<tr>
        <td>${levelTag[a.level] || '<span class="tag">提示</span>'}</td>
        <td><b style="font-size:13px">${escapeHtml(a.patient_name)}</b>
          <div style="font-size:11px;color:var(--text-2)">${escapeHtml(a.condition_name || "-")}</div></td>
        <td style="font-size:13px">${escapeHtml(a.title)}</td>
        <td style="font-size:12px;color:var(--text-2);max-width:420px">${escapeHtml(a.message)}</td>
        <td><button class="btn ghost sm" data-alert="${i}">${escapeHtml(a.action || "查看")}</button></td>
      </tr>`).join("")}</tbody></table></div>` : `
      <div class="empty" style="padding:32px 0"><span class="ico">✅</span><p>暂无待办预警，患者训练与复评情况良好</p></div>`}
    </div>
    <div class="card">
      <div class="section-title">📨 随访提醒记录</div>
      <div id="fu-list"><span style="color:var(--text-2);font-size:13px">加载中…</span></div>
    </div>`;

  el.querySelector("#alert-refresh").onclick = () => viewAlerts(el);
  el.querySelectorAll("[data-alert]").forEach((b) => {
    b.onclick = () => {
      const a = data.items[+b.dataset.alert];
      if (a.action === "发送提醒") {
        sendFollowupReminder(a.patient_id, a.patient_name, a.message, () => viewAlerts(el));
      } else if (a.action === "去评估") {
        focusAssessment(a.patient_id);
        location.hash = "#/assess";
      } else {
        location.hash = "#/cases";
      }
    };
  });
  renderFollowupList(el.querySelector("#fu-list"));
}

/* ================= 排班预约 ================= */
const APPT_STATUS = { booked: ["待就诊", "warn"], completed: ["已完成", "green"], cancelled: ["已取消", "gray"] };

async function viewSchedule(el) {
  killCharts();
  const [schedules, appts, students, cards] = await Promise.all([
    api("/api/rehab/schedules"),
    api("/api/rehab/appointments"),
    api("/api/coach/all-students"),
    api("/api/rehab/treatment-cards"),
  ]);
  const tomorrow = new Date(Date.now() + 864e5).toISOString().slice(0, 10);
  const today = new Date().toISOString().slice(0, 10);

  el.innerHTML = `
    <div class="grid cols-2" style="grid-template-columns: 1fr 1.6fr;align-items:start">
      <div class="card">
        <div class="section-title">🗓️ 新增排班</div>
        <div class="grid cols-2">
          <div class="field"><label>出诊日期</label><input type="date" id="s-date" value="${tomorrow}"></div>
          <div class="field"><label>可预约人数</label><input type="number" id="s-cap" min="1" value="2"></div>
          <div class="field"><label>开始时间</label><input type="time" id="s-start" value="09:00"></div>
          <div class="field"><label>结束时间</label><input type="time" id="s-end" value="12:00"></div>
          <div class="field"><label>每个号源（分钟）</label><input type="number" id="s-slot" min="10" value="30"></div>
          <div class="field"><label>地点</label><input id="s-loc" value="康衡康复中心 · 治疗区"></div>
        </div>
        <div class="field"><label>备注</label><input id="s-note" placeholder="如：术后评估专场"></div>
        <button class="btn" id="s-save" style="width:100%">保存排班</button>
      </div>
      <div class="card">
        <div class="section-title">📅 我的排班 <span class="tag">未来 30 天</span></div>
        <div style="max-height:420px;overflow:auto">
        ${schedules.length ? `<table><thead><tr><th>日期</th><th>时间</th><th>人数</th><th>地点</th><th></th></tr></thead><tbody>
          ${schedules.map((s) => `<tr>
            <td>${escapeHtml(s.work_date)}</td>
            <td>${escapeHtml(s.start_time)}-${escapeHtml(s.end_time)}</td>
            <td>${s.booked}/${s.capacity}${s.remaining ? "" : ' <span class="tag red">已满</span>'}</td>
            <td style="font-size:12px;color:var(--text-2)">${escapeHtml(s.location || "-")}</td>
            <td><button class="btn danger sm" data-del-s="${s.id}">删除</button></td></tr>`).join("")}
        </tbody></table>` : '<div class="empty">暂无排班</div>'}
        </div>
      </div>
    </div>
    <div class="card mt-16">
      <div class="section-title">📋 预约列表</div>
      ${appts.length ? `<div style="overflow-x:auto"><table><thead><tr><th>日期</th><th>时间</th><th>患者</th><th>类型</th><th>状态</th><th>备注</th><th>操作</th></tr></thead><tbody>
        ${appts.map((a) => {
          const st = APPT_STATUS[a.status] || [a.status, "gray"];
          return `<tr>
            <td>${escapeHtml(a.appt_date)}</td><td>${escapeHtml(a.start_time)}-${escapeHtml(a.end_time || "")}</td>
            <td><b style="font-size:13px">${escapeHtml(a.patient_name)}</b></td>
            <td>${escapeHtml(a.appt_type)}</td><td><span class="tag ${st[1]}">${st[0]}</span></td>
            <td style="font-size:12px;color:var(--text-2)">${escapeHtml(a.note || "-")}</td>
            <td class="flex" style="gap:6px">${a.status === "booked" ? `
              <button class="btn green sm" data-done="${a.id}">完成到诊</button>
              <button class="btn ghost sm" data-cancel="${a.id}">取消</button>` : "-"}</td>
          </tr>`;
        }).join("")}</tbody></table></div>` : '<div class="empty">暂无预约</div>'}
    </div>
    <div class="card mt-16">
      <div class="section-title">🎫 疗程卡
        <button class="btn ghost sm" id="card-new">＋ 新增疗程卡</button></div>
      ${cards.length ? `<div class="grid cols-3">${cards.map((c) => `
        <div class="card" style="padding:12px">
          <b style="font-size:13px">${escapeHtml(c.title)}</b>
          <div style="font-size:12px;color:var(--text-2);margin:4px 0">${escapeHtml(c.patient_name)} · ${escapeHtml(c.valid_from || "-")} ~ ${escapeHtml(c.valid_to || "-")}</div>
          <div class="flex between" style="font-size:12px;margin-bottom:4px"><span>已用 ${c.used_sessions} / ${c.total_sessions} 次</span><b style="color:${c.remaining > 2 ? "var(--success)" : "var(--danger)"}">剩余 ${c.remaining}</b></div>
          <div style="height:7px;background:var(--border);border-radius:99px;overflow:hidden">
            <div style="height:100%;width:${Math.min(100, c.used_sessions / c.total_sessions * 100)}%;background:var(--primary)"></div></div>
        </div>`).join("")}</div>` : '<div class="empty">暂无疗程卡</div>'}
    </div>`;

  el.querySelector("#s-save").onclick = async () => {
    try {
      await api("/api/rehab/schedules", {
        method: "POST",
        body: {
          work_date: el.querySelector("#s-date").value, start_time: el.querySelector("#s-start").value,
          end_time: el.querySelector("#s-end").value, capacity: +el.querySelector("#s-cap").value || 1,
          slot_min: +el.querySelector("#s-slot").value || 30, location: el.querySelector("#s-loc").value,
          note: el.querySelector("#s-note").value,
        },
      });
      toast("排班已保存", "success"); viewSchedule(el);
    } catch (err) { toast(err.message, "error"); }
  };
  el.querySelectorAll("[data-del-s]").forEach((b) => {
    b.onclick = () => confirmBox("删除该排班？已预约的患者不受影响。", async () => {
      try {
        await api(`/api/rehab/schedules/${b.dataset.delS}`, { method: "DELETE" });
        closeModal(); toast("排班已删除", "success"); viewSchedule(el);
      } catch (err) { toast(err.message, "error"); }
    });
  });
  el.querySelectorAll("[data-done]").forEach((b) => {
    b.onclick = () => confirmBox("确认患者已到诊？将自动扣减 1 次疗程。", async () => {
      try {
        const res = await api(`/api/rehab/appointments/${b.dataset.done}/complete`, { method: "POST" });
        closeModal();
        toast(res.card_remaining === null ? "已标记完成（该患者暂无可用疗程卡）" : `已到诊，疗程剩余 ${res.card_remaining} 次`, "success");
        viewSchedule(el);
      } catch (err) { toast(err.message, "error"); }
    });
  });
  el.querySelectorAll("[data-cancel]").forEach((b) => {
    b.onclick = () => confirmBox("取消该预约？", async () => {
      try {
        await api(`/api/rehab/appointments/${b.dataset.cancel}/cancel`, { method: "POST" });
        closeModal(); toast("预约已取消", "success"); viewSchedule(el);
      } catch (err) { toast(err.message, "error"); }
    });
  });
  el.querySelector("#card-new").onclick = () => openModal({
    title: "新增疗程卡",
    content: `
      <div class="grid cols-2">
        <div class="field"><label>患者</label><select id="tc-patient">${students.map((s) => `<option value="${s.id}">${escapeHtml(s.nickname)}</option>`).join("")}</select></div>
        <div class="field"><label>名称</label><input id="tc-title" value="康复治疗疗程卡（10次）"></div>
        <div class="field"><label>总次数</label><input type="number" id="tc-total" min="1" value="10"></div>
        <div class="field"><label>有效期至</label><input type="date" id="tc-to" value="${new Date(Date.now() + 90 * 864e5).toISOString().slice(0, 10)}"></div>
      </div>
      <div class="field"><label>备注</label><input id="tc-note" placeholder="含评估、理疗与训练指导"></div>`,
    footer: `<button class="btn ghost" id="tc-cancel">取消</button><button class="btn" id="tc-save">创建疗程卡</button>`,
    onMount(modal) {
      modal.querySelector("#tc-cancel").onclick = closeModal;
      modal.querySelector("#tc-save").onclick = async () => {
        try {
          await api("/api/rehab/treatment-cards", {
            method: "POST",
            body: {
              patient_id: +modal.querySelector("#tc-patient").value,
              title: modal.querySelector("#tc-title").value.trim() || "康复治疗疗程卡",
              total_sessions: +modal.querySelector("#tc-total").value || 10,
              valid_from: today, valid_to: modal.querySelector("#tc-to").value || null,
              note: modal.querySelector("#tc-note").value,
            },
          });
          closeModal(); toast("疗程卡已创建", "success"); viewSchedule(el);
        } catch (err) { toast(err.message, "error"); }
      };
    },
  });
}

export function initCoach() {
  registerViews("coach", {
    students: viewStudents,
    cases: viewRehabCases,
    assess: viewAssessments,
    plans: viewPlans,
    alerts: viewAlerts,
    schedule: viewSchedule,
    guide: viewGuide,
    community: viewCommunity,
    earnings: viewCoachEarnings,
    batch: viewBatch,
    messages: renderChat,
    profile: viewProfile,
  });
}
