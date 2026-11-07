import { api } from "./api.js";
import { toast, openModal, closeModal, confirmBox, escapeHtml, fmtNum, fmtDate, fmtTime, registerViews, avatarHtml } from "./app.js";
import { viewRevenue, viewWithdrawals } from "./features.js";
const charts = [];
function killCharts() { charts.forEach((c) => c.destroy && c.destroy()); charts.length = 0; }
function afterRender(fn) { requestAnimationFrame(fn); }
Chart.defaults.color = "#6B8580";
Chart.defaults.borderColor = "#D6E6E2";

/* ================= 统计看板 ================= */
async function viewDashboard(el) {
  killCharts();
  let days = 30;
  const [d, trend] = await Promise.all([api("/api/admin/stats/overview"), api("/api/admin/stats/trend?days=30")]);

  el.innerHTML = `
    <div class="stat-cards">
      <div class="stat-card clickable" id="drill-users"><div class="label">注册用户</div><div class="value">${fmtNum(d.total_users)}</div><div class="sub">患者 ${d.students} · 康复治疗师 ${d.coaches}</div><div class="drill-hint">点击查看用户明细 →</div></div>
      <div class="stat-card green clickable" id="drill-active"><div class="label">日活 / 月活</div><div class="value">${fmtNum(d.dau)} / ${fmtNum(d.mau)}</div><div class="sub">月活 = 近30天有康复日志</div><div class="drill-hint">点击查看活跃用户 →</div></div>
      <div class="stat-card purple clickable" id="drill-checkins"><div class="label">今日康复日志</div><div class="value">${fmtNum(d.checkins_today)}</div><div class="sub">康复日志率 ${d.checkin_rate}%</div><div class="drill-hint">点击查看康复日志明细 →</div></div>
      <div class="stat-card purple clickable" id="drill-msg"><div class="label">近30天消息量</div><div class="value">${fmtNum(d.messages_30d)}</div><div class="sub">含聊天 / 系统通知</div><div class="drill-hint">点击查看消息明细 →</div></div>
      <div class="stat-card ${d.pending_coach_reviews ? "warn clickable" : ""}" id="drill-pending"><div class="label">待处理</div><div class="value">${d.pending_coach_reviews}</div><div class="sub">康复治疗师认证审核 ${d.pending_coach_reviews}</div>${d.pending_coach_reviews ? '<div class="drill-hint">点击前往审核 →</div>' : ""}</div>
    </div>
    <div class="card">
      <div class="section-title">
        趋势分析
        <span class="flex">
          ${[7, 30, 90].map((n) => `<button class="btn ghost sm" data-days="${n}">${n}天</button>`).join("")}
          <button class="btn ghost sm" id="export-csv">⬇ 导出 CSV</button>
        </span>
      </div>
      <div style="height:280px"><canvas id="trend-chart"></canvas></div>
    </div>`;

  el.querySelectorAll("[data-days]").forEach((b) => {
    b.onclick = async () => {
      days = +b.dataset.days;
      const t = await api(`/api/admin/stats/trend?days=${days}`);
      drawChart(t);
    };
  });
  el.querySelector("#export-csv").onclick = () => {
    const rows = [["日期", "新增用户", "康复日志数"],
      ...trend.map((t) => [t.date, t.new_users, t.checkins])];
    const csv = "\ufeff" + rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `stats_${days}d.csv`;
    a.click();
  };

  // ---- 看板下钻 ----
  el.querySelector("#drill-users").onclick = () => (location.hash = "#/users");
  el.querySelector("#drill-pending").onclick = () => (location.hash = "#/coachreview");

  el.querySelector("#drill-active").onclick = async () => {
    try {
      const res = await api("/api/admin/stats/active-users?days=30");
      openModal({
        title: `近30天活跃用户（${res.items.length} 人）`,
        wide: true,
        content: res.items.length ? `
          <table><thead><tr><th>用户</th><th>角色</th><th>近30天康复日志天数</th><th>最近康复日志</th><th>当前连续</th></tr></thead>
          <tbody>${res.items.map((u) => `<tr>
            <td><b>${escapeHtml(u.nickname)}</b></td>
            <td><span class="tag ${{ student: "", coach: "purple", admin: "red" }[u.role]}">${{ student: "患者", coach: "康复治疗师", admin: "管理员" }[u.role] || u.role}</span></td>
            <td class="num">${u.checkin_days} 天</td>
            <td class="num">${u.last_checkin}</td>
            <td class="num">${u.current_streak} 天</td>
          </tr>`).join("")}</tbody></table>`
          : `<div class="empty"><span class="ico">📭</span>近30天暂无活跃用户</div>`,
        footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`,
      });
    } catch (err) { toast(err.message, "error"); }
  };

  el.querySelector("#drill-checkins").onclick = async () => {
    let page = 1;
    const loadPage = async () => {
      try {
        const res = await api(`/api/admin/stats/checkins?page=${page}&page_size=15`);
        openModal({
          title: `今日康复日志明细（共 ${res.total} 条）`,
          wide: true,
          content: res.items.length ? `
            <table><thead><tr><th>患者</th><th>角色</th><th>训练量kg</th><th>时长min</th><th>强度</th><th>补签</th><th>内容</th></tr></thead>
            <tbody>${res.items.map((c) => `<tr>
              <td><b>${escapeHtml(c.nickname)}</b></td>
              <td><span class="tag ${{ student: "", coach: "purple" }[c.role] || "gray"}">${{ student: "患者", coach: "康复治疗师" }[c.role] || c.role}</span></td>
              <td class="num">${fmtNum(c.train_volume)}</td>
              <td class="num">${c.duration_min}</td>
              <td class="num">${c.intensity}</td>
              <td>${c.is_makeup ? '<span class="tag warn">补</span>' : "-"}</td>
              <td style="max-width:220px;font-size:12px;color:var(--text-2)">${escapeHtml((c.content || "").slice(0, 40))}</td>
            </tr>`).join("")}</tbody></table>
            <div class="pagination">
              <span>第 ${page} 页</span>
              <button class="btn ghost sm" id="ck-prev" ${page <= 1 ? "disabled" : ""}>上一页</button>
              <button class="btn ghost sm" id="ck-next" ${page * 15 >= res.total ? "disabled" : ""}>下一页</button>
            </div>`
            : `<div class="empty"><span class="ico">📭</span>今天还没有人康复日志</div>`,
          footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`,
          onMount(m) {
            const prev = m.querySelector("#ck-prev"), next = m.querySelector("#ck-next");
            if (prev) prev.onclick = () => { page--; loadPage(); };
            if (next) next.onclick = () => { page++; loadPage(); };
          },
        });
      } catch (err) { toast(err.message, "error"); }
    };
    loadPage();
  };

  el.querySelector("#drill-msg").onclick = async () => {
    let page = 1;
    const typeLabel = { text: "聊天", image: "图片", voice: "语音", video: "视频", system: "系统通知" };
    const loadPage = async () => {
      try {
        const res = await api(`/api/admin/stats/messages?page=${page}&page_size=15`);
        openModal({
          title: `近30天消息明细（共 ${res.total} 条）`,
          wide: true,
          content: res.items.length ? `
            <table><thead><tr><th>发送方</th><th>接收方</th><th>类型</th><th>内容</th><th>时间</th><th>已读</th></tr></thead>
            <tbody>${res.items.map((m) => `<tr>
              <td><b>${escapeHtml(m.sender_name || "系统")}</b><div style="font-size:11px;color:var(--text-2)">${{ student: "患者", coach: "康复治疗师", admin: "管理员" }[m.sender_role] || "系统"}</div></td>
              <td><b>${escapeHtml(m.receiver_name || "-")}</b><div style="font-size:11px;color:var(--text-2)">${{ student: "患者", coach: "康复治疗师", admin: "管理员" }[m.receiver_role] || "-"}</div></td>
              <td><span class="tag ${m.msg_type === "system" ? "purple" : ""}">${typeLabel[m.msg_type] || m.msg_type}</span></td>
              <td style="max-width:260px;font-size:12px;color:var(--text-2)">${escapeHtml((m.content || "").slice(0, 50))}</td>
              <td style="font-size:12px">${fmtTime(m.created_at)}</td>
              <td>${m.is_read ? '<span class="tag green">已读</span>' : '<span class="tag gray">未读</span>'}</td>
            </tr>`).join("")}</tbody></table>
            <div class="pagination">
              <span>第 ${page} 页</span>
              <button class="btn ghost sm" id="msg-prev" ${page <= 1 ? "disabled" : ""}>上一页</button>
              <button class="btn ghost sm" id="msg-next" ${page * 15 >= res.total ? "disabled" : ""}>下一页</button>
            </div>`
            : `<div class="empty"><span class="ico">📭</span>近30天暂无消息</div>`,
          footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`,
          onMount(m) {
            const prev = m.querySelector("#msg-prev"), next = m.querySelector("#msg-next");
            if (prev) prev.onclick = () => { page--; loadPage(); };
            if (next) next.onclick = () => { page++; loadPage(); };
          },
        });
      } catch (err) { toast(err.message, "error"); }
    };
    loadPage();
  };

  function drawChart(t) {
    killCharts();
    charts.push(new Chart(document.getElementById("trend-chart"), {
      type: "line",
      data: {
        labels: t.map((x) => x.date.slice(5)),
        datasets: [
          { label: "新增用户", data: t.map((x) => x.new_users), borderColor: "#2E8B84", tension: 0.35 },
          { label: "康复日志数", data: t.map((x) => x.checkins), borderColor: "#00E676", tension: 0.35 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    }));
  }
  afterRender(() => drawChart(trend));
}

/* ================= 用户管理 ================= */
async function viewUsers(el) {
  let page = 1, role = "", q = "", status = "";

  async function load() {
    const params = new URLSearchParams({ page, page_size: 15 });
    if (role) params.set("role", role);
    if (q) params.set("q", q);
    if (status !== "") params.set("status", status);
    const res = await api(`/api/admin/users?${params}`);
    box.innerHTML = `
      <table><thead><tr><th>用户</th><th>角色</th><th>康复日志</th><th>最近登录</th><th>注册时间</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>${res.items.map((u) => `<tr>
        <td><b>${escapeHtml(u.nickname)}</b><div style="color:var(--text-2);font-size:12px">@${escapeHtml(u.username)} ${u.phone || ""}</div></td>
        <td><span class="tag ${{ student: "", coach: "purple", admin: "red" }[u.role]}">${{ student: "患者", coach: "康复治疗师", admin: "管理员" }[u.role]}</span></td>
        <td class="num">${u.checkin_count} 次<div style="color:var(--text-2);font-size:12px">最近 ${u.last_checkin || "-"}</div></td>
        <td style="font-size:12px">${u.last_login_at ? fmtTime(u.last_login_at) : "-"}</td>
        <td style="font-size:12px">${fmtDate(u.created_at)}</td>
        <td>${u.status === 1 ? '<span class="tag green">启用</span>' : '<span class="tag red">禁用</span>'}</td>
        <td class="flex wrap">
          <button class="btn ghost sm" data-toggle="${u.id}" data-st="${u.status}">${u.status === 1 ? "禁用" : "启用"}</button>
          <button class="btn ghost sm" data-role="${u.id}" data-cur="${u.role}">角色</button>
          <button class="btn ghost sm" data-reset="${u.id}">重置密码</button>
        </td>
      </tr>`).join("")}</tbody></table>
      <div class="pagination">
        <span>共 ${res.total} 条 · 第 ${page} 页</span>
        <button class="btn ghost sm" id="pg-prev" ${page <= 1 ? "disabled" : ""}>上一页</button>
        <button class="btn ghost sm" id="pg-next" ${page * 15 >= res.total ? "disabled" : ""}>下一页</button>
      </div>`;

    const prev = box.querySelector("#pg-prev"), next = box.querySelector("#pg-next");
    if (prev) prev.onclick = () => { page--; load(); };
    if (next) next.onclick = () => { page++; load(); };

    box.querySelectorAll("[data-toggle]").forEach((b) => {
      b.onclick = () => {
        const enable = b.dataset.st === "0";
        confirmBox(`确定${enable ? "启用" : "禁用"}该账号？`, async () => {
          await api(`/api/admin/users/${b.dataset.toggle}/status`, { method: "PUT", body: { status: enable ? 1 : 0 } });
          closeModal(); toast("已更新", "success"); load();
        });
      };
    });
    box.querySelectorAll("[data-role]").forEach((b) => {
      b.onclick = () => {
        openModal({
          title: "调整角色",
          content: `<div class="field"><select id="r-sel">
            ${["student", "coach", "admin"].map((r) => `<option value="${r}" ${b.dataset.cur === r ? "selected" : ""}>${{ student: "患者", coach: "康复治疗师", admin: "管理员" }[r]}</option>`).join("")}
          </select></div>`,
          footer: `<button class="btn" id="r-save">保存</button>`,
          onMount(m) {
            m.querySelector("#r-save").onclick = async () => {
              await api(`/api/admin/users/${b.dataset.role}/role`, { method: "PUT", body: { role: m.querySelector("#r-sel").value } });
              closeModal(); toast("角色已更新", "success"); load();
            };
          },
        });
      };
    });
    box.querySelectorAll("[data-reset]").forEach((b) => {
      b.onclick = () => {
        openModal({
          title: "重置密码",
          content: `<div class="field"><label>新密码（至少6位）</label><input id="rp-input" minlength="6"></div>`,
          footer: `<button class="btn warn" id="rp-save">重置</button>`,
          onMount(m) {
            m.querySelector("#rp-save").onclick = async () => {
              const pwd = m.querySelector("#rp-input").value;
              if (pwd.length < 6) return toast("密码至少6位", "warn");
              await api(`/api/admin/users/${b.dataset.reset}/reset-password`, { method: "POST", body: { new_password: pwd } });
              closeModal(); toast("密码已重置", "success");
            };
          },
        });
      };
    });
  }

  el.innerHTML = `
    <div class="card">
      <div class="filter-bar">
        <input id="u-q" placeholder="搜索用户名/昵称/手机号…" style="width:220px">
        <select id="u-role"><option value="">全部角色</option><option value="student">患者</option><option value="coach">康复治疗师</option><option value="admin">管理员</option></select>
        <select id="u-status"><option value="">全部状态</option><option value="1">启用</option><option value="0">禁用</option></select>
        <button class="btn" id="u-search">搜索</button>
      </div>
      <div id="users-box"></div>
    </div>`;
  const box = el.querySelector("#users-box");
  el.querySelector("#u-search").onclick = () => {
    q = el.querySelector("#u-q").value.trim();
    role = el.querySelector("#u-role").value;
    status = el.querySelector("#u-status").value;
    page = 1;
    load();
  };
  load();
}

/* ================= 康复治疗师审核 ================= */
async function viewCoachReview(el) {
  let status = "pending";
  const statusTag = { approved: ["green", "✔ 已认证"], pending: ["warn", "待审核"], rejected: ["red", "已驳回"], none: ["gray", "未提交"] };

  async function load() {
    const rows = await api(`/api/admin/coach-reviews${status ? `?status=${status}` : ""}`);
    box.innerHTML = rows.length ? rows.map((c) => `
      <div class="card mb-16">
        <div class="flex between wrap">
          <div class="flex">
            ${avatarHtml(c.nickname, c.avatar)}
            <div>
              <b style="font-size:15px">${escapeHtml(c.nickname)}</b> <span style="color:var(--text-2)">@${escapeHtml(c.username)}</span>
              <div style="color:var(--text-2);font-size:12px">注册于 ${fmtDate(c.register_at)}</div>
            </div>
          </div>
          <span class="tag ${statusTag[c.review_status][0]}">${statusTag[c.review_status][1]}</span>
        </div>
        ${c.review_status === "approved" && (c.bio || c.specialty) ? `
          <div style="margin-top:14px;padding:12px 14px;background:rgba(0,230,118,0.06);border:1px solid rgba(0,230,118,0.25);border-radius:8px">
            <div style="font-size:12px;color:var(--success);margin-bottom:4px">🧑‍🏫 康复治疗师简介</div>
            ${c.specialty ? `<div style="margin-bottom:4px"><span style="color:var(--text-2)">擅长：</span>${escapeHtml(c.specialty)}</div>` : ""}
            ${c.bio ? `<div style="white-space:pre-wrap;line-height:1.7">${escapeHtml(c.bio)}</div>` : ""}
          </div>` : `
          <div class="grid cols-2 mt-16" style="font-size:13px">
            <div><span style="color:var(--text-2)">真实姓名：</span>${escapeHtml(c.real_name || "-")}</div>
            <div><span style="color:var(--text-2)">擅长领域：</span>${escapeHtml(c.specialty || "-")}</div>
            <div style="grid-column:span 2"><span style="color:var(--text-2)">履历：</span>${escapeHtml(c.bio || "-")}</div>
            <div style="grid-column:span 2"><span style="color:var(--text-2)">证书：</span>${escapeHtml(c.certifications || "-")}</div>
          </div>`}
        ${c.certifications && c.review_status === "approved" ? `<div style="margin-top:10px;font-size:13px"><span style="color:var(--text-2)">证书：</span>${escapeHtml(c.certifications)}</div>` : ""}
        ${c.review_note ? `<div style="margin-top:10px;color:var(--warning);font-size:13px">审核备注：${escapeHtml(c.review_note)}</div>` : ""}
        <div class="flex mt-16">
          ${c.review_status === "pending" ? `
            <button class="btn" data-ok="${c.user_id}">✓ 通过认证</button>
            <button class="btn danger" data-no="${c.user_id}">驳回申请</button>` : ""}
          ${c.review_status === "rejected" ? `<button class="btn" data-ok="${c.user_id}">✓ 重新通过认证</button>` : ""}
          ${c.review_status === "approved" ? `<button class="btn ghost sm" data-revoke="${c.user_id}">撤销认证</button>` : ""}
        </div>
      </div>`).join("")
      : `<div class="empty"><span class="ico">🧑‍🏫</span>${{ pending: "没有待审核的康复治疗师申请", approved: "暂无已认证康复治疗师", rejected: "暂无已驳回申请", "": "暂无康复治疗师注册" }[status]}</div>`;

    box.querySelectorAll("[data-ok]").forEach((b) => {
      b.onclick = () => review(+b.dataset.ok, true);
    });
    box.querySelectorAll("[data-no]").forEach((b) => {
      b.onclick = () => review(+b.dataset.no, false);
    });
    box.querySelectorAll("[data-revoke]").forEach((b) => {
      b.onclick = () => confirmBox("确定撤销该康复治疗师的认证？撤销后其将无法使用康复治疗师端功能。", async () => {
        await api(`/api/admin/coach-reviews/${b.dataset.revoke}/review`, {
          method: "POST", body: { approve: false, review_note: "管理员撤销认证" },
        });
        closeModal(); toast("已撤销认证", "success"); load();
      });
    });
  }

  async function review(userId, approve) {
    openModal({
      title: approve ? "通过认证" : "驳回申请",
      content: `<div class="field"><label>审核意见${approve ? "（可选）" : "（必填，将通知申请人）"}</label><textarea id="rv-note" maxlength="500"></textarea></div>`,
      footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">取消</button>
               <button class="btn ${approve ? "" : "danger"}" id="rv-save">${approve ? "确认通过" : "确认驳回"}</button>`,
      onMount(m) {
        m.querySelector("#rv-save").onclick = async () => {
          const note = m.querySelector("#rv-note").value;
          if (!approve && !note.trim()) return toast("驳回时请填写审核意见", "warn");
          await api(`/api/admin/coach-reviews/${userId}/review`, {
            method: "POST",
            body: { approve, review_note: note },
          });
          closeModal(); toast("审核完成", "success"); load();
        };
      },
    });
  }

  el.innerHTML = `
    <div class="card">
      <div class="filter-bar">
        ${[["pending", "待审核"], ["approved", "已认证"], ["rejected", "已驳回"], ["", "全部"]].map(([v, t]) =>
          `<button class="btn ghost sm" data-st="${v}">${t}</button>`).join("")}
      </div>
      <div id="cr-box"></div>
    </div>`;
  const box = el.querySelector("#cr-box");
  el.querySelectorAll("[data-st]").forEach((b) => {
    b.classList.toggle("active-filter", b.dataset.st === status);
    b.onclick = () => {
      status = b.dataset.st;
      el.querySelectorAll("[data-st]").forEach((x) => x.classList.toggle("active-filter", x === b));
      load();
    };
  });
  load();
}

/* ================= 公告管理 ================= */
async function viewAnnouncements(el) {
  async function load() {
    const rows = await api("/api/admin/announcements");
    box.innerHTML = rows.length ? rows.map((a) => `
      <div class="card mb-16 ann-item" data-id="${a.id}" style="cursor:pointer;transition:border-color .18s">
        <div class="flex between wrap">
          <b>${a.is_pinned ? "📌 " : ""}${escapeHtml(a.title)}</b>
          <span class="flex">
            <span class="tag ${{ published: "green", draft: "gray", offline: "red" }[a.status]}">${{ published: "已发布", draft: "草稿", offline: "已下架" }[a.status]}</span>
            <span class="tag gray">${{ all: "全部", student: "患者", coach: "康复治疗师" }[a.target_role]}</span>
          </span>
        </div>
        <p style="color:var(--text-2);font-size:13px;margin:8px 0">${escapeHtml(a.content.length > 80 ? a.content.slice(0, 80) + "…" : a.content)}</p>
        <div class="flex between">
          <span style="color:var(--text-2);font-size:12px">${fmtTime(a.publish_at)} · ${escapeHtml(a.creator || "系统")} <span style="color:var(--primary);font-size:12px">点击查看详情 →</span></span>
          <span class="flex">
            <button class="btn ghost sm" data-edit='${JSON.stringify(a).replace(/'/g, "&#39;")}'>编辑</button>
            <button class="btn danger sm" data-del="${a.id}">删除</button>
          </span>
        </div>
      </div>`).join("") : `<div class="empty"><span class="ico">📢</span>暂无公告</div>`;

    box.querySelectorAll(".ann-item").forEach((card) => {
      card.onclick = () => {
        const a = rows.find((x) => x.id === +card.dataset.id);
        if (!a) return;
        openModal({
          title: `${a.is_pinned ? "📌 " : ""}${escapeHtml(a.title)}`,
          content: `
            <div class="flex wrap mb-16">
              <span class="tag ${{ published: "green", draft: "gray", offline: "red" }[a.status]}">${{ published: "已发布", draft: "草稿", offline: "已下架" }[a.status]}</span>
              <span class="tag gray">面向：${{ all: "全部用户", student: "患者", coach: "康复治疗师" }[a.target_role]}</span>
              <span class="tag ${a.is_pinned ? "warn" : "gray"}">${a.is_pinned ? "已置顶" : "未置顶"}</span>
            </div>
            <div style="white-space:pre-wrap;line-height:1.8;color:var(--text)">${escapeHtml(a.content)}</div>
            <div style="margin-top:16px;padding-top:12px;border-top:1px solid var(--border);color:var(--text-2);font-size:12px">
              发布时间：${fmtTime(a.publish_at)} · 创建人：${escapeHtml(a.creator || "系统")}
            </div>`,
          footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`,
        });
      };
    });

    box.querySelectorAll("[data-del]").forEach((b) => {
      b.onclick = (e) => {
        e.stopPropagation();
        confirmBox("确定删除该公告？", async () => {
          await api(`/api/admin/announcements/${b.dataset.del}`, { method: "DELETE" });
          closeModal(); toast("已删除", "success"); load();
        });
      };
    });
    box.querySelectorAll("[data-edit]").forEach((b) => {
      b.onclick = (e) => {
        e.stopPropagation();
        openForm(JSON.parse(b.dataset.edit));
      };
    });
  }

  function openForm(a) {
    a = a || { title: "", content: "", is_pinned: 0, status: "published", target_role: "all" };
    openModal({
      title: a.id ? "编辑公告" : "发布公告",
      content: `
        <div class="field"><label>标题</label><input id="a-title" value="${escapeHtml(a.title)}" maxlength="100"></div>
        <div class="field"><label>内容</label><textarea id="a-content" maxlength="2000">${escapeHtml(a.content)}</textarea></div>
        <div class="grid cols-3">
          <div class="field"><label>状态</label><select id="a-status">
            <option value="published" ${a.status === "published" ? "selected" : ""}>发布</option>
            <option value="draft" ${a.status === "draft" ? "selected" : ""}>草稿</option>
            <option value="offline" ${a.status === "offline" ? "selected" : ""}>下架</option>
          </select></div>
          <div class="field"><label>定向</label><select id="a-target">
            <option value="all" ${a.target_role === "all" ? "selected" : ""}>全部</option>
            <option value="student" ${a.target_role === "student" ? "selected" : ""}>患者</option>
            <option value="coach" ${a.target_role === "coach" ? "selected" : ""}>康复治疗师</option>
          </select></div>
          <div class="field"><label>置顶</label><select id="a-pin">
            <option value="0" ${!a.is_pinned ? "selected" : ""}>否</option>
            <option value="1" ${a.is_pinned ? "selected" : ""}>是</option>
          </select></div>
        </div>`,
      footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">取消</button>
               <button class="btn" id="a-save">保存</button>`,
      onMount(m) {
        m.querySelector("#a-save").onclick = async () => {
          const payload = {
            title: m.querySelector("#a-title").value.trim(),
            content: m.querySelector("#a-content").value.trim(),
            status: m.querySelector("#a-status").value,
            target_role: m.querySelector("#a-target").value,
            is_pinned: +m.querySelector("#a-pin").value,
          };
          if (!payload.title || !payload.content) return toast("请填写标题与内容", "warn");
          if (a.id) await api(`/api/admin/announcements/${a.id}`, { method: "PUT", body: payload });
          else await api("/api/admin/announcements", { method: "POST", body: payload });
          closeModal(); toast("已保存", "success"); load();
        };
      },
    });
  }

  el.innerHTML = `<div class="card"><div class="filter-bar"><button class="btn" id="a-new">+ 发布公告</button></div><div id="ann-box"></div></div>`;
  const box = el.querySelector("#ann-box");
  el.querySelector("#a-new").onclick = () => openForm(null);
  load();
}

/* ================= 计划分配总览（只读） ================= */
async function viewPlans(el) {
  async function load() {
    const params = q ? `?q=${encodeURIComponent(q)}` : "";
    const rows = await api(`/api/admin/plans${params}`);
    box.innerHTML = rows.length ? `
      <table><thead><tr><th>计划</th><th>康复治疗师 → 患者</th><th>周期</th><th>动作条目</th><th>推荐状态</th><th>计划状态</th><th>创建时间</th></tr></thead>
      <tbody>${rows.map((p) => `<tr>
        <td><b>${escapeHtml(p.title)}</b>${p.description ? `<div style="font-size:12px;color:var(--text-2);max-width:220px">${escapeHtml(p.description.slice(0, 40))}</div>` : ""}</td>
        <td>${escapeHtml(p.coach_name)} → <b>${escapeHtml(p.student_name)}</b></td>
        <td style="font-size:12px">${p.start_date} ~ ${p.end_date}</td>
        <td class="num">${p.item_count} 项</td>
        <td>${p.is_recommended ? '<span class="tag purple">康复治疗师推荐中</span>' : '<span class="tag gray">未推荐</span>'}</td>
        <td>${p.status === "active" ? '<span class="tag green">进行中</span>' : '<span class="tag gray">已结束</span>'}</td>
        <td style="font-size:12px">${fmtDate(p.created_at)}</td>
      </tr>`).join("")}</tbody></table>`
      : `<div class="empty"><span class="ico">📋</span>${q ? "没有匹配的康复方案" : "暂无康复方案：康复治疗师在康复治疗师端给患者制定后，会在此展示分配情况"}</div>`;

    const count = el.querySelector("#plans-count");
    if (count) count.textContent = `共 ${rows.length} 条`;
  }

  let q = "";
  el.innerHTML = `
    <div class="card">
      <div class="section-title">
        计划分配总览
        <span class="flex">
          <input id="p-q" placeholder="搜索计划标题…" style="width:200px">
          <button class="btn ghost sm" id="p-search">搜索</button>
          <span id="plans-count" class="tag gray"></span>
        </span>
      </div>
      <p style="color:var(--text-2);font-size:12px;margin-bottom:12px">计划由康复治疗师在康复治疗师端制定并布置给患者，推荐操作也在康复治疗师端完成，此处仅展示分配情况。</p>
      <div id="plans-box"></div>
    </div>`;
  const box = el.querySelector("#plans-box");
  el.querySelector("#p-search").onclick = () => { q = el.querySelector("#p-q").value.trim(); load(); };
  el.querySelector("#p-q").onkeydown = (e) => { if (e.key === "Enter") el.querySelector("#p-search").click(); };
  load();
}

/* ================= 系统配置 ================= */
async function viewConfigs(el) {
  const rows = await api("/api/admin/configs");
  const labels = {
    checkin_window_start: "每日康复日志窗口开始",
    checkin_window_end: "每日康复日志窗口结束",
    makeup_days_limit: "补签回溯天数上限",
    ranking_refresh_sec: "排行榜刷新间隔(秒)",
    max_image_size_mb: "图片上传上限(MB)",
    max_video_size_mb: "视频上传上限(MB)",
    log_retention_days: "日志保留天数",
  };
  el.innerHTML = `
    <div class="card" style="max-width:640px">
      <div class="section-title">系统参数</div>
      <form id="cfg-form">
        ${rows.map((r) => `
          <div class="field"><label>${labels[r.config_key] || r.config_key} <span class="tag gray" style="font-size:11px">${r.config_key}</span></label>
          <input name="${r.config_key}" value="${escapeHtml(r.config_value)}"></div>`).join("")}
        <button class="btn" type="submit">保存配置</button>
      </form>
    </div>`;
  el.querySelector("#cfg-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const configs = {};
    fd.forEach((v, k) => (configs[k] = v));
    try {
      await api("/api/admin/configs", { method: "PUT", body: { configs } });
      toast("配置已保存", "success");
    } catch (err) { toast(err.message, "error"); }
  };
}

/* ================= 操作日志 ================= */
async function viewLogs(el) {
  let page = 1, module = "";

  async function load() {
    const params = new URLSearchParams({ page, page_size: 20 });
    if (module) params.set("module", module);
    const res = await api(`/api/admin/logs?${params}`);
    box.innerHTML = `
      <table><thead><tr><th>时间</th><th>操作人</th><th>模块</th><th>操作</th><th>详情</th><th>IP</th></tr></thead>
      <tbody>${res.items.map((l) => `<tr>
        <td style="font-size:12px">${fmtTime(l.created_at)}</td>
        <td>${escapeHtml(l.admin_name || "系统")}</td>
        <td><span class="tag gray">${escapeHtml(l.module)}</span></td>
        <td>${escapeHtml(l.action)}</td>
        <td style="font-size:12px;color:var(--text-2)">${escapeHtml(l.detail)}</td>
        <td class="num" style="font-size:12px">${escapeHtml(l.ip || "-")}</td>
      </tr>`).join("") || `<tr><td colspan="6" class="empty">暂无日志</td></tr>`}</tbody></table>
      <div class="pagination">
        <span>共 ${res.total} 条 · 第 ${page} 页 · 日志保留90天</span>
        <button class="btn ghost sm" id="lg-prev" ${page <= 1 ? "disabled" : ""}>上一页</button>
        <button class="btn ghost sm" id="lg-next" ${page * 20 >= res.total ? "disabled" : ""}>下一页</button>
      </div>`;
    const prev = box.querySelector("#lg-prev"), next = box.querySelector("#lg-next");
    if (prev) prev.onclick = () => { page--; load(); };
    if (next) next.onclick = () => { page++; load(); };
  }

  el.innerHTML = `
    <div class="card">
      <div class="filter-bar">
        <select id="lg-module"><option value="">全部模块</option>
          ${["用户管理", "康复治疗师审核", "内容管理", "系统配置", "系统"].map((m) => `<option value="${m}">${m}</option>`).join("")}
        </select>
        <button class="btn" id="lg-search">筛选</button>
      </div>
      <div id="lg-box"></div>
    </div>`;
  const box = el.querySelector("#lg-box");
  el.querySelector("#lg-search").onclick = () => {
    module = el.querySelector("#lg-module").value;
    page = 1;
    load();
  };
  load();
}

export function initAdmin() {
  registerViews("admin", {
    dashboard: viewDashboard,
    revenue: viewRevenue,
    users: viewUsers,
    coachreview: viewCoachReview,
    withdrawals: viewWithdrawals,
    announcements: viewAnnouncements,
    plans: viewPlans,
    configs: viewConfigs,
    logs: viewLogs,
  });
}
