import { api, uploadFile } from "./api.js";
import { toast, openModal, closeModal, confirmBox, escapeHtml, fmtTime, avatarHtml, me } from "./app.js";

const VIS_ICON = { public: "🌐", coach: "🧑‍🏫", private: "🔒" };
let scope = "feed";

export async function viewCommunity(el) {
  const user = me();
  let page = 1;

  el.innerHTML = `
    <div class="card mb-16" id="composer">
      <div class="flex mb-16" style="gap:12px">
        ${avatarHtml(user.nickname, user.avatar)}
        <div style="flex:1">
          <div style="font-weight:600">${escapeHtml(user.nickname)}</div>
          <div style="color:var(--text-2);font-size:12px">分享你的训练日常，让坚持被看见</div>
        </div>
      </div>
      <textarea id="post-content" maxlength="2000" placeholder="今天练了什么？有什么进步和心得…" style="min-height:80px"></textarea>
      <div class="flex between wrap mt-16">
        <div class="flex wrap">
          <label class="btn ghost sm" style="cursor:pointer">🖼️ 添加图片
            <input type="file" id="post-images" accept="image/jpeg,image/png,image/gif,image/webp" multiple style="display:none">
          </label>
          <div class="flex" id="post-img-tags" style="gap:6px"></div>
        </div>
        <div class="flex">
          <select id="post-vis" style="width:auto">
            <option value="public">🌐 公开 · 所有人可见</option>
            <option value="coach">🧑‍🏫 仅康复治疗师可见</option>
            <option value="private">🔒 仅自己可见</option>
          </select>
          <button class="btn" id="post-submit">发布动态</button>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="filter-bar">
        <button class="btn ghost sm" data-scope="feed">全部动态</button>
        <button class="btn ghost sm" data-scope="mine">我的动态</button>
        <span style="flex:1"></span>
        <span id="feed-total" style="color:var(--text-2);font-size:13px"></span>
      </div>
      <div id="feed" class="feed"></div>
      <div style="text-align:center;margin-top:12px">
        <button class="btn ghost sm" id="feed-more" style="display:none">加载更多</button>
      </div>
    </div>`;

  const images = [];
  el.querySelector("#post-images").onchange = async (e) => {
    for (const file of e.target.files) {
      if (images.length >= 3) return toast("最多上传 3 张图片", "warn");
      try {
        const up = await uploadFile(file, "image");
        images.push(up.path);
        el.querySelector("#post-img-tags").insertAdjacentHTML("beforeend",
          `<span class="tag green">🖼️ 已传 ${images.length}</span>`);
      } catch (err) { toast(err.message, "error"); }
    }
    e.target.value = "";
  };

  el.querySelector("#post-submit").onclick = async () => {
    const content = el.querySelector("#post-content").value.trim();
    if (!content) return toast("请输入动态内容", "warn");
    try {
      await api("/api/community/posts", {
        method: "POST",
        body: { content, media_paths: images, visibility: el.querySelector("#post-vis").value },
      });
      toast("动态已发布", "success");
      el.querySelector("#post-content").value = "";
      images.length = 0;
      el.querySelector("#post-img-tags").innerHTML = "";
      scope = "feed";
      page = 1;
      load(true);
    } catch (err) { toast(err.message, "error"); }
  };

  el.querySelectorAll("[data-scope]").forEach((b) => {
    b.onclick = () => {
      scope = b.dataset.scope;
      page = 1;
      load(true);
    };
  });

  function postCard(p) {
    const mine = p.user_id === user.id || user.role === "admin";
    return `
    <div class="feed-item card" data-post="${p.id}">
      <div class="head">
        ${avatarHtml(p.nickname, p.avatar)}
        <div>
          <b>${escapeHtml(p.nickname)}</b>
          <span class="tag sm ${p.author_role === "coach" ? "purple" : p.author_role === "admin" ? "red" : "gray"}" style="font-size:11px">${{ student: "患者", coach: "康复治疗师", admin: "管理员" }[p.author_role] || ""}</span>
          <div style="color:var(--text-2);font-size:12px">${fmtTime(p.created_at)} · ${VIS_ICON[p.visibility]} ${p.visibility_label}</div>
        </div>
        <span style="flex:1"></span>
        ${mine ? `<button class="pi-del" data-del-post="${p.id}" title="删除动态">×</button>` : ""}
      </div>
      <div style="font-size:14px;line-height:1.7;white-space:pre-wrap">${escapeHtml(p.content)}</div>
      ${p.media_paths.length ? `<div class="media">${p.media_paths.map((m) =>
        `<img src="/uploads/${m}" data-img="${m}" alt="动态图片">`).join("")}</div>` : ""}
      <div class="flex mt-16" style="gap:14px">
        <button class="btn ghost sm ${p.liked ? "liked" : ""}" data-like="${p.id}">
          ${p.liked ? "❤️" : "🤍"} <span data-like-cnt="${p.id}">${p.like_count}</span> 点赞
        </button>
        <button class="btn ghost sm" data-cmt="${p.id}">💬 <span>${p.comment_count}</span> 评论</button>
      </div>
      <div class="cmt-box" id="cmt-${p.id}" style="display:none;margin-top:10px">
        <div class="cmt-list" data-cmt-list="${p.id}"></div>
        <div class="flex mt-16">
          <input class="cmt-input" data-cmt-input="${p.id}" placeholder="友善评论，给 TA 加个油…" maxlength="1000" style="flex:1">
          <button class="btn sm" data-cmt-send="${p.id}">发送</button>
        </div>
      </div>
    </div>`;
  }

  async function load(reset) {
    try {
      const res = await api(`/api/community/posts?scope=${scope}&page=${page}&page_size=10`);
      el.querySelector("#feed-total").textContent = `共 ${res.total} 条`;
      const feed = el.querySelector("#feed");
      const html = res.items.map(postCard).join("");
      if (reset) feed.innerHTML = html;
      else feed.insertAdjacentHTML("beforeend", html);
      el.querySelector("#feed-more").style.display =
        page * res.page_size < res.total ? "" : "none";
      bindFeed();
    } catch (err) {
      el.querySelector("#feed").innerHTML =
        `<div class="empty"><span class="ico">⚠️</span>${escapeHtml(err.message)}</div>`;
    }
  }

  function bindFeed() {
    el.querySelectorAll("[data-del-post]").forEach((b) => {
      b.onclick = () => confirmBox("确定删除这条动态？", async () => {
        await api(`/api/community/posts/${b.dataset.delPost}`, { method: "DELETE" });
        closeModal(); toast("已删除", "success"); page = 1; load(true);
      });
    });
    el.querySelectorAll("[data-like]").forEach((b) => {
      b.onclick = async () => {
        try {
          const r = await api(`/api/community/posts/${b.dataset.like}/like`, { method: "POST" });
          b.innerHTML = `${r.liked ? "❤️" : "🤍"} <span data-like-cnt="${b.dataset.like}">${r.like_count}</span> 点赞`;
          b.classList.toggle("liked", r.liked);
        } catch (err) { toast(err.message, "error"); }
      };
    });
    el.querySelectorAll("[data-img]").forEach((img) => {
      img.onclick = () => openModal({
        title: "查看图片",
        wide: true,
        content: `<img src="/uploads/${img.dataset.img}" style="width:100%;border-radius:8px" alt="">`,
        footer: `<button class="btn ghost" onclick="document.getElementById('modal-root').innerHTML=''">关闭</button>`,
      });
    });
    el.querySelectorAll("[data-cmt]").forEach((b) => {
      b.onclick = () => {
        const box = el.querySelector(`#cmt-${b.dataset.cmt}`);
        const show = box.style.display === "none";
        box.style.display = show ? "block" : "none";
        if (show) loadComments(b.dataset.cmt);
      };
    });
    el.querySelectorAll("[data-cmt-send]").forEach((b) => {
      b.onclick = async () => {
        const pid = b.dataset.cmtSend;
        const input = el.querySelector(`[data-cmt-input="${pid}"]`);
        const content = input.value.trim();
        if (!content) return toast("请输入评论内容", "warn");
        try {
          await api(`/api/community/posts/${pid}/comments`, { method: "POST", body: { content } });
          input.value = "";
          loadComments(pid);
          const cntBtn = el.querySelector(`[data-cmt="${pid}"]`);
          if (cntBtn) cntBtn.innerHTML = `💬 <span>${+cntBtn.querySelector("span").textContent + 1}</span> 评论`;
        } catch (err) { toast(err.message, "error"); }
      };
    });
  }

  async function loadComments(pid) {
    const box = el.querySelector(`[data-cmt-list="${pid}"]`);
    const comments = await api(`/api/community/posts/${pid}/comments`);
    box.innerHTML = comments.length ? comments.map((c) => `
      <div class="flex" style="border-bottom:1px dashed var(--border);padding:6px 0;gap:8px">
        <div style="font-size:13px;flex:1">
          <b style="color:var(--primary)">${escapeHtml(c.nickname)}</b>
          <span class="tag sm ${c.author_role === "coach" ? "purple" : "gray"}" style="font-size:10px">${{ student: "患者", coach: "康复治疗师", admin: "管理员" }[c.author_role] || ""}</span>
          ${escapeHtml(c.content)}
          <span style="color:var(--text-2);font-size:11px;margin-left:6px">${fmtTime(c.created_at)}</span>
        </div>
        ${c.user_id === user.id || user.role === "admin"
          ? `<button class="pi-del" data-del-cmt="${c.id}" data-pid="${pid}" style="font-size:14px">×</button>` : ""}
      </div>`).join("") : `<div class="empty" style="padding:10px;font-size:13px">还没有评论，来抢沙发～</div>`;
    box.querySelectorAll("[data-del-cmt]").forEach((b) => {
      b.onclick = async () => {
        await api(`/api/community/comments/${b.dataset.delCmt}`, { method: "DELETE" });
        loadComments(b.dataset.pid);
      };
    });
  }

  el.querySelector("#feed-more").onclick = () => { page++; load(false); };
  load(true);
}
