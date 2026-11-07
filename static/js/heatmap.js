import { api } from "./api.js";
import { localDate } from "./app.js";

const WEEK = ["一", "二", "三", "四", "五", "六", "日"];

export async function renderHeatmap(container, userId, year, month, onPick) {
  const data = await api(`/api/student/checkins?year=${year}&month=${month}`);
  const map = {};
  data.days.forEach((d) => (map[d.date] = d));

  const first = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const lead = (first.getDay() + 6) % 7;
  const todayStr = localDate();
  const todayDate = new Date(todayStr);

  let cells = WEEK.map((w) => `<div class="hd">${w}</div>`).join("");
  for (let i = 0; i < lead; i++) cells += `<div class="cell empty"></div>`;
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const rec = map[ds];
    const isPast = new Date(ds) < todayDate;
    const isToday = ds === todayStr;
    let cls = "cell";
    if (rec) cls += rec.intensity >= 4 ? " h3" : rec.intensity >= 2 ? " h2" : " h1";
    if (isToday) cls += " today";
    if (!rec && isPast) cls += " missed";
    const inner = rec
      ? `<span class="day-num">${d}</span><span class="day-vol">${rec.duration}分</span>${rec.is_makeup ? '<span class="day-tag">补</span>' : ""}`
      : `<span class="day-num">${d}</span>${isPast ? '<span class="day-miss">未康复日志</span>' : ""}`;
    cells += `<div class="${cls}" data-date="${ds}" role="button" tabindex="0"><div class="cell-inner">${inner}</div></div>`;
  }

  container.innerHTML = `
    <div class="flex between mb-16">
      <div class="flex">
        <button class="btn ghost sm" id="hm-prev">‹ 上月</button>
        <b style="font-family:var(--mono)">${year} 年 ${month} 月</b>
        <button class="btn ghost sm" id="hm-next">下月 ›</button>
      </div>
      <div class="flex" style="gap:8px">
        <span class="tag green">康复日志 ${data.checkin_days} 天</span>
        <span class="tag">康复时长 ${data.total_duration} 分钟</span>
      </div>
    </div>
    <div class="heatmap">${cells}</div>
    <div class="heat-legend">
      <span>少</span>
      <span class="sw" style="background:var(--heat-0)"></span>
      <span class="sw" style="background:var(--heat-1)"></span>
      <span class="sw" style="background:var(--heat-2)"></span>
      <span class="sw" style="background:var(--heat-3)"></span>
      <span>多</span>
      <span style="margin-left:10px;color:var(--text-2)">点击日期查看详情</span>
    </div>`;

  container.querySelector("#hm-prev").onclick = () => {
    const m = month === 1 ? 12 : month - 1;
    const y = month === 1 ? year - 1 : year;
    renderHeatmap(container, userId, y, m, onPick);
  };
  container.querySelector("#hm-next").onclick = () => {
    const m = month === 12 ? 1 : month + 1;
    const y = month === 12 ? year + 1 : year;
    renderHeatmap(container, userId, y, m, onPick);
  };
  container.querySelectorAll(".cell[data-date]").forEach((c) => {
    c.onclick = () => { if (onPick) onPick(c.dataset.date); };
  });
}
