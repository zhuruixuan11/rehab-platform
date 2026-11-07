/* P1/P2 前端功能视图：会员内容墙 / AI点评 / 邀请裂变 / 优惠券 / 康复治疗师收益 / 营收看板 / 提现审核 */
import { toast, openModal, closeModal, escapeHtml, fmtNum, fmtDate, fmtTime, avatarHtml, me } from "./app.js";
import { api } from "./api.js";

/* =============== 患者端：会员内容墙 =============== */
export async function viewMemberContent(el) {
  const items = await api("/api/features/member-content");
  const isMember = me().is_member;
  el.innerHTML = `
    <div class="section-title">📖 会员内容墙 ${isMember ? '' : '<span class="tag warn" style="font-size:12px">开通会员看完整内容</span>'}</div>
    <div class="grid cols-2" style="gap:14px;margin-top:12px">
      ${items.length ? items.map((c) => `
        <div class="card" style="cursor:pointer" data-cid="${c.id}">
          <div class="flex between" style="margin-bottom:8px">
            <b>${escapeHtml(c.title)}</b>
            <span class="tag gray">${{article:'文章',video:'视频',course:'课程'}[c.category]||c.category}</span>
          </div>
          <div style="color:var(--text-2);font-size:13px;white-space:pre-wrap;line-height:1.7;max-height:120px;overflow:hidden">
            ${escapeHtml(c.content)}
          </div>
          <div style="color:var(--text-2);font-size:12px;margin-top:10px">${avatarHtml(c.author_name, '', 'sm')} ${escapeHtml(c.author_name)} · 👁 ${c.view_count}</div>
        </div>`).join("") : '<div class="empty">暂无内容</div>'}
    </div>`;
  el.querySelectorAll("[data-cid]").forEach((c) => {
    c.onclick = async () => {
      const d = await api("/api/features/member-content/" + c.dataset.cid);
      openModal({
        title: d.title,
        content: `<div style="white-space:pre-wrap;line-height:1.8;font-size:14px">${escapeHtml(d.content)}</div>
                  ${d.is_locked ? '<div style="margin-top:16px;padding:12px;background:rgba(46,139,132,0.08);border-radius:8px"><a href="#/member" class="btn warn">⭐ 开通会员查看完整内容</a></div>' : ''}`,
        footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`,
      });
    };
  });
}

/* =============== 患者端：邀请裂变 =============== */
export async function renderInvite(el) {
  const info = await api("/api/features/invite/info");
  el.innerHTML = `
    <div class="card" style="background:linear-gradient(135deg,rgba(46,139,132,0.1),rgba(99,184,174,0.1));border-color:rgba(46,139,132,0.3)">
      <div class="section-title">🎁 邀请好友，双方得会员</div>
      <div style="color:var(--text-2);font-size:13px;margin:8px 0 16px">每邀请1位好友注册，<b style="color:var(--warning)">你获得7天会员</b>，好友也能开始康复训练～</div>
      <div class="flex between wrap" style="gap:12px;align-items:center">
        <div>
          <div style="color:var(--text-2);font-size:12px">我的邀请码</div>
          <div style="font-size:24px;font-weight:800;letter-spacing:4px;color:var(--warning)">${info.invite_code}</div>
        </div>
        <div style="text-align:center">
          <div style="font-size:28px;font-weight:800;color:var(--warning)">${info.invited_count}</div>
          <div style="color:var(--text-2);font-size:12px">已邀请好友</div>
        </div>
        <div style="text-align:center">
          <div style="font-size:28px;font-weight:800;color:var(--success)">${info.reward_days_total}</div>
          <div style="color:var(--text-2);font-size:12px">获得会员天数</div>
        </div>
      </div>
      <div class="flex wrap" style="gap:10px;margin-top:16px">
        <button class="btn warn" id="copy-link">📋 复制邀请链接</button>
        <button class="btn ghost" id="claim-btn">填写好友邀请码</button>
      </div>
      ${info.list.length ? `
        <div style="margin-top:16px">
          <div style="color:var(--text-2);font-size:12px;margin-bottom:8px">邀请记录</div>
          <div class="grid cols-2" style="gap:8px">
            ${info.list.map((i) => `<div class="flex" style="gap:8px;padding:8px;background:var(--card-2);border-radius:8px">${avatarHtml(i.nickname,'','sm')}<div><b style="font-size:13px">${escapeHtml(i.nickname)}</b><div style="color:var(--success);font-size:11px">+${i.reward_days}天会员</div></div></div>`).join("")}
          </div>
        </div>` : ''}
    </div>`;
  el.querySelector("#copy-link").onclick = () => {
    navigator.clipboard.writeText(info.invite_link);
    toast("邀请链接已复制", "success");
  };
  el.querySelector("#claim-btn").onclick = () => {
    openModal({
      title: "填写好友邀请码",
      content: `<input id="invite-code-input" placeholder="输入好友的邀请码" style="margin-top:12px">`,
      footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">取消</button>
               <button class="btn warn" id="do-claim">提交</button>`,
      onMount(m) {
        m.querySelector("#do-claim").onclick = async () => {
          const code = m.querySelector("#invite-code-input").value.trim();
          if (!code) return toast("请输入邀请码", "error");
          try {
            await api("/api/features/invite/claim?code=" + encodeURIComponent(code), { method: "POST" });
            closeModal();
            toast("邀请成功！好友获得7天会员", "success");
            renderInvite(el);
          } catch (e) { toast(e.message, "error"); }
        };
      },
    });
  };
}

/* =============== 患者端：优惠券 =============== */
export async function renderCoupons(el) {
  const [available, mine] = await Promise.all([api("/api/features/coupons"), api("/api/features/coupons/mine")]);
  el.innerHTML = `
    <div class="section-title">🎟️ 优惠券</div>
    <div class="grid cols-2" style="gap:12px;margin-top:12px">
      ${available.map((c) => {
        const owned = mine.find((m) => m.coupon_id === c.id);
        return `
        <div class="card" style="border-left:4px solid var(--warning);padding:16px">
          <div class="flex between">
            <div>
              <b>${escapeHtml(c.name)}</b>
              <div style="color:var(--warning);font-size:24px;font-weight:800;margin-top:4px">
                ${c.type === 'percent' ? c.value + '折' : '¥' + c.value}
                ${c.min_amount > 0 ? `<span style="font-size:12px;color:var(--text-2)">满${c.min_amount}可用</span>` : ''}
              </div>
              <div style="color:var(--text-2);font-size:11px;margin-top:4px">有效期至 ${fmtDate(c.end_date)}</div>
            </div>
            ${owned ? '<span class="tag gray">已领取</span>' : `<button class="btn warn sm" data-claim="${c.id}">领取</button>`}
          </div>
        </div>`;
      }).join("")}
    </div>`;
  el.querySelectorAll("[data-claim]").forEach((b) => {
    b.onclick = async () => {
      try {
        await api("/api/features/coupons/" + b.dataset.claim + "/claim", { method: "POST" });
        toast("领取成功", "success");
        renderCoupons(el);
      } catch (e) { toast(e.message, "error"); }
    };
  });
}

/* =============== 康复治疗师端：我的收益 =============== */
export async function viewCoachEarnings(el) {
  const e = await api("/api/features/coach/earnings");
  el.innerHTML = `
    <div class="grid cols-3 mb-16" style="gap:12px">
      <div class="card"><div style="color:var(--text-2);font-size:13px">累计收益</div><div style="font-size:28px;font-weight:800;color:var(--warning)">¥${fmtNum(e.total_earned)}</div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">已提现</div><div style="font-size:28px;font-weight:800;color:var(--success)">¥${fmtNum(e.withdrawn)}</div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">可提现</div><div style="font-size:28px;font-weight:800;color:var(--primary)">¥${fmtNum(e.available)}</div></div>
    </div>
    <div class="card mb-16">
      <div class="section-title">💸 申请提现</div>
      <div class="flex wrap" style="gap:12px;margin-top:12px">
        <div class="field" style="margin:0;flex:1;min-width:120px"><label>提现金额</label><input type="number" id="w-amount" min="1" step="0.01" placeholder="最低1元"></div>
        <div class="field" style="margin:0;flex:1"><label>银行</label><input id="w-bank" placeholder="如：招商银行"></div>
        <div class="field" style="margin:0;flex:1"><label>账号</label><input id="w-account" placeholder="银行卡号"></div>
        <button class="btn warn" id="do-withdraw" style="align-self:flex-end">申请提现</button>
      </div>
      <div style="color:var(--text-2);font-size:12px;margin-top:8px">* 当前为 Mock 提现，真实上线需对接银行/微信提现接口</div>
    </div>
    ${e.withdrawals.length ? `
    <div class="card">
      <div class="section-title">📋 提现记录</div>
      <table><thead><tr><th>申请时间</th><th>金额</th><th>银行</th><th>状态</th></tr></thead>
      <tbody>${e.withdrawals.map((w) => `<tr><td>${fmtTime(w.created_at)}</td><td class="num">¥${fmtNum(w.amount)}</td><td>${escapeHtml(w.bank_name||'-')}</td><td><span class="tag ${{pending:'warn',approved:'green',rejected:'red',paid:'gray'}[w.status]}">${{pending:'审核中',approved:'已批准',rejected:'已拒绝',paid:'已打款'}[w.status]}</span></td></tr>`).join("")}</tbody></table>
    </div>` : '<div class="card"><div class="empty">暂无提现记录</div></div>'}
  `;
  el.querySelector("#do-withdraw").onclick = async () => {
    const amount = +el.querySelector("#w-amount").value;
    const bank = el.querySelector("#w-bank").value;
    const account = el.querySelector("#w-account").value;
    if (!amount || amount <= 0) return toast("请输入有效金额", "error");
    if (!bank || !account) return toast("请填写银行信息", "error");
    try {
      await api("/api/features/coach/withdraw", { method: "POST", body: { amount, bank_name: bank, bank_account: account } });
      toast("提现申请已提交", "success");
      viewCoachEarnings(el);
    } catch (err) { toast(err.message, "error"); }
  };
}

/* =============== 管理端：营收看板 =============== */
export async function viewRevenue(el) {
  const d = await api("/api/features/revenue/dashboard");
  el.innerHTML = `
    <div class="grid cols-4 mb-16" style="gap:12px">
      <div class="card"><div style="color:var(--text-2);font-size:13px">总营收</div><div style="font-size:26px;font-weight:800;color:var(--warning)">¥${fmtNum(d.total_revenue)}</div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">本月营收</div><div style="font-size:26px;font-weight:800;color:var(--primary)">¥${fmtNum(d.month_revenue)}</div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">今日营收</div><div style="font-size:26px;font-weight:800;color:var(--success)">¥${fmtNum(d.today_revenue)}</div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">活跃会员</div><div style="font-size:26px;font-weight:800;color:var(--accent)">${d.active_members}人</div></div>
    </div>
    <div class="grid cols-3 mb-16" style="gap:12px">
      <div class="card"><div style="color:var(--text-2);font-size:13px">付费定制订单</div><div style="font-size:22px;font-weight:700">${d.paid_plan_orders}笔</div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">康复营订单</div><div style="font-size:22px;font-weight:700">${d.bootcamp_orders}笔</div></div>
      <div class="card"><div style="color:var(--text-2);font-size:13px">ARPU</div><div style="font-size:22px;font-weight:700">¥${d.active_members ? fmtNum(d.total_revenue/d.active_members) : 0}</div></div>
    </div>
    <div class="card">
      <div class="section-title">📈 近30天营收趋势</div>
      <div style="height:260px;margin-top:12px"><canvas id="rev-chart"></canvas></div>
    </div>`;
  try {
    const Chart = window.Chart;
    const ctx = document.getElementById("rev-chart");
    if (!Chart) {
      document.getElementById("rev-chart").outerHTML = '<div class="empty">图表库未加载</div>';
      return;
    }
    if (ctx && d.trend.length) {
      new Chart(ctx, {
        type: "line",
        data: { labels: d.trend.map((t) => t.date.slice(5)), datasets: [{ label: "营收¥", data: d.trend.map((t) => t.amount), borderColor: "#2E8B84", backgroundColor: "rgba(46,139,132,0.1)", fill: true, tension: 0.3 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { ticks: { color: "#B2BEC3" }, grid: { color: "#334155" } }, x: { ticks: { color: "#B2BEC3" }, grid: { display: false } } } },
      });
    }
  } catch (e) {
    const box = document.getElementById("rev-chart");
    if (box) box.outerHTML = '<div class="empty">图表加载失败</div>';
  }
}

/* =============== 管理端：提现审核 =============== */
export async function viewWithdrawals(el) {
  const rows = await api("/api/features/admin/withdrawals");
  el.innerHTML = `
    <div class="filter-bar mb-16">
      ${[["pending","待审核"],["approved","已批准"],["paid","已打款"],["rejected","已拒绝"],["","全部"]].map(([v,t])=>`<button class="btn ghost sm" data-st="${v}">${t}</button>`).join("")}
    </div>
    <div id="wd-box">
      ${rows.length ? `
      <table><thead><tr><th>时间</th><th>康复治疗师</th><th>金额</th><th>银行</th><th>账号</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>${rows.map((w)=>`<tr>
        <td>${fmtTime(w.created_at)}</td><td>${escapeHtml(w.coach_name)}</td><td class="num">¥${fmtNum(w.amount)}</td>
        <td>${escapeHtml(w.bank_name||'-')}</td><td>${escapeHtml(w.bank_account||'-')}</td>
        <td><span class="tag ${{pending:'warn',approved:'green',rejected:'red',paid:'gray'}[w.status]}">${{pending:'审核中',approved:'已批准',rejected:'已拒绝',paid:'已打款'}[w.status]}</span></td>
        <td>${w.status==='pending' ? `<button class="btn green sm" data-approve="${w.id}">批准</button> <button class="btn red sm" data-reject="${w.id}">拒绝</button>` : '-'}</td>
      </tr>`).join("")}</tbody></table>` : '<div class="empty">暂无提现申请</div>'}
    </div>`;
  el.querySelectorAll("[data-st]").forEach((b) => b.onclick = async () => {
    const q = b.dataset.st ? `?status=${b.dataset.st}` : "";
    const r = await api("/api/features/admin/withdrawals" + q);
    el.querySelector("#wd-box").innerHTML = renderTable(r);
    bindActions(el);
  });
  bindActions(el);
  function renderTable(rows) {
    return rows.length ? `<table><thead><tr><th>时间</th><th>康复治疗师</th><th>金额</th><th>银行</th><th>账号</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>${rows.map((w)=>`<tr>
        <td>${fmtTime(w.created_at)}</td><td>${escapeHtml(w.coach_name)}</td><td class="num">¥${fmtNum(w.amount)}</td>
        <td>${escapeHtml(w.bank_name||'-')}</td><td>${escapeHtml(w.bank_account||'-')}</td>
        <td><span class="tag ${{pending:'warn',approved:'green',rejected:'red',paid:'gray'}[w.status]}">${{pending:'审核中',approved:'已批准',rejected:'已拒绝',paid:'已打款'}[w.status]}</span></td>
        <td>${w.status==='pending' ? `<button class="btn green sm" data-approve="${w.id}">批准</button> <button class="btn red sm" data-reject="${w.id}">拒绝</button>` : '-'}</td>
      </tr>`).join("")}</tbody></table>` : '<div class="empty">暂无提现申请</div>';
  }
  function bindActions(root) {
    root.querySelectorAll("[data-approve]").forEach((b) => b.onclick = async () => {
      await api("/api/features/admin/withdrawals/" + b.dataset.approve + "/process?action=approve", { method: "POST" });
      toast("已批准", "success"); viewWithdrawals(el);
    });
    root.querySelectorAll("[data-reject]").forEach((b) => b.onclick = async () => {
      await api("/api/features/admin/withdrawals/" + b.dataset.reject + "/process?action=reject", { method: "POST" });
      toast("已拒绝", "success"); viewWithdrawals(el);
    });
  }
}
