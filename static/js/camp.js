import { api, uploadFile } from "./api.js";
import { toast, openModal, closeModal, confirmBox, escapeHtml, fmtNum, fmtTime, registerViews, me, avatarHtml, localDate, getWS } from "./app.js";

const charts = [];
function killCharts() { charts.forEach((c) => c.destroy && c.destroy()); charts.length = 0; }

const STATUS_TAG = { draft: "gray", recruiting: "warn", ongoing: "green", ended: "purple" };

function campCard(c, isCoach) {
  const statusTag = `<span class="tag ${STATUS_TAG[c.status] || ""}">${c.status_label}</span>`;
  const meta = isCoach
    ? `<div class="m">👥 ${c.member_count}/${c.capacity} 人 · 今日康复日志 ${c.checked_today}/${c.member_count}</div>`
    : `<div class="m">我的排名 ${c.my_rank ? "#" + c.my_rank : "—"} · ${c.checked_today ? "今日已康复日志 ✅" : "今日未康复日志"}</div>`;
  return `
    <div class="stat-card clickable camp-card" data-id="${c.id}">
      <div class="label">${statusTag} ${escapeHtml(c.title)}</div>
      <div class="value" style="font-size:17px">${c.start_date} ~ ${c.end_date}</div>
      ${meta}
      <div class="sub">${c.status === "ongoing" ? `剩余 ${c.days_left} 天 / 共 ${c.days_total} 天` : `共 ${c.days_total} 天`}</div>
      ${isCoach ? `<div class="drill-hint">邀请码 ${c.invite_code} · 点击管理 →</div>` : `<div class="drill-hint">点击查看详情 →</div>`}
    </div>`;
}

function leaderboardHtml(rows, metricLabel) {
  if (!rows.length) return `<div class="empty">暂无排行数据</div>`;
  return `<table><thead><tr><th>排名</th><th>成员</th><th>${metricLabel}</th><th>连续天数</th></tr></thead>
    <tbody>${rows.map((r) => `<tr>
      <td class="num">${r.rank <= 3 ? ["🥇", "🥈", "🥉"][r.rank - 1] : r.rank}</td>
      <td><div class="flex">${r.anonymous ? '<div class="avatar sm">匿</div>' : avatarHtml(r.nickname, r.avatar, "sm")}
        <b>${escapeHtml(r.anonymous ? "匿名患者" : r.nickname)}</b></div></td>
      <td class="num">${fmtNum(r.score)}</td>
      <td class="num">${r.current_streak} 天</td>
    </tr>`).join("")}</tbody></table>`;
}

/* ================= 康复治疗师端：康复营管理 ================= */
async function viewCoachCamps(el) {
  killCharts();
  const camps = await api("/api/camps");
  el.innerHTML = `
    <div class="card mb-16">
      <div class="flex" style="justify-content:space-between;align-items:center">
        <div>
          <div class="section-title" style="margin-bottom:4px">我的康复营</div>
          <div style="color:var(--text-2);font-size:13px">以营为单位批量带练：邀请码入营 → 批量生成计划 → 营内排行与群聊 → 结营报告</div>
        </div>
        <button class="btn" id="btn-new-camp">＋ 创建康复营</button>
      </div>
    </div>
    ${camps.length ? `<div class="grid cols-3">${camps.map((c) => campCard(c, true)).join("")}</div>`
      : `<div class="card"><div class="empty"><span class="ico">🏕️</span>还没有康复营，点击右上角创建第一个营期<br>
          <small>建议先在「计划制定」里准备一份模板计划，开营后可一键为全员生成</small></div></div>`}`;

  el.querySelector("#btn-new-camp").onclick = () => openCampForm();
  el.querySelectorAll(".camp-card").forEach((card) => {
    card.onclick = () => openCoachCampDetail(+card.dataset.id);
  });
}

function openCampForm(camp = null) {
  const isEdit = !!camp;
  openModal({
    title: isEdit ? "编辑康复营" : "创建康复营",
    content: `
      <div class="field"><label>营期名称</label><input id="cf-title" maxlength="100" placeholder="如：肩颈康复营第1期" value="${escapeHtml(camp?.title || "")}"></div>
      <div class="field"><label>营期介绍</label><textarea id="cf-desc" maxlength="500" rows="3" placeholder="营期目标、适合人群、交付内容…">${escapeHtml(camp?.description || "")}</textarea></div>
      <div class="grid cols-3">
        <div class="field"><label>开始日期</label><input type="date" id="cf-start" value="${camp?.start_date || localDate()}"></div>
        <div class="field"><label>结束日期</label><input type="date" id="cf-end" value="${camp?.end_date || localDate(new Date(Date.now() + 20 * 864e5))}"></div>
        <div class="field"><label>人数上限</label><input type="number" id="cf-capacity" min="1" max="500" value="${camp?.capacity || 30}"></div>
      </div>`,
    footer: `<button class="btn ghost" id="cf-cancel">取消</button>
             <button class="btn" id="cf-save">${isEdit ? "保存修改" : "创建（状态：筹备中）"}</button>`,
    onMount(modal) {
      modal.querySelector("#cf-cancel").onclick = closeModal;
      modal.querySelector("#cf-save").onclick = async () => {
        const body = {
          title: modal.querySelector("#cf-title").value.trim(),
          description: modal.querySelector("#cf-desc").value.trim(),
          start_date: modal.querySelector("#cf-start").value,
          end_date: modal.querySelector("#cf-end").value,
          capacity: +modal.querySelector("#cf-capacity").value || 30,
        };
        if (!body.title || !body.start_date || !body.end_date) {
          toast("请填写营期名称与起止日期", "error"); return;
        }
        try {
          if (isEdit) await api(`/api/camps/${camp.id}`, { method: "PUT", body });
          else await api("/api/camps", { method: "POST", body });
          toast(isEdit ? "营期已更新" : "康复营已创建，可开始添加患者", "success");
          closeModal();
          routeRefresh();
        } catch (err) { toast(err.message, "error"); }
      };
    },
  });
}

async function openCoachCampDetail(campId) {
  killCharts();
  const [camp, members, board] = await Promise.all([
    api(`/api/camps/${campId}`),
    api(`/api/camps/${campId}/members`),
    api(`/api/camps/${campId}/leaderboard`),
  ]);

  const actions = [];
  if (camp.status === "draft") {
    actions.push(`<button class="btn warn" data-transition="start">📣 发布招生</button>`);
    actions.push(`<button class="btn ghost" id="camp-edit">✏️ 编辑信息</button>`);
  }
  if (camp.status === "recruiting") {
    actions.push(`<button class="btn success" data-transition="open">🚀 开营</button>`);
    actions.push(`<button class="btn ghost" id="camp-edit">✏️ 编辑信息</button>`);
  }
  if (camp.status === "ongoing") {
    const unchecked = members.filter((m) => !m.checked_today).length;
    actions.push(`<button class="btn warn" id="camp-urge">📢 催康复日志（${unchecked} 人未康复日志）</button>`);
    actions.push(`<button class="btn danger" data-transition="finish">🏁 结营并生成报告</button>`);
  }
  actions.push(`<button class="btn ghost" id="camp-chat">💬 营内群聊</button>`);
  if (camp.status === "ended") actions.push(`<button class="btn purple" id="camp-report">📊 结营报告</button>`);
  if (camp.status === "ongoing") actions.push(`<button class="btn ghost" id="camp-genplans">📋 批量生成计划</button>`);
  actions.push(`<button class="btn ghost" id="camp-addmember">＋ 添加患者</button>`);

  openModal({
    title: `${escapeHtml(camp.title)} <span class="tag ${STATUS_TAG[camp.status]}">${camp.status_label}</span>`,
    wide: true,
    content: `
      <div class="card mb-16" style="box-shadow:none">
        <div class="flex" style="justify-content:space-between;flex-wrap:wrap;gap:10px">
          <div style="color:var(--text-2);font-size:13px">
            ${camp.start_date} ~ ${camp.end_date}（共 ${camp.days_total} 天）· 👥 ${camp.member_count}/${camp.capacity} 人
            ${camp.status === "ongoing" ? ` · 剩余 ${camp.days_left} 天` : ""}
            ${camp.description ? `<div style="margin-top:6px">${escapeHtml(camp.description)}</div>` : ""}
          </div>
          <div class="flex" style="flex-wrap:wrap;gap:8px">${actions.join("")}</div>
        </div>
        <div class="flex mt-16" style="align-items:center;gap:8px">
          <span style="color:var(--text-2);font-size:13px">入营邀请码</span>
          <code id="camp-invite" style="font-family:var(--mono);font-size:16px;letter-spacing:2px;
            background:var(--card-2);padding:4px 10px;border-radius:6px;cursor:pointer"
            title="点击复制">${camp.invite_code}</code>
          <small style="color:var(--text-2)">患者在「康复营」页输入此码加入</small>
        </div>
      </div>
      <div class="grid cols-2">
        <div class="card" style="box-shadow:none">
          <div class="section-title">营员（${members.length}）</div>
          ${members.length ? `<div style="max-height:360px;overflow-y:auto"><table>
            <thead><tr><th>患者</th><th>今日</th><th>营内康复日志</th><th>营内训练量</th><th>连续</th><th></th></tr></thead>
            <tbody>${members.map((m) => `<tr>
              <td><div class="flex">${avatarHtml(m.nickname, m.avatar, "sm")}<b>${escapeHtml(m.nickname)}</b></div></td>
              <td>${camp.status === "ongoing" ? (m.checked_today ? '<span class="tag green">已康复日志</span>' : '<span class="tag red">未康复日志</span>') : "-"}</td>
              <td class="num">${m.camp_days} 天</td>
              <td class="num">${fmtNum(m.camp_volume)} kg</td>
              <td class="num">${m.current_streak}</td>
              <td><button class="btn danger sm" data-remove="${m.id}" data-name="${escapeHtml(m.nickname)}">移除</button></td>
            </tr>`).join("")}</tbody></table></div>`
          : `<div class="empty">暂无营员，可通过邀请码或「添加患者」入营</div>`}
        </div>
        <div class="card" style="box-shadow:none">
          <div class="section-title">营内排行榜（康复日志天数）</div>
          ${leaderboardHtml(board, "康复日志天数")}
        </div>
      </div>`,
    onMount(modal) {
      modal.querySelector("#camp-invite").onclick = () => {
        navigator.clipboard?.writeText(camp.invite_code).then(
          () => toast("邀请码已复制", "success"), () => toast(camp.invite_code, "info"));
      };
      modal.querySelector("#camp-edit")?.addEventListener("click", () => openCampForm(camp));
      modal.querySelector("#camp-chat").onclick = () => openCampChat(camp);
      modal.querySelector("#camp-report")?.addEventListener("click", () => openCampReport(camp.id));
      modal.querySelector("#camp-genplans").onclick = () => openGenPlansModal(camp);
      modal.querySelector("#camp-addmember").onclick = () => openAddMemberModal(camp, members);
      modal.querySelector("#camp-urge")?.addEventListener("click", async (e) => {
        try {
          const res = await api(`/api/camps/${camp.id}/urge`, { method: "POST", body: {} });
          toast(`已向 ${res.sent} 名未康复日志患者发送催康复日志消息`, "success");
          e.target.outerHTML = `<button class="btn success" disabled>✔ 已催促</button>`;
        } catch (err) { toast(err.message, "error"); }
      });
      modal.querySelectorAll("[data-transition]").forEach((b) => {
        b.onclick = () => {
          const act = b.dataset.transition;
          const labels = { start: "发布招生（患者可凭邀请码入营）", open: "正式开营（开启群聊与排行）", finish: "结营（自动生成结营报告，不可逆）" };
          confirmBox(`确认${labels[act]}？`, async () => {
            try {
              await api(`/api/camps/${camp.id}/transition?action=${act}`, { method: "POST" });
              toast("操作成功", "success");
              closeModal();
              routeRefresh();
            } catch (err) { toast(err.message, "error"); }
          }, "确认");
        };
      });
      modal.querySelectorAll("[data-remove]").forEach((b) => {
        b.onclick = () => {
          confirmBox(`确认将 ${b.dataset.name} 移出康复营？其历史康复日志数据保留。`, async () => {
            try {
              await api(`/api/camps/${camp.id}/members/${b.dataset.remove}`, { method: "DELETE" });
              toast("已移除", "success");
              closeModal();
              openCoachCampDetail(camp.id);
            } catch (err) { toast(err.message, "error"); }
          }, "移除");
        };
      });
    },
  });
}

async function openGenPlansModal(camp) {
  const plans = await api("/api/coach/plans");
  openModal({
    title: "批量生成营期计划",
    content: `
      <p style="color:var(--text-2);font-size:13px">以一份现有计划为模板，为全体在营患者（含你自己复制的动作明细）生成营期计划，日期自动对齐营期开始日。</p>
      <div class="field"><label>模板计划</label>
        <select id="gp-template">
          ${plans.map((p) => `<option value="${p.id}">${escapeHtml(p.title)}（${p.items?.length || "?"} 个动作 · 患者 ${escapeHtml(p.student_name || "")}）</option>`).join("")}
        </select></div>
      <div class="field"><label>营期计划标题</label>
        <input id="gp-title" maxlength="100" value="${escapeHtml(camp.title)} · 康复方案"></div>`,
    footer: `<button class="btn ghost" id="gp-cancel">取消</button>
             <button class="btn" id="gp-go">生成</button>`,
    onMount(modal) {
      modal.querySelector("#gp-cancel").onclick = closeModal;
      modal.querySelector("#gp-go").onclick = async () => {
        try {
          const res = await api(`/api/camps/${camp.id}/generate-plans`, {
            method: "POST",
            body: { template_plan_id: +modal.querySelector("#gp-template").value,
                    title: modal.querySelector("#gp-title").value.trim() },
          });
          toast(`已为 ${res.created} 名患者生成营期计划`, "success");
          closeModal();
        } catch (err) { toast(err.message, "error"); }
      };
    },
  });
}

function openAddMemberModal(camp, members) {
  const memberIds = new Set(members.map((m) => m.id));
  openModal({
    title: "添加患者入营",
    content: `
      <div class="field"><label>搜索患者（昵称/用户名/手机号）</label>
        <input id="am-q" placeholder="输入关键词搜索"></div>
      <div id="am-list" style="max-height:320px;overflow-y:auto;margin-top:10px">
        <div class="empty" style="padding:20px">输入关键词搜索患者</div>
      </div>`,
    onMount(modal) {
      const list = modal.querySelector("#am-list");
      async function search() {
        const q = modal.querySelector("#am-q").value.trim();
        if (!q) { list.innerHTML = `<div class="empty" style="padding:20px">输入关键词搜索患者</div>`; return; }
        const students = await api(`/api/coach/all-students?q=${encodeURIComponent(q)}`);
        list.innerHTML = students.length ? students.map((s) => `
          <div class="c-item" style="display:flex;gap:10px;padding:10px;border-bottom:1px solid rgba(69,69,96,0.4);align-items:center">
            ${avatarHtml(s.nickname, s.avatar, "sm")}
            <div style="flex:1"><b>${escapeHtml(s.nickname)}</b>
              <div style="color:var(--text-2);font-size:12px">${escapeHtml(s.phone || "")}</div></div>
            ${memberIds.has(s.id) ? '<span class="tag gray">已在营中</span>'
              : `<button class="btn sm" data-add="${s.id}">加入</button>`}
          </div>`).join("") : `<div class="empty" style="padding:20px">未找到患者</div>`;
        list.querySelectorAll("[data-add]").forEach((b) => {
          b.onclick = async () => {
            try {
              await api(`/api/camps/${camp.id}/members`, { method: "POST", body: { user_id: +b.dataset.add } });
              toast("已添加入营", "success");
              closeModal();
              openCoachCampDetail(camp.id);
            } catch (err) { toast(err.message, "error"); }
          };
        });
      }
      let timer = null;
      modal.querySelector("#am-q").oninput = () => {
        clearTimeout(timer);
        timer = setTimeout(search, 300);
      };
    },
  });
}

/* ================= 患者端：我的康复营 ================= */
async function viewStudentCamps(el) {
  killCharts();
  const camps = await api("/api/camps/my");
  el.innerHTML = `
    <div class="card mb-16">
      <div class="flex" style="justify-content:space-between;align-items:center">
        <div>
          <div class="section-title" style="margin-bottom:4px">我的康复营</div>
          <div style="color:var(--text-2);font-size:13px">跟着康复治疗师和营友一起练：营期计划 · 营内排行 · 营内群聊 · 结营报告</div>
        </div>
        <button class="btn" id="btn-join-camp">🔑 邀请码入营</button>
      </div>
    </div>
    ${camps.length ? `<div class="grid cols-3">${camps.map((c) => campCard(c, false)).join("")}</div>`
      : `<div class="card"><div class="empty"><span class="ico">🏕️</span>还没有参加康复营<br>
          <small>向你的康复治疗师索取邀请码，点击右上角「邀请码入营」加入</small></div></div>`}`;

  el.querySelector("#btn-join-camp").onclick = () => {
    openModal({
      title: "邀请码入营",
      content: `<div class="field"><label>康复营邀请码</label>
        <input id="jc-code" maxlength="8" placeholder="8 位邀请码，如 7KX2M9QA" style="text-transform:uppercase;font-family:var(--mono);letter-spacing:2px"></div>`,
      footer: `<button class="btn ghost" id="jc-cancel">取消</button>
               <button class="btn" id="jc-go">加入康复营</button>`,
      onMount(modal) {
        modal.querySelector("#jc-cancel").onclick = closeModal;
        modal.querySelector("#jc-go").onclick = async () => {
          const code = modal.querySelector("#jc-code").value.trim();
          if (!code) { toast("请输入邀请码", "error"); return; }
          try {
            const camp = await api("/api/camps/join", { method: "POST", body: { invite_code: code } });
            toast(`已加入【${camp.title}】`, "success");
            closeModal();
            routeRefresh();
          } catch (err) { toast(err.message, "error"); }
        };
      },
    });
  };
  el.querySelectorAll(".camp-card").forEach((card) => {
    card.onclick = () => {
      const camp = camps.find((c) => c.id === +card.dataset.id);
      openStudentCampDetail(+card.dataset.id, camp);
    };
  });
}

async function openStudentCampDetail(campId, cached = null) {
  killCharts();
  const [camp, board, msgs] = await Promise.all([
    api(`/api/camps/${campId}`),
    api(`/api/camps/${campId}/leaderboard`),
    api(`/api/camps/${campId}/messages?limit=20`),
  ]);
  if (cached) Object.assign(camp, { checked_today: cached.checked_today, my_rank: cached.my_rank });
  let report = null;
  if (camp.status === "ended") {
    try { report = await api(`/api/camps/${campId}/report`); } catch {}
  }

  openModal({
    title: `${escapeHtml(camp.title)} <span class="tag ${STATUS_TAG[camp.status]}">${camp.status_label}</span>`,
    wide: true,
    content: `
      <div class="card mb-16" style="box-shadow:none">
        <div class="flex" style="justify-content:space-between;flex-wrap:wrap;gap:10px">
          <div>
            <div class="flex">${avatarHtml(camp.coach_name, camp.coach_avatar, "sm")}
              <b>康复治疗师：${escapeHtml(camp.coach_name)}</b></div>
            <div style="color:var(--text-2);font-size:13px;margin-top:6px">
              ${camp.start_date} ~ ${camp.end_date}（共 ${camp.days_total} 天）· 👥 ${camp.member_count} 人
              ${camp.status === "ongoing" ? ` · 剩余 ${camp.days_left} 天` : ""}</div>
            ${camp.description ? `<div style="color:var(--text-2);font-size:13px;margin-top:4px">${escapeHtml(camp.description)}</div>` : ""}
          </div>
          <div class="flex" style="gap:8px">
            ${camp.status === "ongoing" ? `<button class="btn" id="camp-chat">💬 营内群聊</button>` : ""}
            ${camp.status !== "ended" ? `<a class="btn ghost" href="#/checkin" id="camp-gocheckin">${camp.checked_today ? "✅ 今日已康复日志" : "去康复日志"}</a>` : ""}
            ${report ? `<button class="btn purple" id="camp-report">📊 结营报告</button>` : ""}
          </div>
        </div>
      </div>
      ${report ? `
      <div class="card mb-16" style="box-shadow:none">
        <div class="section-title">结营战报</div>
        <div class="stat-cards">
          <div class="stat-card"><div class="label">营期康复日志率</div><div class="value">${report.checkin_rate}%</div><div class="sub">共 ${report.total_checkins} 次康复日志</div></div>
          <div class="stat-card purple"><div class="label">人均训练量</div><div class="value">${fmtNum(report.avg_volume)}<span style="font-size:14px"> kg</span></div><div class="sub">${report.member_count} 人 · ${report.total_days} 天</div></div>
          <div class="stat-card ${report.weight_change_avg < 0 ? "green" : "warn"}"><div class="label">平均体重变化</div><div class="value">${report.weight_change_avg > 0 ? "+" : ""}${report.weight_change_avg}<span style="font-size:14px"> kg</span></div><div class="sub">有记录患者均值</div></div>
          <div class="stat-card"><div class="label">解锁徽章</div><div class="value">${report.badges_unlocked}</div><div class="sub">全营累计</div></div>
        </div>
        ${report.top3?.length ? `<div class="section-title" style="margin-top:12px">营内 Top3</div>
          <div class="flex" style="gap:16px;flex-wrap:wrap">${report.top3.map((t) => `
            <div class="flex" style="gap:8px">${["🥇", "🥈", "🥉"][t.rank - 1]}
              <b>${escapeHtml(t.nickname)}</b><span style="color:var(--text-2)">${t.score} 天</span></div>`).join("")}</div>` : ""}
      </div>` : ""}
      <div class="grid cols-2">
        <div class="card" style="box-shadow:none">
          <div class="section-title">营内排行榜（康复日志天数）</div>
          ${leaderboardHtml(board, "康复日志天数")}
        </div>
        <div class="card" style="box-shadow:none">
          <div class="section-title">营内动态（最近 ${msgs.length} 条）</div>
          <div style="max-height:360px;overflow-y:auto">
            ${msgs.length ? msgs.map((m) => `
              <div class="flex mb-16" style="gap:10px">
                ${m.msg_type === "system" ? '<div class="avatar sm">📢</div>'
                  : avatarHtml(m.sender_nickname || "?", m.sender_avatar, "sm")}
                <div><b style="font-size:13px">${escapeHtml(m.msg_type === "system" ? "系统" : m.sender_nickname || "患者")}</b>
                  <div style="font-size:13px">${escapeHtml(m.content)}</div>
                  <div style="color:var(--text-2);font-size:11px">${fmtTime(m.created_at)}</div></div>
              </div>`).join("") : `<div class="empty">暂无动态</div>`}
          </div>
        </div>
      </div>`,
    onMount(modal) {
      modal.querySelector("#camp-chat")?.addEventListener("click", () => openCampChat(camp));
      modal.querySelector("#camp-report")?.addEventListener("click", () => openCampReport(camp.id));
      modal.querySelector("#camp-gocheckin")?.addEventListener("click", () => closeModal());
    },
  });
}

async function openCampReport(campId) {
  const r = await api(`/api/camps/${campId}/report`);
  openModal({
    title: `结营报告 · ${escapeHtml(r.title)}`,
    wide: true,
    content: `
      <div class="stat-cards">
        <div class="stat-card"><div class="label">营期康复日志率</div><div class="value">${r.checkin_rate}%</div><div class="sub">${r.total_checkins} 次康复日志 / ${r.member_count} 人 / ${r.total_days} 天</div></div>
        <div class="stat-card purple"><div class="label">人均训练量</div><div class="value">${fmtNum(r.avg_volume)}<span style="font-size:14px"> kg</span></div></div>
        <div class="stat-card ${r.weight_change_avg < 0 ? "green" : "warn"}"><div class="label">平均体重变化</div><div class="value">${r.weight_change_avg > 0 ? "+" : ""}${r.weight_change_avg}<span style="font-size:14px"> kg</span></div></div>
        <div class="stat-card"><div class="label">解锁徽章</div><div class="value">${r.badges_unlocked}</div></div>
      </div>
      <div class="card" style="box-shadow:none">
        <div class="section-title">营内 Top3</div>
        ${r.top3?.length ? r.top3.map((t) => `
          <div class="flex mb-16" style="gap:10px">${["🥇", "🥈", "🥉"][t.rank - 1]}
            <b>${escapeHtml(t.nickname)}</b>
            <span style="color:var(--text-2)">${t.score} 天 · ${fmtNum(t.score)}</span></div>`).join("")
        : `<div class="empty">暂无数据</div>`}
      </div>
      <p style="color:var(--text-2);font-size:12px">报告生成于结营时（${r.end_date}），如需最新数据请康复治疗师重新结营生成。</p>`,
  });
}

/* ================= 营内群聊 ================= */
let wsHandler = null;

function openCampChat(camp) {
  openModal({
    title: `💬 ${escapeHtml(camp.title)} · 营内群聊`,
    wide: true,
    content: `
      <div class="chat-panel" style="height:60vh;border:none">
        <div class="head">全体营员（${camp.member_count || "…"} 人）· 开营期间实时聊天</div>
        <div class="msgs" id="camp-msgs"></div>
        <div class="chat-input">
          <label class="btn ghost sm" style="cursor:pointer" title="发送图片">📎<input type="file" id="camp-file" accept="image/*" style="display:none"></label>
          <input type="text" id="camp-text" placeholder="和营友聊聊今天的训练…" maxlength="500">
          <button class="btn" id="camp-send">发送</button>
        </div>
      </div>`,
    async onMount(modal) {
      const user = me();
      const msgsBox = modal.querySelector("#camp-msgs");
      const history = await api(`/api/camps/${camp.id}/messages`);

      function renderMsgs(list, append = false) {
        const html = list.map((m) => {
          if (m.msg_type === "system") {
            return `<div style="text-align:center;color:var(--text-2);font-size:12px;padding:4px 0">—— ${escapeHtml(m.content)} ——</div>`;
          }
          const mine = Number(m.sender_id) === Number(user.id);
          const sender = m.sender_nickname || "患者";
          let body = escapeHtml(m.content);
          if (m.msg_type === "image" && m.media_path) body = `<img src="/uploads/${m.media_path}" alt="图片消息">`;
          if (m.msg_type === "video" && m.media_path) body = `📹 视频消息`;
          return `<div class="msg ${mine ? "mine" : ""}">
            ${avatarHtml(sender, m.sender_avatar)}
            <div class="bubble">${body}<div class="time">${escapeHtml(sender)} · ${fmtTime(m.created_at)}</div></div>
          </div>`;
        }).join("");
        if (append) msgsBox.insertAdjacentHTML("beforeend", html);
        else msgsBox.innerHTML = html || `<div class="empty">暂无消息，和营友打个招呼吧</div>`;
        msgsBox.scrollTop = msgsBox.scrollHeight;
      }

      renderMsgs(history);

      if (wsHandler) {
        const oldWs = getWS();
        oldWs?.removeEventListener("message", wsHandler);
        wsHandler = null;
      }
      wsHandler = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "camp_msg" && Number(data.camp_id) === Number(camp.id)) {
            renderMsgs([data.data], true);
          }
        } catch {}
      };
      getWS()?.addEventListener("message", wsHandler);

      function wsSend(payload) {
        const ws = getWS();
        if (!ws || ws.readyState !== 1) { toast("连接已断开，稍后重试", "error"); return false; }
        ws.send(JSON.stringify(payload));
        return true;
      }

      async function send() {
        const input = modal.querySelector("#camp-text");
        const text = input.value.trim();
        if (!text) return;
        input.value = "";
        wsSend({ type: "camp", camp_id: camp.id, msg_type: "text", content: text });
      }

      modal.querySelector("#camp-send").onclick = send;
      modal.querySelector("#camp-text").onkeydown = (e) => { if (e.key === "Enter") send(); };
      modal.querySelector("#camp-file").onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        try {
          const up = await uploadFile(file, "image");
          wsSend({ type: "camp", camp_id: camp.id, msg_type: "image",
                   content: "[图片]", media_path: up.path });
        } catch (err) { toast(err.message, "error"); }
      };

      const closeBtn = modal.querySelector(".m-close");
      const origClose = closeBtn.onclick;
      closeBtn.onclick = () => {
        if (wsHandler) { getWS()?.removeEventListener("message", wsHandler); wsHandler = null; }
        origClose();
      };
    },
  });
}

/* ================= 注册 ================= */
function routeRefresh() {
  const refreshEvent = new HashChangeEvent("hashchange");
  window.dispatchEvent(refreshEvent);
}

export function initCamp() {
  registerViews("coach", { camps: viewCoachCamps });
  registerViews("student", { camps: viewStudentCamps });
}
