import { api, uploadFile } from "./api.js";
import { toast, openModal, closeModal, confirmBox, particles, escapeHtml, fmtNum, fmtDate, fmtTime, registerViews, me, setMe, updateAvatar, avatarHtml, isTimed, localDate } from "./app.js";
import { renderHeatmap } from "./heatmap.js";
import { renderChat } from "./chat.js";
import { viewExercises } from "./exercises.js";
import { viewCommunity } from "./community.js";
import { viewMemberContent, renderInvite, renderCoupons } from "./features.js";
import { viewRehabCases, viewAssessments, viewTcmConstitution } from "./rehab.js";

const charts = [];
function killCharts() { charts.forEach((c) => c.destroy && c.destroy()); charts.length = 0; }
function afterRender(fn) { requestAnimationFrame(fn); }

const DARK_GRID = { color: "#B2BEC3", font: { size: 11 } };
Chart.defaults.color = "#6B8580";
Chart.defaults.borderColor = "#D6E6E2";

/* ================= 数据总览 ================= */
async function viewDashboard(el) {
  killCharts();
  const user = me();
  const [d, anns] = await Promise.all([api("/api/student/dashboard"), api("/api/announcements")]);

  el.innerHTML = `
    <div class="stat-cards">
      <div class="stat-card ${d.checked_today ? "green" : ""}">
        <div class="label">${d.checked_today ? "今日已康复日志" : "今日待康复日志"}</div>
        <div class="value">${d.checked_today ? "✅ 完成" : "—"}</div>
        <div class="sub">连续 ${d.current_streak} 天 · 最长 ${d.longest_streak} 天</div>
      </div>
      <div class="stat-card"><div class="label">本月康复日志</div><div class="value">${d.month_days}<span style="font-size:14px;color:var(--text-2)"> 天</span></div><div class="sub">累计 ${d.total_days} 天</div></div>
      <div class="stat-card purple"><div class="label">本月康复时长</div><div class="value">${fmtNum(d.month_duration)}<span style="font-size:14px;color:var(--text-2)"> 分钟</span></div><div class="sub">完成 ${d.month_days} 天康复日志</div></div>
      <div class="stat-card ${d.weight_change < 0 ? "green" : d.weight_change > 0 ? "warn" : ""}"><div class="label">近90天体重变化</div><div class="value">${d.weight_change > 0 ? "+" : ""}${d.weight_change}<span style="font-size:14px;color:var(--text-2)"> kg</span></div><div class="sub">${d.body_series.length} 条记录</div></div>
    </div>

    <div class="grid cols-2 mb-16">
      <div class="card"><div class="section-title">本周康复时长</div><div id="week-chart" style="height:260px"></div></div>
      <div class="card"><div class="section-title">体重 / 体脂趋势（近90天）</div><div style="height:240px"><canvas id="body-chart"></canvas></div></div>
    </div>

    ${d.today_plan ? `
    <div class="card mb-16">
      <div class="section-title">今日计划 · ${escapeHtml(d.today_plan.title)} <span class="tag">按计划执行康复日志</span></div>
      <table><thead><tr><th>动作</th><th>组数</th><th>次数/秒</th><th>建议重量kg</th><th>休息</th><th>备注</th></tr></thead>
      <tbody>${d.today_plan.items.map((i) => `<tr><td>${escapeHtml(i.exercise_name)}</td><td class="num">${i.sets}</td><td class="num">${isTimed(i.exercise_name) ? i.reps + "秒" : i.reps}</td><td class="num">${isTimed(i.exercise_name) ? "-" : i.weight_suggest}</td><td class="num">${i.rest_sec}s</td><td>${escapeHtml(i.note || "-")}</td></tr>`).join("")}</tbody></table>
    </div>` : ""}

    <div class="grid cols-2">
      <div class="card"><div class="section-title">最近里程碑</div>
        ${d.recent_badges.length ? d.recent_badges.map((b) => `
          <div class="flex mb-16"><span style="font-size:28px">${b.icon}</span>
          <div><b>${escapeHtml(b.name)}</b><div style="color:var(--text-2);font-size:12px">${fmtDate(b.unlocked_at)} 解锁</div></div></div>`).join("")
        : `<div class="empty"><span class="ico">🏅</span>还没有里程碑，快去康复日志解锁吧</div>`}
        <a href="#/achievements" class="btn ghost sm">查看里程碑墙 →</a>
      </div>
      <div class="card"><div class="section-title">公告</div>
        ${anns.map((a) => `<div class="mb-16"><b>${a.is_pinned ? "📌 " : ""}${escapeHtml(a.title)}</b>
          <div style="color:var(--text-2);font-size:13px">${escapeHtml(a.content)}</div>
          <div style="color:var(--text-2);font-size:12px">${fmtDate(a.publish_at)}</div></div>`).join("") || `<div class="empty">暂无公告</div>`}
      </div>
    </div>`;

  if (!d.checked_today) {
    const top = document.getElementById("topbar-actions");
    top.innerHTML = `<button class="btn" id="go-checkin">✅ 去康复日志</button>`;
    top.querySelector("#go-checkin").onclick = () => (location.hash = "#/checkin");
  }

  afterRender(() => {
    const week = echarts.init(document.getElementById("week-chart"));
    const days = d.week_series.map((w) => w.date.slice(5));
    week.setOption({
      grid: { left: 46, right: 46, top: 30, bottom: 26 },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: days, axisLine: { lineStyle: { color: "#D6E6E2" } } },
      yAxis: [
        { type: "value", name: "训练量kg", splitLine: { lineStyle: { color: "#E4EFEC" } } },
        { type: "value", name: "分钟", splitLine: { show: false } },
      ],
      series: [
        { name: "训练量", type: "bar", data: d.week_series.map((w) => w.volume),
          itemStyle: { color: "#2E8B84", borderRadius: [4, 4, 0, 0] } },
        { name: "康复时长", type: "line", yAxisIndex: 1, data: d.week_series.map((w) => w.duration),
          itemStyle: { color: "#4FA8A0" }, smooth: true },
      ],
    });
    charts.push(week);

    const bodyData = d.body_series.filter((b) => b.weight !== null);
    const ctx = document.getElementById("body-chart").getContext("2d");
    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: bodyData.map((b) => b.date.slice(5)),
        datasets: [
          { label: "体重kg", data: bodyData.map((b) => b.weight), borderColor: "#2E8B84", tension: 0.35, yAxisID: "y" },
          { label: "体脂%", data: d.body_series.filter((b) => b.body_fat !== null).map((b) => b.body_fat),
            borderColor: "#4FA8A0", tension: 0.35, yAxisID: "y1", borderDash: [5, 4] },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: {
          y: { position: "left" }, y1: { position: "right", grid: { drawOnChartArea: false } },
        },
      },
    });
    charts.push(chart);
  });
}

/* ================= 每日康复日志 ================= */
async function viewCheckin(el) {
  killCharts();
  const today = localDate();
  const [streak, plans, adherence] = await Promise.all([
    api("/api/student/streak"), api("/api/student/plans"), api("/api/rehab/adherence"),
  ]);
  const todayPlan = plans.find((p) => p.start_date <= today && p.end_date >= today);

  el.innerHTML = `
    <div class="grid cols-2" style="grid-template-columns: 1.4fr 1fr">
      <div class="card">
        <div class="section-title">今日康复日志 <span class="tag ${streak.checked_today ? "green" : "warn"}">${streak.checked_today ? "已完成" : "未康复日志"}</span></div>
        <form id="checkin-form">
          <div class="field"><label>康复心得（文字康复日志）</label>
            <textarea name="content" maxlength="500" placeholder="记录今天的康复感受、疼痛变化…"></textarea></div>
          <div class="grid cols-2">
            <div class="field"><label>练前疼痛 VAS（0-10）</label><input name="vas_before" type="number" min="0" max="10" value="3"></div>
            <div class="field"><label>练后疼痛 VAS（0-10）</label><input name="vas_after" type="number" min="0" max="10" value="2"></div>
          </div>
          <div class="grid cols-3">
            <div class="field"><label>康复时长（分钟）</label><input name="duration_min" type="number" min="0" max="600" value="60"></div>
            <div class="field"><label>疲劳程度（1-5）</label><input name="intensity" type="number" min="1" max="5" value="3"></div>
            <div class="field"><label>关联计划</label>
              <select name="plan_id"><option value="">不关联</option>
              ${plans.map((p) => `<option value="${p.id}" ${todayPlan && p.id === todayPlan.id ? "selected" : ""}>${escapeHtml(p.title)}</option>`).join("")}
              </select></div>
          </div>
          <div class="field"><label>动作明细（组数×次数×重量 = 训练量；平板支撑等计时动作按「组数×秒」记录）</label>
            <div id="detail-rows"></div>
            <button type="button" class="btn ghost sm" id="add-row">+ 添加动作</button>
          </div>
          <div class="field"><label>图片 / 短视频康复日志（可多选）</label>
            <input type="file" id="media-input" accept="image/*,video/*" multiple>
            <div class="flex wrap" id="media-preview" style="margin-top:8px"></div>
            <button type="button" class="btn purple sm" id="ai-eval-btn" style="margin-top:10px;display:none">🤖 AI 姿势点评（会员专属）</button>
            <div id="ai-eval-result" style="margin-top:10px"></div>
          </div>
          <button class="btn" type="submit" style="width:100%;padding:12px">✅ 提交康复日志</button>
        </form>
      </div>
      <div>
        <div class="card mb-16">
          <div class="section-title">康复日志日历热力图</div>
          <div id="heatmap-box"></div>
        </div>
        <div class="card">
          <div class="section-title">连续康复日志</div>
          <div class="flex" style="gap:20px">
            <div><div class="stat-card green" style="box-shadow:none;border:none;padding:8px"><div class="label">当前连续</div><div class="value">${streak.current_streak}<span style="font-size:13px"> 天</span></div></div></div>
            <div><div class="stat-card purple" style="box-shadow:none;border:none;padding:8px"><div class="label">历史最长</div><div class="value">${streak.longest_streak}<span style="font-size:13px"> 天</span></div></div></div>
          </div>
          <div style="margin-top:14px">
            <button class="btn warn sm" id="btn-makeup">申请补签（需康复治疗师审批）</button>
          </div>
          <div id="makeup-list" style="margin-top:12px;font-size:13px"></div>
        </div>
        <div class="card mt-16">
          <div class="section-title">📊 近 7 天训练依从率</div>
          <div class="flex between" style="align-items:baseline;margin-bottom:8px">
            <div style="font-size:30px;font-weight:800;color:${adherence.rate >= 80 ? "var(--success)" : adherence.rate >= 60 ? "var(--warning)" : "var(--danger)"}">${adherence.rate}%</div>
            <div style="color:var(--text-2);font-size:12px">应训练 ${adherence.target_days} 天 · 已记录 ${adherence.logged_days} 天</div>
          </div>
          <div style="height:8px;background:var(--border);border-radius:99px;overflow:hidden">
            <div style="height:100%;width:${adherence.rate}%;background:${adherence.rate >= 80 ? "var(--success)" : adherence.rate >= 60 ? "var(--warning)" : "var(--danger)"};border-radius:99px"></div>
          </div>
          <div style="color:var(--text-2);font-size:11px;margin-top:6px">${adherence.planned_days ? `本周方案安排 ${adherence.planned_days} 天训练` : "暂无进行中的康复方案，按每日训练计算"} · ${adherence.start_date} ~ ${adherence.end_date}</div>
        </div>
      </div>
    </div>`;

  const media = [];
  const preview = el.querySelector("#media-preview");
  const aiBtn = el.querySelector("#ai-eval-btn");
  const aiResult = el.querySelector("#ai-eval-result");
  el.querySelector("#media-input").onchange = async (e) => {
    for (const file of e.target.files) {
      try {
        const kind = file.type.startsWith("video") ? "video" : "image";
        const up = await uploadFile(file, kind);
        media.push({ path: up.path, kind });
        preview.insertAdjacentHTML("beforeend",
          `<span class="tag ${kind}">${kind === "video" ? "📹" : "🖼️"} 已上传</span>`);
      } catch (err) { toast(err.message, "error"); }
    }
    if (media.some((m) => m.kind === "image")) aiBtn.style.display = "inline-block";
    e.target.value = "";
  };
  aiBtn.onclick = async () => {
    const img = media.find((m) => m.kind === "image");
    if (!img) return toast("请先上传一张动作照片", "warn");
    aiBtn.disabled = true;
    aiResult.innerHTML = '<span style="color:var(--text-2)">🤖 AI 分析中…</span>';
    try {
      const res = await api("/api/features/ai-evaluate", { method: "POST", body: { image_url: img.path } });
      const a = res.analysis;
      aiResult.innerHTML = `
        <div style="padding:12px;background:rgba(99,184,174,0.1);border:1px solid rgba(99,184,174,0.3);border-radius:8px">
          <div class="flex between" style="margin-bottom:8px">
            <b>🤖 AI 姿势评分</b>
            <span style="font-size:20px;font-weight:800;color:${a.score >= 85 ? 'var(--success)' : a.score >= 70 ? 'var(--warning)' : 'var(--danger)'}">${a.score}分</span>
          </div>
          <div style="color:var(--text-2);font-size:13px;margin-bottom:6px">识别动作：${escapeHtml(a.pose)}</div>
          <div style="font-size:13px;line-height:1.7">
            <b>问题：</b>${a.issues.map((i) => `<div>· ${escapeHtml(i)}</div>`).join("")}
            <div style="margin-top:6px"><b>建议：</b>${escapeHtml(a.tips)}</div>
          </div>
        </div>`;
    } catch (err) {
      aiResult.innerHTML = `<div style="color:var(--danger);font-size:13px">${escapeHtml(err.message)}</div>`;
    } finally {
      aiBtn.disabled = false;
    }
  };

  const rowsBox = el.querySelector("#detail-rows");
  function setRowTimed(row, timed) {
    if ((row.dataset.timed === "1") === timed) return;
    row.dataset.timed = timed ? "1" : "0";
    const reps = row.querySelector(".d-reps");
    const weight = row.querySelector(".d-weight");
    reps.placeholder = timed ? "秒" : "次";
    weight.placeholder = timed ? "自重" : "kg";
    weight.disabled = timed;
    if (timed) weight.value = 0;
  }
  function addRow(preset) {
    const p = preset || { exercise_name: "", sets: 3, reps: 12, weight: 30, rpe: 7 };
    const timed = isTimed(p.exercise_name);
    rowsBox.insertAdjacentHTML("beforeend", `
      <div class="plan-items"><div class="pi-row" data-timed="${timed ? 1 : 0}">
        <input class="d-name" placeholder="动作名称" value="${escapeHtml(p.exercise_name)}">
        <input class="d-sets num" type="number" min="0" placeholder="组" value="${p.sets}">
        <input class="d-reps num" type="number" min="0" placeholder="${timed ? "秒" : "次"}" value="${p.reps}">
        <input class="d-weight num" type="number" min="0" step="0.5" placeholder="${timed ? "自重" : "kg"}" value="${timed ? 0 : p.weight}" ${timed ? "disabled" : ""}>
        <input class="d-rpe num" type="number" min="1" max="10" placeholder="RPE" value="${p.rpe || ""}">
        <button type="button" class="pi-del" aria-label="删除">×</button>
      </div></div>`);
    const row = rowsBox.lastElementChild.querySelector(".pi-row");
    row.querySelector(".pi-del").onclick = (ev) => ev.target.closest(".plan-items").remove();
    row.querySelector(".d-name").oninput = (ev) => setRowTimed(row, isTimed(ev.target.value));
  }
  if (todayPlan) {
    const itemMap = {};
    todayPlan.items.filter((i) => i.day_date === today).forEach((i) => {
      const key = i.exercise_name;
      itemMap[key] = itemMap[key] || i;
    });
    Object.values(itemMap).forEach((i) => addRow({ exercise_name: i.exercise_name, sets: i.sets, reps: i.reps, weight: i.weight_suggest || 30 }));
  }
  if (!rowsBox.children.length) addRow();
  el.querySelector("#add-row").onclick = () => addRow();

  el.querySelector("#checkin-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const details = [...rowsBox.querySelectorAll(".pi-row")].map((r) => ({
      exercise_name: r.querySelector(".d-name").value.trim(),
      sets: +r.querySelector(".d-sets").value || 0,
      reps: +r.querySelector(".d-reps").value || 0,
      weight: +r.querySelector(".d-weight").value || 0,
      rpe: +r.querySelector(".d-rpe").value || null,
    })).filter((d) => d.exercise_name);
    const payload = {
      checkin_date: today,
      content: fd.get("content") || "",
      plan_id: fd.get("plan_id") ? +fd.get("plan_id") : null,
      duration_min: +fd.get("duration_min") || 0,
      intensity: +fd.get("intensity") || 3,
      vas_before: fd.get("vas_before") === "" ? null : +fd.get("vas_before"),
      vas_after: fd.get("vas_after") === "" ? null : +fd.get("vas_after"),
      media_paths: media.map((m) => m.path),
      details,
    };
    try {
      const res = await api("/api/student/checkins", { method: "POST", body: payload });
      particles();
      toast(`康复日志成功！连续 ${res.streak.current_streak} 天`, "success");
      if (res.vas_alert) setTimeout(() => toast(res.vas_alert, "warn"), 600);
      if (res.new_badges && res.new_badges.length) {
        openModal({
          title: "🎉 解锁新里程碑",
          content: res.new_badges.map((b) =>
            `<div class="flex mb-16" style="gap:14px"><span style="font-size:36px">${b.icon}</span>
             <div><b style="color:${b.color}">${escapeHtml(b.name)}</b><div style="color:var(--text-2)">${escapeHtml(b.desc)}</div></div></div>`).join(""),
          footer: `<button class="btn" onclick="document.getElementById('modal-root').innerHTML=''">太棒了</button>`,
        });
      }
      viewCheckin(el);
    } catch (err) { toast(err.message, "error"); }
  };

  const hmBox = el.querySelector("#heatmap-box");
  const now = new Date();
  renderHeatmap(hmBox, me().id, now.getFullYear(), now.getMonth() + 1, async (ds) => {
    const today = localDate();
    try {
      const detail = await api(`/api/student/checkins/${ds}`);
      if (!detail || !detail.checkin) { toast("当日无康复日志记录", "warn"); return; }
      openModal({
        title: `${ds} 康复日志详情`,
        content: `
          <p style="margin-bottom:10px">${escapeHtml(detail.checkin.content || "（无文字内容）")}</p>
          <div class="flex" style="gap:8px;flex-wrap:wrap">
            <div class="tag green">训练量 ${detail.checkin.train_volume} kg</div>
            <div class="tag">时长 ${detail.checkin.duration_min} 分钟</div>
            <div class="tag">强度 ${detail.checkin.intensity}/5</div>
            ${detail.checkin.vas_before != null ? `<div class="tag">练前 VAS ${detail.checkin.vas_before}</div>` : ""}
            ${detail.checkin.vas_after != null ? `<div class="tag ${detail.checkin.vas_before != null && detail.checkin.vas_after - detail.checkin.vas_before >= 2 ? "warn" : "green"}">练后 VAS ${detail.checkin.vas_after}</div>` : ""}
            ${detail.checkin.is_makeup ? '<div class="tag warn">补签</div>' : ""}
          </div>
          ${detail.details.length ? `<table class="mt-16"><thead><tr><th>动作</th><th>组</th><th>${detail.details.some((d) => isTimed(d.exercise_name)) ? "次/秒" : "次"}</th><th>kg</th><th>RPE</th><th>心率</th></tr></thead>
            <tbody>${detail.details.map((d) => `<tr><td>${escapeHtml(d.exercise_name)}</td><td class="num">${d.sets}</td><td class="num">${isTimed(d.exercise_name) ? d.reps + "秒" : d.reps}</td><td class="num">${isTimed(d.exercise_name) ? "-" : d.weight}</td><td class="num">${d.rpe ?? "-"}</td><td class="num">${d.heart_rate ?? "-"}</td></tr>`).join("")}</tbody></table>` : ""}
          ${detail.media.length ? `<div class="media mt-16">${detail.media.map((m) => m.media_type === "image" ? `<img src="/uploads/${m.file_path}" style="width:100%;border-radius:8px" alt="康复日志图片">` : `<video src="/uploads/${m.file_path}" controls style="width:100%;border-radius:8px"></video>`).join("")}</div>` : ""}
          ${detail.comments.length ? `<div class="comments mt-16"><b style="color:var(--primary)">康复治疗师点评</b>${detail.comments.map((c) => `<div class="c"><b>${escapeHtml(c.coach_name)}：</b>${escapeHtml(c.content)}</div>`).join("")}</div>` : ""}`,
        footer: detail.checkin.checkin_date === today && !detail.checkin.is_makeup
          ? `<button class="btn danger" id="del-checkin">删除今日康复日志</button><button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`
          : `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`,
        onMount(modal) {
          const del = modal.querySelector("#del-checkin");
          if (del) del.onclick = () => confirmBox("确定删除今日康复日志？删除后连续天数将重新计算。", async () => {
            await api(`/api/student/checkins/${ds}`, { method: "DELETE" });
            closeModal(); toast("已删除", "success"); viewCheckin(el);
          });
        },
      });
    } catch {
      if (ds < today) {
        openMakeupModal(ds);
      } else {
        toast("该日期暂无康复日志记录", "warn");
      }
    }
  });

  function openMakeupModal(presetDate) {
    const today = localDate();
    const weekAgo = localDate(new Date(Date.now() - 6 * 86400000));
    api("/api/student/makeup-requests").then((list) => {
      openModal({
        title: "申请补签",
        content: `
          <div class="field"><label>补签日期（仅限过去 7 天内未康复日志日期）</label>
            <input type="date" id="mu-date" min="${weekAgo}" max="${today}" value="${presetDate || ''}">
            <div style="color:var(--text-2);font-size:12px;margin-top:4px">可选范围：${weekAgo} ~ ${today}</div>
          </div>
          <div class="field"><label>原因（必填）</label><textarea id="mu-reason" maxlength="500" placeholder="说明漏康复日志原因…"></textarea></div>
          <div class="section-title" style="margin-top:16px">历史申请</div>
          ${list.length ? `<table><thead><tr><th>日期</th><th>状态</th><th>备注</th></tr></thead><tbody>
            ${list.map((m) => `<tr><td>${m.checkin_date}</td><td><span class="tag ${m.status === "approved" ? "green" : m.status === "rejected" ? "red" : "warn"}">${{ pending: "待审批", approved: "已通过", rejected: "已驳回" }[m.status]}</span></td><td>${escapeHtml(m.review_note || m.reason || "-")}</td></tr>`).join("")}
          </tbody></table>` : "<div class='empty'>暂无申请记录</div>"}`,
        footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">取消</button><button class="btn warn" id="mu-submit">提交申请</button>`,
        onMount(modal) {
          modal.querySelector("#mu-submit").onclick = async () => {
            const date = modal.querySelector("#mu-date").value;
            if (!date) return toast("请选择日期", "warn");
            const reason = modal.querySelector("#mu-reason").value.trim();
            if (!reason) return toast("请填写补签原因", "warn");
            try {
              await api("/api/student/makeup-requests", {
                method: "POST",
                body: { checkin_date: date, reason },
              });
              closeModal(); toast("申请已提交，等待康复治疗师审批", "success");
              viewCheckin(el);
            } catch (err) { toast(err.message, "error"); }
          };
        },
      });
    });
  }

  el.querySelector("#btn-makeup").onclick = () => openMakeupModal("");
}

/* ================= 康复指标 ================= */
async function viewBody(el) {
  killCharts();
  const records = await api("/api/student/body-records?days=180");
  const last = records[records.length - 1] || {};

  el.innerHTML = `
    <div class="card mb-16">
      <div class="section-title">记录康复指标</div>
      <form id="body-form">
        <div class="grid cols-4">
          <div class="field"><label>日期</label><input type="date" name="record_date" value="${new Date().toISOString().slice(0, 10)}"></div>
          <div class="field"><label>体重 kg</label><input name="weight" type="number" step="0.1" value="${last.weight ?? ""}"></div>
          <div class="field"><label>体脂率 %</label><input name="body_fat" type="number" step="0.1" value="${last.body_fat ?? ""}"></div>
          <div class="field"><label>胸围 cm</label><input name="chest" type="number" step="0.1" value="${last.chest ?? ""}"></div>
          <div class="field"><label>腰围 cm</label><input name="waist" type="number" step="0.1" value="${last.waist ?? ""}"></div>
          <div class="field"><label>臀围 cm</label><input name="hip" type="number" step="0.1" value="${last.hip ?? ""}"></div>
          <div class="field"><label>臂围 cm</label><input name="arm" type="number" step="0.1" value="${last.arm ?? ""}"></div>
          <div class="field"><label>腿围 cm</label><input name="thigh" type="number" step="0.1" value="${last.thigh ?? ""}"></div>
        </div>
        <button class="btn" type="submit">保存记录</button>
      </form>
    </div>
    <div class="grid cols-2 mb-16">
      <div class="card"><div class="section-title">体重 / 体脂趋势</div><div style="height:230px"><canvas id="trend-1"></canvas></div></div>
      <div class="card"><div class="section-title">围度变化</div><div style="height:230px"><canvas id="trend-2"></canvas></div></div>
    </div>
    <div class="card">
      <div class="section-title">记录历史</div>
      <div style="overflow-x:auto"><table><thead><tr><th>日期</th><th>体重</th><th>体脂%</th><th>胸围</th><th>腰围</th><th>臀围</th><th>臂围</th><th>腿围</th></tr></thead>
      <tbody>${[...records].reverse().map((r) => `<tr><td>${r.record_date}</td><td class="num">${r.weight ?? "-"}</td><td class="num">${r.body_fat ?? "-"}</td><td class="num">${r.chest ?? "-"}</td><td class="num">${r.waist ?? "-"}</td><td class="num">${r.hip ?? "-"}</td><td class="num">${r.arm ?? "-"}</td><td class="num">${r.thigh ?? "-"}</td></tr>`).join("") || `<tr><td colspan="8" class="empty">暂无记录</td></tr>`}</tbody></table></div>
    </div>`;

  el.querySelector("#body-form").onsubmit = async (e) => {
    e.preventDefault();
    const payload = Object.fromEntries(new FormData(e.target).entries());
    for (const k of Object.keys(payload)) payload[k] = payload[k] === "" ? null : +payload[k];
    payload.record_date = new FormData(e.target).get("record_date");
    try {
      await api("/api/student/body-records", { method: "POST", body: payload });
      toast("康复指标已保存", "success");
      viewBody(el);
    } catch (err) { toast(err.message, "error"); }
  };

  afterRender(() => {
    const labels = records.map((r) => r.record_date.slice(5));
    const mk = (id, datasets) => new Chart(document.getElementById(id), {
      type: "line",
      data: { labels, datasets },
      options: { responsive: true, maintainAspectRatio: false, tension: 0.35,
        scales: { x: { ticks: { maxTicksLimit: 10 } } } },
    });
    charts.push(mk("trend-1", [
      { label: "体重kg", data: records.map((r) => r.weight), borderColor: "#2E8B84" },
      { label: "体脂%", data: records.map((r) => r.body_fat), borderColor: "#4FA8A0", borderDash: [5, 4] },
    ]));
    const colors = { chest: "#2E8B84", waist: "#F59E0B", hip: "#00E676", arm: "#4FA8A0", thigh: "#EF4444" };
    const names = { chest: "胸围", waist: "腰围", hip: "臀围", arm: "臂围", thigh: "腿围" };
    charts.push(mk("trend-2", Object.keys(colors).map((k) => ({
      label: names[k], data: records.map((r) => r[k]), borderColor: colors[k],
    }))));
  });
}

/* ================= 康复方案 ================= */
async function viewPlans(el) {
  killCharts();
  const today = localDate();
  const [plans, recs, todayCheckin] = await Promise.all([
    api("/api/student/plans"),
    api("/api/student/recommended-plans"),
    api(`/api/student/checkins/${today}`).catch(() => null),
  ]);
  const checkedToday = !!(todayCheckin && todayCheckin.checkin);

  function planCard(p) {
    const days = [...new Set(p.items.map((i) => i.day_date))].sort();
    const todayItems = p.items.filter((i) => i.day_date === today);
    return `
      <div class="card mb-16">
        <div class="flex between wrap">
          <div class="flex">
            ${avatarHtml(p.coach_name || "康复治疗师", p.coach_avatar, "sm")}
            <div>
              <b style="font-size:15px">${escapeHtml(p.title)}</b>
              <div style="color:var(--text-2);font-size:12px">来自 ${escapeHtml(p.coach_name || "康复治疗师")} 的安排 · ${p.start_date} ~ ${p.end_date}</div>
            </div>
          </div>
          ${p.start_date <= today && p.end_date >= today
            ? (checkedToday ? '<span class="tag green">✔ 今日已完成康复日志</span>' : '<span class="tag warn">今日待执行</span>')
            : '<span class="tag gray">已结束</span>'}
        </div>
        ${p.description ? `<p style="color:var(--text-2);font-size:13px;margin-top:10px">${escapeHtml(p.description)}</p>` : ""}
        ${todayItems.length ? `
          <div style="margin-top:14px;padding:12px 14px;background:rgba(46,139,132,0.08);border:1px solid rgba(46,139,132,0.3);border-radius:8px">
            <b style="color:var(--primary);font-size:13px">🎯 今日任务（${todayItems.length} 项）</b>
            <div style="margin-top:8px;font-size:13px;line-height:2">
              ${todayItems.map((i) => `· ${escapeHtml(i.exercise_name)} <span style="color:var(--text-2)">${isTimed(i.exercise_name) ? `${i.sets}组 × ${i.reps}秒（自重）` : `${i.sets}组 × ${i.reps}次${i.weight_suggest ? ` @ ${i.weight_suggest}kg` : ""}`}</span>`).join("<br>")}
            </div>
            ${checkedToday
              ? '<div style="margin-top:8px;color:var(--success);font-size:12px">✔ 今日已康复日志，任务已完成</div>'
              : '<div style="margin-top:8px;color:var(--warning);font-size:12px">完成训练后，去「每日康复日志」记录今日成果</div>'}
          </div>` : ""}
        ${days.map((d) => `
          <div class="mt-16">
            <div class="flex between"><b style="color:var(--primary)">${d}${d === today ? " · 今天" : ""}</b></div>
            <table><thead><tr><th>动作</th><th>组数</th><th>次数</th><th>建议重量</th><th>休息</th></tr></thead>
            <tbody>${p.items.filter((i) => i.day_date === d).map((i) =>
              `<tr><td>${escapeHtml(i.exercise_name)}</td><td class="num">${i.sets}</td><td class="num">${isTimed(i.exercise_name) ? i.reps + "秒" : i.reps}</td><td class="num">${isTimed(i.exercise_name) ? "-" : i.weight_suggest + "kg"}</td><td class="num">${i.rest_sec}s</td></tr>`).join("")}
            </tbody></table>
          </div>`).join("")}
      </div>`;
  }

  el.innerHTML = `
    <div class="card mb-16" style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
      <div style="font-size:26px">📋</div>
      <div style="flex:1;min-width:200px">
        <b>我的康复方案</b>
        <div style="color:var(--text-2);font-size:13px">计划由康复治疗师在康复治疗师端制定并布置，按日执行后到「每日康复日志」记录，坚持完成才能拿到里程碑徽章</div>
      </div>
      ${checkedToday ? '<span class="tag green">✔ 今日已康复日志</span>' : '<a href="#/checkin"><span class="btn sm" style="text-decoration:none">去康复日志</span></a>'}
    </div>
    ${plans.length ? plans.map(planCard).join("") : `<div class="card"><div class="empty"><span class="ico">📋</span>暂无康复方案，等待康复治疗师安排<br><span style="font-size:12px;color:var(--text-2)">可在「社区动态」或「消息」中联系康复治疗师</span></div></div>`}
    ${recs.length ? `<div class="card"><div class="section-title">⭐ 康复治疗师推荐计划</div>
      ${recs.map((p) => `<div class="flex between mb-16" style="border-bottom:1px dashed var(--border);padding-bottom:10px">
        <div><b>${escapeHtml(p.title)}</b><div style="color:var(--text-2);font-size:12px">康复治疗师：${escapeHtml(p.coach_name)} · ${p.start_date}~${p.end_date}</div></div>
        <span class="tag purple">推荐</span></div>`).join("")}</div>` : ""}`;
}

/* ================= 里程碑排行 ================= */
async function viewAchievements(el) {
  killCharts();
  const [badges, rankW, rankM] = await Promise.all([
    api("/api/student/achievements"),
    api("/api/student/rankings?period=week"),
    api("/api/student/rankings?period=month&metric=volume"),
  ]);

  const unlocked = badges.filter((b) => b.unlocked);
  const locked = badges.filter((b) => !b.unlocked);

  function badgeCard(b) {
    return `
      <div class="badge-item ${b.unlocked ? "unlocked" : "locked"}" style="color:${b.color}">
        <div class="ico">${b.icon}</div>
        <div class="name">${escapeHtml(b.name)}</div>
        <div class="desc">${b.unlocked ? fmtDate(b.unlocked_at) + " 解锁" : escapeHtml(b.desc)}</div>
        ${b.unlocked ? "" : `
        <div class="badge-progress">
          <div class="bar"><i style="width:${Math.min(b.percent, 100)}%"></i></div>
          <span class="txt">${b.progress}/${b.target}</span>
        </div>`}
      </div>`;
  }

  function rankTable(r, label) {
    const empty = !r.items.length;
    return `<div class="card"><div class="section-title">${label} ${r.my_rank ? `<span class="tag green">我的排名 #${r.my_rank}</span>` : '<span class="tag gray">未上榜</span>'}</div>
      ${empty ? `<div class="empty"><span class="ico">🏅</span>本周期还没有排行数据<br><a href="#/checkin" class="btn sm mt-16" style="display:inline-block">去康复日志获取里程碑</a></div>`
      : `<table><thead><tr><th>#</th><th>患者</th><th>${r.metric === "days" ? "康复日志天数" : "训练量kg"}</th></tr></thead>
      <tbody>${r.items.map((i) => `<tr><td class="num">${i.rank <= 3 ? ["🥇", "🥈", "🥉"][i.rank - 1] : i.rank}</td><td>${escapeHtml(i.nickname)}</td><td class="num">${fmtNum(i.score)}</td></tr>`).join("")}</tbody></table>`}
    </div>`;
  }

  el.innerHTML = `
    <div class="card mb-16">
      <div class="section-title">里程碑墙 <span class="tag">${unlocked.length}/${badges.length} 已解锁 · 连续/累计康复日志自动发牌</span></div>
      ${unlocked.length ? `<div class="badge-wall">${badges.map(badgeCard).join("")}</div>`
      : `<div class="empty" style="padding:36px 0">
          <span class="ico">🏅</span>
          <p style="margin:8px 0 4px;font-size:15px;font-weight:600">还没有解锁任何里程碑</p>
          <p style="margin-bottom:16px">连续康复日志 3 天即可解锁第一枚徽章「三日入门」</p>
          <a href="#/checkin" class="btn" style="display:inline-block">✅ 去康复日志获取里程碑</a>
        </div>
        <div class="grid cols-4">${locked.slice(0, 4).map(badgeCard).join("")}</div>`}
    </div>
    <div class="grid cols-2">
      ${rankTable(rankW, "本周康复日志榜")}
      ${rankTable(rankM, "本月训练量榜")}
    </div>`;
}

/* ================= 康复资源 ================= */
const BILI_SEARCH = "https://search.bilibili.com/all?keyword=";

const RESOURCES = [
  { icon: "🔍", title: "运动康复综合搜索", desc: "B 站运动康复视频综合搜索，海量康复内容一站式查找", kw: "运动康复", hot: true },
  { icon: "🦴", title: "术后康复训练", desc: "骨科术后分阶段康复动作与注意事项", kw: "术后康复训练" },
  { icon: "💪", title: "肩颈康复", desc: "肩袖损伤、颈椎不适的居家康复训练", kw: "肩颈康复训练" },
  { icon: "🧍", title: "腰背疼痛缓解", desc: "核心稳定训练与慢性腰痛的康复方法", kw: "腰痛康复训练" },
  { icon: "🦵", title: "膝关节康复", desc: "膝关节术后与运动损伤的康复训练", kw: "膝关节康复训练" },
  { icon: "📐", title: "关节活动度训练", desc: "ROM 改善与关节松动训练示范", kw: "关节活动度训练" },
  { icon: "⚖️", title: "平衡与本体感觉", desc: "平衡训练与本体感觉重建，预防再次损伤", kw: "平衡训练" },
  { icon: "🌿", title: "中医导引", desc: "八段锦、五禽戏等传统导引功法跟练", kw: "八段锦" },
];

async function viewResources(el) {
  killCharts();
  el.innerHTML = `
    <div class="card mb-16">
      <div class="section-title">🔗 康复资源 <span class="tag">点击卡片跳转 B 站搜索</span></div>
      <p style="color:var(--text-2);font-size:13px;margin-bottom:16px">
        精选运动康复学习主题，配合康复治疗师计划一起使用效果更佳。点击任意卡片将在新窗口打开对应的 B 站视频搜索结果。
      </p>
      <div class="grid cols-4">
        ${RESOURCES.map((r) => `
          <a class="card resource-card" style="display:block;color:inherit;text-decoration:none;padding:18px"
             href="${BILI_SEARCH}${encodeURIComponent(r.kw)}" target="_blank" rel="noopener noreferrer">
            <div style="font-size:30px">${r.icon}</div>
            <div style="font-weight:600;margin-top:8px">${r.title} ${r.hot ? '<span class="tag green">推荐</span>' : ""}</div>
            <div style="color:var(--text-2);font-size:12px;margin-top:4px">${r.desc}</div>
            <div style="color:var(--primary);font-size:12px;margin-top:8px">在 B 站搜索 →</div>
          </a>`).join("")}
      </div>
    </div>
    <div class="card">
      <div class="section-title">使用建议</div>
      <p style="color:var(--text-2);font-size:13px">· 每日康复日志后可挑选一个主题跟练，并在康复日志时记录动作明细。</p>
      <p style="color:var(--text-2);font-size:13px">· 不确定动作是否标准时，先到「康复动作库」查看动作详解，或把疑问发消息问康复治疗师。</p>
      <p style="color:var(--text-2);font-size:13px">· 训练心得和进步瞬间可以发布到「社区动态」，与大家互相鼓励。</p>
    </div>`;
}

/* ================= 个人主页 ================= */
async function viewProfile(el) {
  const user = await api("/api/auth/me");
  el.innerHTML = `
    <div class="grid cols-2">
      <div class="card">
        <div class="section-title">个人信息</div>
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
        <form id="profile-form">
          <div class="field"><label>昵称</label><input name="nickname" value="${escapeHtml(user.nickname)}" maxlength="50"></div>
          <div class="field"><label>手机号</label><input name="phone" value="${escapeHtml(user.phone || "")}" maxlength="20"></div>
          <div class="field"><label>性别</label><select name="gender">
            <option value="0" ${user.gender === 0 ? "selected" : ""}>未设置</option>
            <option value="1" ${user.gender === 1 ? "selected" : ""}>男</option>
            <option value="2" ${user.gender === 2 ? "selected" : ""}>女</option></select></div>
          <div class="field"><label>每日康复日志提醒时间</label><input type="time" name="reminder_time" value="${(user.reminder_time || "20:00:00").slice(0, 5)}"></div>
          <div class="field"><label>排行榜匿名 <input type="checkbox" name="anonymous" ${user.anonymous_rank ? "checked" : ""} style="width:auto"> 在排行榜中隐藏昵称</label></div>
          <button class="btn" type="submit">保存</button>
        </form>
      </div>
      <div>
        <div class="card mb-16">
          <div class="section-title">账号安全</div>
          <form id="pwd-form">
            <div class="field"><label>原密码</label><input type="password" name="old" required></div>
            <div class="field"><label>新密码（至少6位）</label><input type="password" name="new" minlength="6" required></div>
            <button class="btn warn" type="submit">修改密码</button>
          </form>
        </div>
        <div class="card">
          <div class="section-title">康复日志数据</div>
          <div class="grid cols-2">
            <div><div class="label" style="color:var(--text-2);font-size:13px">当前连续</div><div class="value num" style="font-size:26px;font-weight:700">${user.current_streak} 天</div></div>
            <div><div class="label" style="color:var(--text-2);font-size:13px">历史最长</div><div class="value num" style="font-size:26px;font-weight:700">${user.longest_streak} 天</div></div>
          </div>
        </div>
        <div id="invite-box" class="mt-16"></div>
        <div id="push-box" class="mt-16"></div>
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
  el.querySelector("#profile-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/auth/me", {
        method: "PUT",
        body: {
          nickname: fd.get("nickname"), phone: fd.get("phone"),
          gender: +fd.get("gender"), reminder_time: fd.get("reminder_time") + ":00",
          anonymous_rank: fd.get("anonymous") ? 1 : 0,
        },
      });
      toast("个人信息已更新", "success");
    } catch (err) { toast(err.message, "error"); }
  };
  el.querySelector("#pwd-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/auth/password", { method: "PUT", body: { old_password: fd.get("old"), new_password: fd.get("new") } });
      toast("密码修改成功", "success");
      e.target.reset();
    } catch (err) { toast(err.message, "error"); }
  };
  renderInvite(el.querySelector("#invite-box")).catch((e) => {});
  renderPushSettings(el.querySelector("#push-box")).catch((e) => {});
}

async function renderPushSettings(el) {
  const s = await api("/api/features/push/settings");
  el.innerHTML = `
    <div class="card">
      <div class="section-title">📬 康复日志提醒邮件 ${s.smtp_configured ? '' : '<span class="tag gray" style="font-size:11px">SMTP未配置</span>'}</div>
      <div class="field"><label>接收邮箱</label><input id="ps-email" value="${escapeHtml(s.email || '')}" placeholder="your@email.com"></div>
      <div class="field"><label><input type="checkbox" id="ps-email-push" ${s.email_push ? 'checked' : ''} style="width:auto"> 开启每日康复日志邮件提醒</label></div>
      <div class="flex" style="gap:10px">
        <button class="btn" id="ps-save">保存设置</button>
        <button class="btn ghost" id="ps-test">发送测试邮件</button>
      </div>
    </div>`;
  el.querySelector("#ps-save").onclick = async () => {
    await api("/api/features/push/settings", { method: "PUT", body: { email: el.querySelector("#ps-email").value, email_push: el.querySelector("#ps-email-push").checked ? 1 : 0 } });
    toast("推送设置已保存", "success");
  };
  el.querySelector("#ps-test").onclick = async () => {
    try { await api("/api/features/push/test-email", { method: "POST" }); toast("测试邮件已发送，请查收", "success"); }
    catch (e) { toast(e.message, "error"); }
  };
}

/* ================= 预约与疗程 ================= */
const APPT_STATUS_LABEL = { booked: ["待就诊", "warn"], completed: ["已完成", "green"], cancelled: ["已取消", "gray"] };

async function viewAppointments(el) {
  killCharts();
  const [cards, appts, schedules, followups] = await Promise.all([
    api("/api/rehab/treatment-cards"),
    api("/api/rehab/appointments"),
    api("/api/rehab/schedules"),
    api("/api/rehab/followups"),
  ]);
  const upcoming = appts.filter((a) => a.status === "booked");
  const history = appts.filter((a) => a.status !== "booked");
  const pendingFollowups = followups.filter((f) => f.status === "pending");
  const remaining = cards.reduce((s, c) => s + (c.status === "active" ? c.remaining : 0), 0);
  const byDate = {};
  schedules.forEach((s) => { (byDate[s.work_date] = byDate[s.work_date] || []).push(s); });

  el.innerHTML = `
    ${pendingFollowups.length ? `
    <div class="card mb-16" style="border-left:4px solid var(--warning);background:#FFFBEB">
      <div style="font-weight:700;margin-bottom:4px">📨 治疗师随访提醒</div>
      ${pendingFollowups.map((f) => `<div style="font-size:13px;color:var(--text-2)">· ${escapeHtml(f.content)} <span style="font-size:11px">（${escapeHtml(f.due_date || "")}）</span></div>`).join("")}
    </div>` : ""}
    <div class="grid cols-3 mb-16" style="gap:12px">
      <div class="card"><div style="color:var(--text-2);font-size:13px">待就诊预约</div>
        <div style="font-size:28px;font-weight:800;color:var(--primary)">${upcoming.length}<span style="font-size:13px;color:var(--text-2)"> 个</span></div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">可用疗程</div>
        <div style="font-size:28px;font-weight:800;color:${remaining > 0 ? "var(--success)" : "var(--danger)"}">${remaining}<span style="font-size:13px;color:var(--text-2)"> 次</span></div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">可预约号源</div>
        <div style="font-size:28px;font-weight:800;color:var(--accent)">${schedules.reduce((s, x) => s + x.remaining, 0)}<span style="font-size:13px;color:var(--text-2)"> 个</span></div></div>
    </div>

    <div class="grid cols-2" style="grid-template-columns: 1.2fr 1fr;align-items:start">
      <div class="card">
        <div class="section-title">📅 可预约排班 <span class="tag">未来 7 天</span></div>
        ${Object.keys(byDate).length ? Object.keys(byDate).sort().slice(0, 7).map((d) => `
          <div style="margin-bottom:12px">
            <div style="font-weight:700;color:var(--primary);font-size:13px;margin-bottom:6px">${d} · ${["周日","周一","周二","周三","周四","周五","周六"][new Date(`${d}T00:00:00`).getDay()]}</div>
            ${byDate[d].map((s) => `
              <div class="flex between" style="padding:9px 12px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;align-items:center">
                <div>
                  <b style="font-size:13px">${escapeHtml(s.coach_name)}</b>
                  <div style="font-size:12px;color:var(--text-2)">${escapeHtml(s.start_time)}-${escapeHtml(s.end_time)} · ${escapeHtml(s.location || "")}</div>
                </div>
                <div class="flex" style="gap:8px;align-items:center">
                  <span class="tag ${s.remaining ? "green" : "red"}">余 ${s.remaining}</span>
                  <button class="btn sm" data-book="${s.id}" ${s.remaining ? "" : "disabled"}>预约</button>
                </div>
              </div>`).join("")}
          </div>`).join("") : '<div class="empty">近 7 天暂无排班，请联系治疗师</div>'}
      </div>
      <div>
        <div class="card mb-16">
          <div class="section-title">🎫 我的疗程卡</div>
          ${cards.length ? cards.map((c) => `
            <div style="padding:10px 0;border-bottom:1px solid var(--border)">
              <div class="flex between"><b style="font-size:13px">${escapeHtml(c.title)}</b>
                <span class="tag ${c.status === "active" ? "green" : "gray"}">${c.status === "active" ? "使用中" : c.status === "finished" ? "已完成" : "已过期"}</span></div>
              <div style="font-size:12px;color:var(--text-2);margin:4px 0">${escapeHtml(c.valid_from || "-")} ~ ${escapeHtml(c.valid_to || "-")} · 剩余 ${c.remaining} / ${c.total_sessions} 次</div>
              <div style="height:7px;background:var(--border);border-radius:99px;overflow:hidden">
                <div style="height:100%;width:${Math.min(100, c.used_sessions / c.total_sessions * 100)}%;background:var(--primary)"></div></div>
            </div>`).join("") : '<div class="empty">暂无疗程卡</div>'}
        </div>
        <div class="card">
          <div class="section-title">🗓️ 我的预约</div>
          ${upcoming.length ? upcoming.map((a) => `
            <div class="flex between" style="padding:9px 0;border-bottom:1px solid var(--border);align-items:center">
              <div><b style="font-size:13px">${escapeHtml(a.appt_date)} ${escapeHtml(a.start_time)}</b>
                <div style="font-size:12px;color:var(--text-2)">${escapeHtml(a.appt_type)} · ${escapeHtml(a.coach_name)}</div></div>
              <button class="btn ghost sm" data-cancel="${a.id}">取消</button>
            </div>`).join("") : '<div class="empty">暂无待就诊预约</div>'}
          ${history.length ? `
            <div style="margin-top:10px;font-size:12px;color:var(--text-2)">历史预约</div>
            ${history.slice(0, 6).map((a) => `<div class="flex between" style="font-size:12px;padding:4px 0">
              <span>${escapeHtml(a.appt_date)} ${escapeHtml(a.start_time)} · ${escapeHtml(a.appt_type)}</span>
              <span class="tag ${(APPT_STATUS_LABEL[a.status] || [a.status, "gray"])[1]}">${(APPT_STATUS_LABEL[a.status] || [a.status])[0]}</span>
            </div>`).join("")}` : ""}
        </div>
      </div>
    </div>`;

  el.querySelectorAll("[data-book]").forEach((b) => {
    b.onclick = () => {
      const s = schedules.find((x) => x.id === +b.dataset.book);
      openModal({
        title: `预约 · ${s.coach_name} ${s.work_date} ${s.start_time}`,
        content: `
          <div class="field"><label>预约类型</label><select id="ap-type">
            <option>门诊评估</option><option>手法治疗</option><option>训练指导</option><option>复评</option>
          </select></div>
          <div class="field"><label>备注（选填）</label><input id="ap-note" maxlength="200" placeholder="如：肩关节活动度复评"></div>
          <div style="font-size:12px;color:var(--text-2)">时间：${s.start_time}-${s.end_time} · 地点：${escapeHtml(s.location || "康衡康复中心")}</div>`,
        footer: `<button class="btn ghost" id="ap-cancel">取消</button><button class="btn" id="ap-save">确认预约</button>`,
        onMount(modal) {
          modal.querySelector("#ap-cancel").onclick = closeModal;
          modal.querySelector("#ap-save").onclick = async () => {
            try {
              await api("/api/rehab/appointments", {
                method: "POST",
                body: { schedule_id: s.id, appt_type: modal.querySelector("#ap-type").value, note: modal.querySelector("#ap-note").value.trim() },
              });
              closeModal(); toast("预约成功，请按时到诊", "success"); viewAppointments(el);
            } catch (err) { toast(err.message, "error"); }
          };
        },
      });
    };
  });
  el.querySelectorAll("[data-cancel]").forEach((b) => {
    b.onclick = () => confirmBox("确定取消该预约？", async () => {
      try {
        await api(`/api/rehab/appointments/${b.dataset.cancel}/cancel`, { method: "POST" });
        closeModal(); toast("预约已取消", "success"); viewAppointments(el);
      } catch (err) { toast(err.message, "error"); }
    });
  });
}

export function initStudent() {
  registerViews("student", {
    checkin: viewCheckin,
    cases: viewRehabCases,
    assess: viewAssessments,
    tcm: viewTcmConstitution,
    body: viewBody,
    plans: viewPlans,
    appointments: viewAppointments,
    exercises: viewExercises,
    community: viewCommunity,
    resources: viewResources,
    achievements: viewAchievements,
    content: viewMemberContent,
    member: viewMember,
    messages: renderChat,
    profile: viewProfile,
  });
}

/* ================= 会员中心 ================= */
async function viewMember(el) {
  killCharts();
  const data = await api("/api/member/status");
  const me2 = me();

  el.innerHTML = `
    <div class="card mb-16" style="background:linear-gradient(135deg, rgba(46,139,132,0.15), rgba(99,184,174,0.15));border-color:rgba(46,139,132,0.4)">
      <div class="flex between wrap">
        <div>
          <div style="font-size:22px;font-weight:700;color:${me2.is_member ? 'var(--warning)' : 'var(--text)'}">
            ${me2.is_member ? '⭐ 康衡会员' : '解锁会员，获得完整康复指导'}
          </div>
          <div style="color:var(--text-2);margin-top:6px">
            ${me2.is_member
              ? `会员有效期至 ${me2.member_until} · 老用户迁移福利`
              : '当前为免费版本 · 升级会员解锁全部康复动作库、AI点评、无限补签等高级功能'}
          </div>
        </div>
        ${me2.is_member ? '<span class="tag warn" style="font-size:13px;padding:6px 18px">⭐ 会员中</span>' : ''}
      </div>
    </div>

    <div class="grid cols-3 mb-16" style="gap:14px">
      ${data.plans.map((p) => `
        <div class="card" style="${p.hot ? 'border-color:var(--warning);box-shadow:0 0 20px rgba(46,139,132,0.2)' : ''}">
          ${p.hot ? '<span class="tag warn" style="position:absolute;top:-10px;right:14px">🔥 热门</span>' : ''}
          <div style="font-size:15px;font-weight:600;margin-bottom:8px">${p.title}</div>
          <div style="font-size:28px;font-weight:800;color:var(--warning)">¥${p.price}<span style="font-size:13px;color:var(--text-2);font-weight:400"> / ${p.unit}</span></div>
          <div style="color:var(--text-2);font-size:12px;margin-top:8px;line-height:1.6">${p.desc}</div>
          <button class="btn warn" style="width:100%;margin-top:14px" data-buy="${p.key}" data-amount="${p.price}">立即开通</button>
        </div>`).join("")}
    </div>

    <div class="card mb-16">
      <div class="section-title">🎁 会员专属权益</div>
      <div class="grid cols-2" style="gap:14px;margin-top:8px">
        ${[
          ['💪', '全部康复动作库（50+）', '免费版限10个基础动作'],
          ['🎯', '康复治疗师1v1定制计划', '认证康复治疗师根据你的康复指标定制训练方案'],
          ['⏰', '无限补签 + 数据导出', '告别漏康复日志焦虑'],
          ['🤖', 'AI动作姿势点评', '上传康复日志照片，AI给出纠正建议'],
          ['🏅', '专属里程碑徽章', '会员限定徽章墙'],
          ['🔗', '全部B站教学视频', '每个动作配详细教学'],
        ].map(([ic, t, d]) => `
          <div style="display:flex;gap:10px;padding:10px;background:rgba(46,139,132,0.05);border-radius:8px">
            <div style="font-size:22px">${ic}</div>
            <div><b style="font-size:13px">${t}</b><div style="color:var(--text-2);font-size:12px;margin-top:2px">${d}</div></div>
          </div>`).join("")}
      </div>
    </div>

    ${data.paid_coaches && data.paid_coaches.length ? `
    <div class="card mb-16">
      <div class="section-title">🎯 认证康复治疗师 · 付费定制计划（¥49/次起）</div>
      <div class="grid cols-2" style="gap:12px;margin-top:6px">
        ${data.paid_coaches.map((c) => `
          <div style="display:flex;gap:12px;padding:12px;background:rgba(46,139,132,0.05);border:1px solid rgba(46,139,132,0.2);border-radius:10px">
            ${avatarHtml(c.nickname, c.avatar, "lg")}
            <div style="flex:1;min-width:0">
              <div class="flex between wrap">
                <b>${escapeHtml(c.nickname)}</b>
                <span class="tag warn">¥${c.paid_plan_price}/次</span>
              </div>
              <div style="color:var(--text-2);font-size:12px;margin:4px 0">${escapeHtml(c.specialty || "全能康复治疗师")} · 已布置 ${c.plan_count} 个计划</div>
              <div style="color:var(--text-2);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(c.bio || "")}</div>
              <button class="btn purple sm" style="margin-top:6px" data-coach="${c.user_id}" data-price="${c.paid_plan_price}">购买定制计划</button>
            </div>
          </div>`).join("")}
      </div>
    </div>` : ''}

    ${data.payments && data.payments.length ? `
    <div class="card">
      <div class="section-title">💰 我的消费记录</div>
      <table><thead><tr><th>时间</th><th>类型</th><th>金额</th><th>状态</th></tr></thead>
      <tbody>${data.payments.map((p) => `<tr><td>${fmtTime(p.created_at)}</td><td>${{monthly:'月度会员',yearly:'年度会员',paid_plan:'康复治疗师定制',bootcamp:'康复营'}[p.type] || p.type}</td><td class="num">¥${p.amount}</td><td><span class="tag green">已支付</span></td></tr>`).join("")}</tbody></table>
    </div>` : ''}

    <div id="coupon-box" class="mt-16"></div>
  `;

  el.querySelectorAll("[data-buy]").forEach((b) => {
    b.onclick = async () => {
      const plan = b.dataset.buy;
      const months = plan === "monthly" ? 1 : undefined;
      openModal({
        title: `确认开通 · ${b.previousElementSibling?.textContent?.trim() || "会员"}`,
        content: `
          <div style="padding:12px;background:rgba(46,139,132,0.08);border-radius:8px;margin-bottom:12px">
            订单类型：${{monthly:'月度会员',yearly:'年度会员',paid_plan:'康复治疗师定制'}[plan]}<br>
            订单金额：<b style="color:var(--warning)">¥${b.dataset.amount}</b>
          </div>
          <div style="color:var(--text-2);font-size:12px">
            当前为 Mock 支付模式（演示用），点击"确认支付"即完成订单。<br>
            真实上线前接微信/支付宝。
          </div>`,
        footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">取消</button>
                 <button class="btn warn" id="do-pay">确认支付 ¥${b.dataset.amount}</button>`,
        onMount(modal) {
          modal.querySelector("#do-pay").onclick = async () => {
            try {
              const body = { plan };
              if (months) body.months = months;
              const res = await api("/api/member/subscribe", { method: "POST", body });
              closeModal();
              toast("🎉 支付成功！已开通会员", "success");
              viewMember(el);
              // 刷新sidebar会员徽章
              const cu = await api("/api/auth/me");
              setMe(cu);
              document.querySelector(".sidebar .user-box .info .name").innerHTML =
                `${escapeHtml(cu.nickname)} <span class="tag purple" style="margin-left:4px;font-size:10px">⭐ 会员</span>`;
              document.querySelector(".sidebar .user-box .info .role").textContent =
                "患者 · 到期" + (cu.member_until || "-");
            } catch (err) { toast(err.message, "error"); }
          };
        },
      });
    };
  });

  el.querySelectorAll("[data-coach]").forEach((b) => {
    b.onclick = async () => {
      openModal({
        title: `购买 ${b.closest("div.card").querySelector("b").textContent} 的定制计划`,
        content: `
          <div style="padding:12px;background:rgba(46,139,132,0.08);border-radius:8px;margin-bottom:12px">
            康复治疗师：${b.closest("div.card").querySelector("b").textContent}<br>
            定价：<b style="color:var(--warning)">¥${b.dataset.price}</b><br>
            服务：康复治疗师将在3天内为你制定30天专属康复方案
          </div>
          <div style="color:var(--text-2);font-size:12px">支付后康复治疗师将收到站内消息通知，立即为你制定计划。</div>`,
        footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">取消</button>
                 <button class="btn warn" id="do-coach-pay">立即支付 ¥${b.dataset.price}</button>`,
        onMount(modal) {
          modal.querySelector("#do-coach-pay").onclick = async () => {
            try {
              await api("/api/member/subscribe", {
                method: "POST",
                body: { plan: "paid_plan", coach_id: +b.dataset.coach },
              });
              closeModal();
              toast("🎉 已购买！康复治疗师将立即收到通知", "success");
              viewMember(el);
            } catch (err) { toast(err.message, "error"); }
          };
        },
      });
    };
  });
  renderCoupons(el.querySelector("#coupon-box")).catch((e) => {});
}

/* ================= 视图注册结束 ================= */
