const state = { kind: "all", rink: "all", payload: null };
const schedule = document.querySelector("#schedule");

const fmtTime = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" });
const fmtDay = new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric" });

function fmtRange(startValue, endValue) {
  let start = fmtTime.format(new Date(startValue));
  const end = fmtTime.format(new Date(endValue));
  const startPeriod = start.match(/ (AM|PM)$/)?.[1];
  const endPeriod = end.match(/ (AM|PM)$/)?.[1];
  if (startPeriod === endPeriod) start = start.replace(/ (AM|PM)$/, "");
  return `${start}–${end}`;
}

function escapeHtml(value = "") {
  return value.replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
}

function visibleEvents() {
  const now = new Date();
  return state.payload.events.filter(event => new Date(event.end) >= now && (state.kind === "all" || event.kind === state.kind) && (state.rink === "all" || event.rink === state.rink));
}

function render() {
  const events = visibleEvents();
  if (!events.length) {
    schedule.innerHTML = '<p class="empty">No matching ice time is currently published.</p>';
    return;
  }
  const days = events.reduce((groups, event) => {
    const key = event.start.slice(0, 10);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(event);
    return groups;
  }, new Map());
  schedule.innerHTML = [...days.values()].map(items => {
    const day = new Date(items[0].start);
    const cards = items.map(event => `<a class="event" href="${escapeHtml(event.source_url)}" target="_blank" rel="noopener">
      <div class="time">${fmtRange(event.start, event.end)}</div>
      <h3>${escapeHtml(event.rink)}</h3>
      <span class="badge ${event.kind}">${event.kind === "public_skate" ? "Public skate" : "Stick + puck"}</span>
    </a>`).join("");
    return `<section class="day"><h2>${fmtDay.format(day)}</h2><div class="event-list">${cards}</div></section>`;
  }).join("");
}

function icsDate(value) { return new Date(value).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, ""); }
function icsEscape(value) { return value.replace(/([,;\\])/g, "\\$1").replace(/\n/g, "\\n"); }
function downloadCalendar() {
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Local Ice//Mass Skate Calendar//EN"];
  visibleEvents().forEach(event => lines.push("BEGIN:VEVENT", `UID:${event.id}@mass-skate-calendar`, `DTSTAMP:${icsDate(state.payload.generated_at || new Date())}`, `DTSTART:${icsDate(event.start)}`, `DTEND:${icsDate(event.end)}`, `SUMMARY:${icsEscape(event.kind === "public_skate" ? "Public Skate" : "Stick + Puck")} — ${icsEscape(event.rink)}`, `LOCATION:${icsEscape(event.address)}`, `URL:${event.source_url}`, "END:VEVENT"));
  lines.push("END:VCALENDAR");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([lines.join("\r\n")], { type: "text/calendar" }));
  link.download = "local-ice.ics";
  link.click();
  URL.revokeObjectURL(link.href);
}

fetch("data/events.json", { cache: "no-store" }).then(response => {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}).then(payload => {
  state.payload = payload;
  const rinkFilter = document.querySelector("#rink-filter");
  [...new Set(payload.sources.map(source => source.rink))].sort().forEach(rink => rinkFilter.add(new Option(rink, rink)));
  const generated = payload.generated_at ? new Date(payload.generated_at) : null;
  document.querySelector("#freshness").textContent = generated ? `Updated ${generated.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}` : "Awaiting first scrape";
  const failures = payload.sources.filter(source => !source.ok);
  if (failures.length) {
    const warning = document.querySelector("#source-warning");
    warning.hidden = false;
    warning.textContent = `Could not refresh: ${failures.map(source => source.rink).join(", ")}. ${failures.some(source => source.stale) ? "Previously collected times are shown." : ""}`;
  }
  render();
}).catch(error => { schedule.innerHTML = `<p class="empty">Schedule unavailable: ${escapeHtml(error.message)}</p>`; });

document.querySelectorAll("[data-kind]").forEach(button => button.addEventListener("click", () => {
  state.kind = button.dataset.kind;
  document.querySelectorAll("[data-kind]").forEach(item => item.classList.toggle("active", item === button));
  render();
}));
document.querySelector("#rink-filter").addEventListener("change", event => { state.rink = event.target.value; render(); });
document.querySelector("#download-ics").addEventListener("click", downloadCalendar);
