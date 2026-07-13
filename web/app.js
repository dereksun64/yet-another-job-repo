const state = {
  payload: null,
  jobs: [],
};

const els = {
  meta: document.querySelector("#meta"),
  refreshButton: document.querySelector("#refreshButton"),
  searchInput: document.querySelector("#searchInput"),
  typeFilter: document.querySelector("#typeFilter"),
  degreeFilter: document.querySelector("#degreeFilter"),
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

function ageDays(age) {
  const value = String(age || "").trim();
  const relative = value.match(/^(\d+)\s*(d|mo)$/i);
  if (relative) return Number(relative[1]) * (relative[2].toLowerCase() === "mo" ? 30 : 1);
  if (!value) return 9999;

  const now = new Date();
  const date = new Date(`${value} ${now.getFullYear()}`);
  if (Number.isNaN(date.getTime())) return 9999;
  if (date > now) date.setFullYear(date.getFullYear() - 1);
  return Math.max(0, (now - date) / 86400000);
}

function matches(job) {
  const query = els.searchInput.value.trim().toLowerCase();
  const haystack = [job.company, job.title, job.location, job.category].join(" ").toLowerCase();
  return (
    (!query || haystack.includes(query)) &&
    (!els.typeFilter.value || job.jobType === els.typeFilter.value) &&
    (!els.degreeFilter.value || job.degreeLevel === els.degreeFilter.value) &&
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
      (job) => `
        <article class="job">
          <div class="jobHeader">
            <div>
              <h2>${escapeHtml(job.title)}</h2>
              <div class="company">${escapeHtml(job.company)} · ${escapeHtml(job.location || "Location unknown")}</div>
            </div>
            <a class="apply" href="${escapeAttribute(job.applyUrl)}" target="_blank" rel="noreferrer">Apply</a>
          </div>
          <div class="tags">
            <span class="tag">${escapeHtml(job.companyTier)}</span>
            <span class="tag">${escapeHtml(job.jobType)}</span>
            <span class="tag">${escapeHtml(job.degreeLevel)}</span>
            <span class="tag">${escapeHtml(job.category)}</span>
            <span class="tag">${job.sourceUrl
              ? `<a class="source" href="${escapeAttribute(job.sourceUrl)}" target="_blank" rel="noreferrer">${escapeHtml(job.source)}</a>`
              : escapeHtml(job.source)}</span>
            ${job.age ? `<span class="tag">${escapeHtml(job.age)}</span>` : ""}
          </div>
        </article>
      `
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

for (const el of [els.searchInput, els.typeFilter, els.degreeFilter, els.tierFilter, els.sortSelect]) {
  el.addEventListener("input", render);
}

els.refreshButton.addEventListener("click", () => {
  loadJobs().catch((error) => {
    els.meta.textContent = error.message;
  });
});

loadJobs().catch((error) => {
  els.meta.textContent = error.message;
});
