import { api, getToken, setAuth, clearAuth, getCachedUser } from "./api.js";
import { initChat, destroyChat } from "./chat.js";
import { initCamp } from "./camp.js";
import { initStudent } from "./student.js";
import { initCoach } from "./coach.js";
import { initAdmin } from "./admin.js";

/* ---------------- UI 工具 ---------------- */
export function toast(msg, type = "info") {
  const root = document.getElementById("toast-root");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  root.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

export function openModal({ title, content, footer = "", wide = false, onMount }) {
  const root = document.getElementById("modal-root");
  root.innerHTML = `
    <div class="modal-mask">
      <div class="modal ${wide ? "wide" : ""}">
        <div class="m-head"><h3>${title}</h3><button class="m-close" aria-label="关闭">×</button></div>
        <div class="m-body">${content}</div>
        ${footer ? `<div class="m-foot">${footer}</div>` : ""}
      </div>
    </div>`;
  root.querySelector(".m-close").onclick = closeModal;
  root.querySelector(".modal-mask").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeModal();
  });
  if (onMount) onMount(root.querySelector(".modal"));
}

export function closeModal() {
  document.getElementById("modal-root").innerHTML = "";
}

export function confirmBox(text, onOk, okText = "确定") {
  openModal({
    title: "确认操作",
    content: `<p>${text}</p>`,
    footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">取消</button>
             <button class="btn danger" id="cf-ok">${okText}</button>`,
    onMount(modal) { modal.querySelector("#cf-ok").onclick = onOk; },
  });
}

export function particles() {
  const wrap = document.createElement("div");
  wrap.className = "particles";
  const colors = ["#2E8B84", "#4FA8A0", "#00E676", "#F59E0B"];
  for (let i = 0; i < 24; i++) {
    const s = document.createElement("span");
    s.style.left = "50%"; s.style.top = "40%";
    s.style.background = colors[i % colors.length];
    const a = (Math.PI * 2 * i) / 24 + Math.random() * 0.4;
    const d = 80 + Math.random() * 130;
    s.style.setProperty("--dx", `${Math.cos(a) * d}px`);
    s.style.setProperty("--dy", `${Math.sin(a) * d}px`);
    wrap.appendChild(s);
  }
  document.body.appendChild(wrap);
  setTimeout(() => wrap.remove(), 600);
}

export function fmtNum(n) {
  if (n === null || n === undefined || n === "") return "-";
  return Number(n).toLocaleString("zh-CN");
}
export function fmtDate(s) {
  if (!s) return "-";
  return String(s).slice(0, 10);
}
export function fmtTime(s) {
  if (!s) return "";
  return String(s).slice(5, 16).replace("T", " ");
}
export function avatarHtml(name, avatar, cls = "") {
  const c = cls ? ` ${cls}` : "";
  const ch = (name || "?").charAt(0);
  if (avatar) {
    const src = avatar.startsWith("/") || avatar.startsWith("http") || avatar.startsWith("data:") ? avatar : `/uploads/${avatar}`;
    return `<img class="avatar${c}" src="${src}" alt="${ch}">`;
  }
  return `<div class="avatar${c}">${ch}</div>`;
}
export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
export const isTimed = (name) => /支撑|静蹲|静态保持/.test(name || "");
export const localDate = (d = new Date()) =>
  new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

/* ---------------- 应用状态 ---------------- */
let currentUser = null;

export function me() { return currentUser; }
export function setMe(u) { currentUser = u; }

const NAV = {
  student: [
    ["checkin", "✅", "康复日志"], ["cases", "🗂️", "我的康复档案"], ["assess", "📈", "康复评估"],
    ["plans", "📋", "康复方案"], ["appointments", "📅", "预约与疗程"], ["camps", "🏕️", "康复营"], ["exercises", "🧘", "康复动作库"],
    ["tcm", "🩺", "中医体质"], ["body", "⚖️", "康复指标"], ["community", "🌐", "社区动态"],
    ["resources", "🔗", "康复资源"], ["achievements", "🏅", "康复里程碑"], ["content", "📖", "会员内容"],
    ["member", "⭐", "会员中心"], ["messages", "💬", "消息"], ["profile", "👤", "我的"],
  ],
  coach: [
    ["students", "👥", "患者管理"], ["cases", "🗂️", "康复档案"], ["assess", "📈", "康复评估"],
    ["plans", "📋", "方案制定"], ["alerts", "🔔", "待办预警"], ["schedule", "🗓️", "排班预约"],
    ["camps", "🏕️", "康复营"], ["guide", "🧭", "线上指导"],
    ["community", "🌐", "社区动态"], ["earnings", "💰", "我的收益"], ["batch", "📣", "消息推送"],
    ["messages", "💬", "聊天"], ["profile", "👤", "我的"],
  ],
  admin: [
    ["dashboard", "📊", "统计看板"], ["revenue", "💰", "营收看板"], ["users", "👤", "用户管理"], ["coachreview", "🧑‍⚕️", "治疗师审核"],
    ["withdrawals", "🏦", "提现审核"], ["announcements", "📢", "公告管理"], ["plans", "⭐", "方案推荐"],
    ["configs", "⚙️", "系统配置"], ["logs", "📝", "操作日志"],
  ],
};

const DEFAULT_VIEW = { student: "checkin", coach: "students", admin: "dashboard" };

const ROLE_LABEL = { student: "患者", coach: "康复治疗师", admin: "管理员" };

function renderLayout() {
  const app = document.getElementById("app");
  const navs = NAV[currentUser.role].map(([id, icon, txt]) =>
    `<a href="#/${id}" data-view="${id}"><span class="icon">${icon}</span><span class="txt">${txt}</span><span class="badge" style="display:none"></span></a>`
  ).join("");
  app.innerHTML = `
    <div class="layout">
      <aside class="sidebar">
        <div class="logo"><span class="dot"></span><span>康衡康复</span></div>
        <nav>${navs}</nav>
        <div class="user-box">
          ${avatarHtml(currentUser.nickname, currentUser.avatar)}
          <div class="info">
            <div class="name">${escapeHtml(currentUser.nickname)} ${currentUser.is_member ? '<span class="tag purple" style="margin-left:4px;font-size:10px">⭐ 会员</span>' : ''}</div>
            <div class="role">${ROLE_LABEL[currentUser.role]}${currentUser.member_until ? ` · 到期${currentUser.member_until}` : ""}</div>
          </div>
          <button class="btn ghost sm" id="btn-logout" title="退出登录" aria-label="退出登录">⎋</button>
        </div>
      </aside>
      <main class="main">
        <div class="topbar">
          <h2 id="page-title"></h2>
          <div class="actions" id="topbar-actions"></div>
        </div>
        <div class="view" id="view"></div>
      </main>
    </div>`;
  document.getElementById("btn-logout").onclick = () => {
    clearAuth();
    destroyChat();
    location.hash = "#/login";
  };
}

const VIEWS = { student: {}, coach: {}, admin: {} };
export function registerViews(role, views) { Object.assign(VIEWS[role], views); }

async function route() {
  const hash = location.hash || "#/";
  if (hash.startsWith("#/login") || !getToken()) { renderLogin(); return; }

  let user = getCachedUser();
  if (!user) { renderLogin(); return; }
  if (!currentUser) {
    try {
      currentUser = await api("/api/auth/me");
      currentUser.role = user.role;
    } catch {
      renderLogin(); return;
    }
  }

  const view = (hash.replace("#/", "") || DEFAULT_VIEW[currentUser.role] || "dashboard").split("?")[0];
  if (!NAV[currentUser.role].some((n) => n[0] === view)) {
    location.hash = "#/" + (DEFAULT_VIEW[currentUser.role] || "dashboard");
    return;
  }
  if (!document.querySelector(".layout")) renderLayout();

  document.querySelectorAll(".sidebar nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.view === view);
  });
  const navItem = NAV[currentUser.role].find((n) => n[0] === view);
  document.getElementById("page-title").textContent = navItem ? navItem[2] : "";
  document.getElementById("topbar-actions").innerHTML = "";

  const container = document.getElementById("view");
  const handler = (VIEWS[currentUser.role] || {})[view];
  destroyChat();
  if (handler) {
    try {
      await handler(container);
    } catch (err) {
      container.innerHTML = `<div class="card"><div class="empty"><span class="ico">⚠️</span>${escapeHtml(err.message)}</div></div>`;
    }
  } else {
    container.innerHTML = `<div class="empty">功能开发中</div>`;
  }
}

/* ---------------- 登录/注册 ---------------- */
function renderLogin(mode = "login") {
  const app = document.getElementById("app");
  app.innerHTML = `
    <div class="auth-wrap">
      <div class="auth-bg">
        <div class="orb o1"></div><div class="orb o2"></div><div class="orb o3"></div>
        <span class="fi f1">🧘</span><span class="fi f2">🩺</span><span class="fi f3">📈</span>
        <span class="fi f4">🦴</span><span class="fi f5">🌿</span><span class="fi f6">🏃</span>
      </div>
      <div class="auth-left">
        <div class="brand">
          <div class="brand-icon">🌿</div>
          <div class="brand-name">康 衡</div>
        </div>
        <h1 class="hero-title">康复中心<br>全周期管理系统</h1>
        <p class="hero-sub">专业评估 · 个体方案 · 全程康复</p>
        <ul class="hero-feats">
          <li><span class="fico">📈</span><div><b>康复评估</b><small>VAS疼痛 · 关节活动度ROM · 肌力MMT · 平衡与步态</small></div></li>
          <li><span class="fico">🗂️</span><div><b>康复档案</b><small>骨科术后 · 运动损伤 · 慢性疼痛 · 分阶段管理</small></div></li>
          <li><span class="fico">🩺</span><div><b>中医体质</b><small>九种体质辨识 · 体质化康复建议</small></div></li>
          <li><span class="fico">💬</span><div><b>医患协同</b><small>治疗师指导 · 康复日志 · 社区互助</small></div></li>
        </ul>
        <div class="hero-stats">
          <div><b>89</b><span>康复动作</span></div>
          <div><b>3</b><span>角色协同</span></div>
          <div><b>全周期</b><span>康复管理</span></div>
        </div>
      </div>
      <div class="auth-card">
        <div class="auth-logo">
          <div class="icon">🌿</div>
          <h1>康 衡 康 复</h1>
          <p>康复中心 · 全周期管理</p>
        </div>
        <div class="auth-tabs">
          <div class="tab ${mode === "login" ? "active" : ""}" data-m="login">登录</div>
          <div class="tab ${mode === "register" ? "active" : ""}" data-m="register">注册</div>
        </div>
        <form id="auth-form">
          <div class="field"><label>用户名</label><input name="username" required minlength="3" maxlength="50" autocomplete="username"></div>
          <div class="field"><label>密码</label><input name="password" type="password" required minlength="6" autocomplete="current-password"></div>
          <div class="field" id="reg-extra" style="display:${mode === "register" ? "block" : "none"}">
            <div class="field"><label>昵称</label><input name="nickname" maxlength="50"></div>
            <div class="field"><label>手机号</label><input name="phone" maxlength="20"></div>
            <div class="field"><label>注册身份</label>
              <select name="role">
                <option value="student">患者</option>
                <option value="coach">康复治疗师（需管理员审核）</option>
              </select>
            </div>
          </div>
          <button class="btn" style="width:100%" type="submit">${mode === "login" ? "登录" : "注册"}</button>
        </form>
        <div class="auth-demo">
          <b>演示账号（点击自动填充）</b>
          <div class="row" data-u="admin" data-p="Admin@123"><span>管理员</span><span>admin / Admin@123</span></div>
          <div class="row" data-u="coach_li" data-p="Coach@123"><span>康复治疗师</span><span>coach_li / Coach@123</span></div>
          <div class="row" data-u="student_wx" data-p="Student@123"><span>患者</span><span>student_wx / Student@123</span></div>
        </div>
      </div>
    </div>`;
  document.querySelectorAll(".auth-tabs .tab").forEach((t) => {
    t.onclick = () => renderLogin(t.dataset.m);
  });
  const form = document.getElementById("auth-form");
  form.onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const payload = Object.fromEntries(fd.entries());
    try {
      if (mode === "login") {
        const res = await api("/api/auth/login", { method: "POST", body: payload });
        setAuth(res.token, res.user);
        location.hash = "#/" + (DEFAULT_VIEW[res.user.role] || "dashboard");
      } else {
        if (!payload.nickname) payload.nickname = payload.username;
        const res = await api("/api/auth/register", { method: "POST", body: payload });
        setAuth(res.token, res.user);
        location.hash = "#/" + (DEFAULT_VIEW[res.user.role] || "dashboard");
        toast("注册成功，已自动登录", "success");
      }
      currentUser = null;
      route();
    } catch (err) {
      toast(err.message, "error");
    }
  };
  document.querySelectorAll(".auth-demo .row").forEach((r) => {
    r.onclick = () => {
      form.username.value = r.dataset.u;
      form.password.value = r.dataset.p;
    };
  });
}

/* ---------------- WebSocket ---------------- */
let ws = null;
function connectWS() {
  if (!getToken()) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${getToken()}`);
  ws.addEventListener("message", (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "notification" || data.type === "message" || data.type === "checkin") {
        toast(data.message || "收到新消息", "info");
      }
    } catch {}
  });
  ws.addEventListener("close", () => {
    if (getToken()) setTimeout(connectWS, 5000);
  });
}
export function getWS() { return ws; }

export function updateAvatar(avatar) {
  if (currentUser) currentUser.avatar = avatar;
  const cached = getCachedUser();
  if (cached) {
    cached.avatar = avatar;
    setAuth(getToken(), cached);
  }
  const old = document.querySelector(".sidebar .user-box .avatar");
  if (old && currentUser) old.outerHTML = avatarHtml(currentUser.nickname, avatar);
}

/* ---------------- 启动 ---------------- */
initStudent();
initCoach();
initAdmin();
initCamp();
initChat();

window.addEventListener("hashchange", route);
route();
connectWS();
