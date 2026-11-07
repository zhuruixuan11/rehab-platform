import { api, uploadFile } from "./api.js";
import { toast, escapeHtml, fmtTime, me, getWS, avatarHtml } from "./app.js";

let chatState = { peer: null };

export function initChat() {}

export function destroyChat() {
  chatState.peer = null;
}

function setupWSRefresh(renderMsgs) {
  const ws = getWS();
  if (ws) {
    ws.addEventListener("message", (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "message" && data.data && chatState.peer &&
            Number(data.data.sender_id) === Number(chatState.peer.id)) {
          renderMsgs([data.data], true);
        }
      } catch {}
    });
  }
}

export async function renderChat(container) {
  const user = me();
  const contacts = await api("/api/messages/contacts");
  const sysMsgs = await api("/api/messages/system");

  container.innerHTML = `
    <div class="chat-wrap">
      <div class="chat-contacts" id="chat-contacts">
        <div class="c-item" data-sys="1">
          <div class="avatar">🔔</div>
          <div class="meta"><div class="n">系统通知</div>
          <div class="m">${sysMsgs.length ? escapeHtml(sysMsgs[0].content).slice(0, 20) : "暂无通知"}</div></div>
        </div>
        ${contacts.map((c) => `
          <div class="c-item" data-id="${c.id}">
            ${avatarHtml(c.nickname, c.avatar)}
            <div class="meta">
              <div class="n">${escapeHtml(c.nickname)} ${c.unread ? `<span class="tag red sm" style="font-size:10px;padding:0 6px">${c.unread}</span>` : ""}</div>
              <div class="m">${escapeHtml(c.last_message || "开始对话")}</div>
            </div>
          </div>`).join("") || `<div class="empty" style="padding:20px">暂无联系人<br><small>患者与康复治疗师建立计划后可互发消息</small></div>`}
      </div>
      <div class="chat-panel" id="chat-panel">
        <div class="empty" style="margin:auto"><span class="ico">💬</span>选择左侧联系人开始聊天</div>
      </div>
    </div>`;

  const panel = container.querySelector("#chat-panel");

  function renderSysList() {
    panel.innerHTML = `
      <div class="head">系统通知</div>
      <div class="msgs" id="chat-msgs">
        ${sysMsgs.map((m) => `<div class="msg"><div class="avatar">SYS</div>
          <div class="bubble">${escapeHtml(m.content)}<div class="time">${fmtTime(m.created_at)}</div></div></div>`).join("") || `<div class="empty">暂无通知</div>`}
      </div>`;
  }

  async function openPeer(peerId) {
    const res = await api(`/api/messages/contacts/${peerId}`);
    chatState.peer = res.peer;
    panel.innerHTML = `
      <div class="head">${escapeHtml(res.peer.nickname)}</div>
      <div class="msgs" id="chat-msgs"></div>
      <div class="chat-input">
        <label class="btn ghost sm" style="cursor:pointer" title="发送图片">📎<input type="file" id="chat-file" accept="image/*,video/*" style="display:none"></label>
        <input type="text" id="chat-text" placeholder="输入消息，回车发送…" maxlength="500">
        <button class="btn" id="chat-send">发送</button>
      </div>`;

    const msgsBox = panel.querySelector("#chat-msgs");

    function renderMsgs(list, append = false) {
      const html = list.map((m) => {
        const mine = Number(m.sender_id) === Number(user.id);
        const sender = m.sender_nickname || "系统";
        let body = escapeHtml(m.content);
        if (m.msg_type === "image" && m.media_path) body = `<img src="/uploads/${m.media_path}" alt="图片消息">`;
        if (m.msg_type === "video" && m.media_path) body = `📹 视频消息`;
        return `<div class="msg ${mine ? "mine" : ""}">
          ${avatarHtml(sender, m.sender_avatar)}
          <div class="bubble">${body}<div class="time">${escapeHtml(sender)} · ${fmtTime(m.created_at)}</div></div>
        </div>`;
      }).join("");
      if (append) msgsBox.insertAdjacentHTML("beforeend", html);
      else msgsBox.innerHTML = html || `<div class="empty">暂无消息，打个招呼吧</div>`;
      msgsBox.scrollTop = msgsBox.scrollHeight;
    }

    renderMsgs(res.messages);
    setupWSRefresh(renderMsgs);

    async function send() {
      const input = panel.querySelector("#chat-text");
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      try {
        const msg = await api("/api/messages", { method: "POST", body: { receiver_id: peerId, msg_type: "text", content: text } });
        renderMsgs([{ ...msg, sender_nickname: user.nickname }], true);
      } catch (err) { toast(err.message, "error"); }
    }

    panel.querySelector("#chat-send").onclick = send;
    panel.querySelector("#chat-text").onkeydown = (e) => { if (e.key === "Enter") send(); };
    panel.querySelector("#chat-file").onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const kind = file.type.startsWith("video") ? "video" : "image";
        const up = await uploadFile(file, kind);
        const msg = await api("/api/messages", {
          method: "POST",
          body: { receiver_id: peerId, msg_type: kind, content: kind === "image" ? "[图片]" : "[视频]", media_path: up.path },
        });
        renderMsgs([{ ...msg, sender_nickname: user.nickname }], true);
      } catch (err) { toast(err.message, "error"); }
    };
  }

  container.querySelectorAll(".c-item").forEach((item) => {
    item.onclick = () => {
      container.querySelectorAll(".c-item").forEach((i) => i.classList.remove("active"));
      item.classList.add("active");
      if (item.dataset.sys) renderSysList();
      else openPeer(item.dataset.id);
    };
  });
}
