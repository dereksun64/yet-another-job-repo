const state = {
  payload: null,
  jobs: [],
  completed: new Set(JSON.parse(localStorage.getItem("completedJobs") || "[]")),
};

const els = {
  meta: document.querySelector("#meta"),
  refreshButton: document.querySelector("#refreshButton"),
  searchInput: document.querySelector("#searchInput"),
  typeFilter: document.querySelector("#typeFilter"),
  hideAdvancedDegrees: document.querySelector("#hideAdvancedDegrees"),
  hideCompleted: document.querySelector("#hideCompleted"),
  listedCompaniesOnly: document.querySelector("#listedCompaniesOnly"),
  tierFilter: document.querySelector("#tierFilter"),
  sortSelect: document.querySelector("#sortSelect"),
  summary: document.querySelector("#summary"),
  jobs: document.querySelector("#jobs"),
};

const tierRank = {
  "Tier 1": 1,
  "Tier 1.5": 1.5,
  "Tier 2": 2,
  "Tier 3": 3,
  "Tier 4": 4,
  Unlisted: 99,
};

const californiaTerms = [
  "ca",
  "california",
  "sf",
  "san francisco",
  "bay area",
  "mountain view",
  "sunnyvale",
  "palo alto",
  "menlo park",
  "san jose",
  "santa clara",
  "cupertino",
  "redwood city",
  "los angeles",
  "la",
  "irvine",
  "san diego",
  "sacramento",
];

function ageDays(age) {
  const value = String(age || "").trim();
  const relative = value.match(/^(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|mo)$/i);
  if (relative) {
    const amount = Number(relative[1]);
    const unit = relative[2].toLowerCase();
    if (unit.startsWith("m") && unit !== "mo") return amount / 1440;
    if (unit.startsWith("h")) return amount / 24;
    return amount * (unit === "mo" ? 30 : 1);
  }
  if (!value) return 9999;

  const now = new Date();
  const date = new Date(`${value} ${now.getFullYear()}`);
  if (Number.isNaN(date.getTime())) return 9999;
  if (date > now) date.setFullYear(date.getFullYear() - 1);
  return Math.max(0, (now - date) / 86400000);
}

function formatAge(age) {
  const value = String(age || "").trim();
  const relative = value.match(/^(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|mo)$/i);
  if (!relative) return value;

  const amount = Number(relative[1]);
  const unit = relative[2].toLowerCase();
  if (unit.startsWith("m") && unit !== "mo") return `${amount}m`;
  if (unit.startsWith("h")) return `${amount}h`;
  if (unit === "mo") return `${amount}mo`;
  return amount === 0 ? "<24h" : `${amount}d`;
}

function locationSearchText(location) {
  const value = String(location || "").toLowerCase();
  const matchesCalifornia = californiaTerms.some((term) => {
    if (term.length <= 2) return new RegExp(`(^|[^a-z])${term}([^a-z]|$)`).test(value);
    return value.includes(term);
  });
  return matchesCalifornia ? `${value} ${californiaTerms.join(" ")}` : value;
}

function includesSearchTerm(value, query) {
  if (query.length <= 2) return new RegExp(`(^|[^a-z0-9])${query}([^a-z0-9]|$)`).test(value);
  return value.includes(query);
}

function matches(job) {
  const query = els.searchInput.value.trim().toLowerCase();
  const locationHaystack = locationSearchText(job.location);
  const haystack = [job.company, job.title, locationSearchText(job.location), job.category].join(" ").toLowerCase();
  return (
    (!query || includesSearchTerm(californiaTerms.includes(query) ? locationHaystack : haystack, query)) &&
    (!els.typeFilter.value || job.jobType === els.typeFilter.value) &&
    (!els.hideAdvancedDegrees.checked || !["masters", "phd"].includes(job.degreeLevel)) &&
    (!els.hideCompleted.checked || !state.completed.has(job.id)) &&
    (!els.listedCompaniesOnly.checked || job.companyTier !== "Unlisted") &&
    (!els.tierFilter.value || job.companyTier === els.tierFilter.value)
  );
}

function sortJobs(jobs) {
  const mode = els.sortSelect.value;
  return [...jobs].sort((a, b) => {
    if (mode === "age") return ageDays(a.age) - ageDays(b.age);
    if (mode === "company") return a.company.localeCompare(b.company);
    if (mode === "location") return a.location.localeCompare(b.location);
    return (tierRank[a.companyTier] || 99) - (tierRank[b.companyTier] || 99) || a.company.localeCompare(b.company);
  });
}

function render() {
  const jobs = sortJobs(state.jobs.filter(matches));
  els.summary.textContent = `${jobs.length.toLocaleString()} of ${state.jobs.length.toLocaleString()} jobs shown`;
  els.jobs.innerHTML = jobs
    .map(
      (job) => {
        const completed = state.completed.has(job.id);
        return `
        <article class="job${completed ? " completed" : ""}">
          <div class="jobHeader">
            <div>
              <h2>${escapeHtml(job.title)}</h2>
              <div class="company">${escapeHtml(job.company)} · ${escapeHtml(job.location || "Location unknown")}</div>
            </div>
            <div class="jobActions">
              <label class="completeControl">
                <input class="completeInput" type="checkbox" data-job-id="${escapeAttribute(job.id)}" ${completed ? "checked" : ""}>
                Done
              </label>
              <a class="apply" href="${escapeAttribute(job.applyUrl)}" target="_blank" rel="noreferrer">Apply</a>
            </div>
          </div>
          <div class="tags">
            <span class="tag">${escapeHtml(job.companyTier)}</span>
            <span class="tag">${escapeHtml(job.jobType)}</span>
            <span class="tag">${escapeHtml(job.degreeLevel)}</span>
            <span class="tag">${escapeHtml(job.category)}</span>
            <span class="tag">${job.sourceUrl
              ? `<a class="source" href="${escapeAttribute(job.sourceUrl)}" target="_blank" rel="noreferrer">${escapeHtml(job.source)}</a>`
              : escapeHtml(job.source)}</span>
            ${job.age ? `<span class="tag">${escapeHtml(formatAge(job.age))}</span>` : ""}
          </div>
        </article>
      `;
      }
    )
    .join("");
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

async function loadJobs() {
  els.meta.textContent = "Loading jobs...";
  const response = await fetch(`../data/jobs.json?ts=${Date.now()}`);
  if (!response.ok) throw new Error(`Failed to load jobs: ${response.status}`);
  state.payload = await response.json();
  state.jobs = state.payload.jobs || [];
  els.meta.textContent = `Generated ${new Date(state.payload.generatedAt).toLocaleString()}`;
  render();
}

for (const el of [els.searchInput, els.typeFilter, els.hideAdvancedDegrees, els.hideCompleted, els.listedCompaniesOnly, els.tierFilter, els.sortSelect]) {
  el.addEventListener("input", render);
}

els.jobs.addEventListener("change", (event) => {
  if (!event.target.matches(".completeInput")) return;
  const id = event.target.dataset.jobId;
  if (event.target.checked) state.completed.add(id);
  else state.completed.delete(id);
  localStorage.setItem("completedJobs", JSON.stringify([...state.completed]));
  render();
});

els.refreshButton.addEventListener("click", () => {
  loadJobs().catch((error) => {
    els.meta.textContent = error.message;
  });
});

loadJobs().catch((error) => {
  els.meta.textContent = error.message;
});
