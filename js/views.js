import { showView } from "./navigation.js";
import { compareEntries, getCoverage, getTrend } from "./progress.js";
import { state } from "./state.js";
import { formatClass, formatFullDate, formatShortDate, formatTissueGroup, relativeDate } from "./utils.js";

export function renderAll() {
  setTodayLabel();
  renderDashboard();
  renderTimeline();
  renderProvider();
}

export function renderResult(entry) {
  const model = entry.modelAnalysis;
  const previous = state.entries[1];
  const comparison = previous ? compareEntries(entry, previous) : "This is the baseline image. Upload another photo later to calculate a visual progress signal.";
  const quality = model.photo_quality;
  const qualityText = quality.notes.length ? quality.notes.join(" ") : "Lighting and sharpness checks passed.";
  const [red, green, blue] = model.features.mean_wound_rgb;
  const tissue = model.tissue_color_analysis;
  document.querySelector("#result-content").innerHTML = `
    <div class="result-grid">
      <section class="panel">
        <div class="result-image-wrap">
          <img class="result-image" src="${entry.photo}" alt="Uploaded wound photo" />
          <img class="model-mask" src="${model.segmentation.mask_data_url}" alt="U-Net wound segmentation mask" />
          <span class="result-image-label">${formatFullDate(entry.date)}</span>
        </div>
        <div class="overlay-legend"><span><i></i> U-Net segmentation mask</span><small>Real model output</small></div>
      </section>
      <section class="panel assessment-card">
        <span class="assessment-status">Photo analysis complete</span>
        <h2>${previous ? getTrend(state.entries).title : "Baseline image analyzed"}</h2>
        <p>${comparison}</p>
        <div class="prototype-callout"><strong>Decision-support note:</strong> these are proof-of-concept image-analysis outputs, not a diagnosis or treatment recommendation.</div>
        <div class="analysis-metrics">
          <div><span>Wound coverage</span><strong>${model.segmentation.coverage_percent}%</strong><small>Of image frame</small></div>
          <div><span>Mask perimeter</span><strong>${model.segmentation.perimeter_pixels} px</strong><small>Boundary length</small></div>
          <div><span>Category estimate</span><strong>${formatClass(model.classification.label)}</strong><small>${Math.round(model.classification.confidence * 100)}% model confidence</small></div>
          <div><span>Shape circularity</span><strong>${model.features.shape_circularity}</strong><small>0 irregular · 1 circular</small></div>
        </div>
        <div class="insight-list">
          <div class="insight"><div class="insight-icon">01</div><div><strong>Photo quality</strong><span>${qualityText}</span></div></div>
          <div class="insight"><div class="insight-icon">02</div><div><strong>Mean segmented color</strong><span>RGB ${red}, ${green}, ${blue}</span></div></div>
          <div class="insight"><div class="insight-icon">03</div><div><strong>Measurement note</strong><span>Coverage is relative to the frame. Keep distance, lighting, and angle consistent between uploads.</span></div></div>
        </div>
        ${renderTissueComposition(tissue)}
        <div class="result-actions"><button class="primary-button" data-result-go="timeline">View progress timeline</button><button class="secondary-button" data-result-go="check-in">Add another photo</button></div>
      </section>
    </div>`;
  document.querySelectorAll("[data-result-go]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.resultGo)));
}

function renderDashboard() {
  const latest = state.entries[0];
  const empty = !latest;
  document.querySelector("#dashboard-empty").classList.toggle("hidden", !empty);
  document.querySelector("#dashboard-progress").classList.toggle("hidden", empty);
  if (!latest) return;
  const trend = getTrend(state.entries);
  document.querySelector("#last-checkin").textContent = relativeDate(latest.date);
  document.querySelector("#last-checkin-note").textContent = formatShortDate(latest.date);
  document.querySelector("#streak-count").textContent = `${state.entries.length} ${state.entries.length === 1 ? "check-in" : "check-ins"}`;
  document.querySelector("#timeline-badge").textContent = `${state.entries.length} journal ${state.entries.length === 1 ? "entry" : "entries"}`;
  document.querySelector("#trend-status").textContent = trend.title;
  document.querySelector("#trend-note").textContent = trend.note;
  document.querySelector("#next-step-copy").textContent = "Add another photo in 2 to 3 days using the same lighting, distance, and angle.";
  renderChart();
}

function renderChart() {
  const entries = [...state.entries].reverse().slice(-8);
  const maximum = Math.max(...entries.map(getCoverage), 1);
  document.querySelector("#progress-chart").innerHTML = entries.map((entry) => `
    <div class="bar-wrap" title="${getCoverage(entry)}% frame coverage">
      <div class="bar" style="height:${Math.max(12, getCoverage(entry) / maximum * 100)}%"></div>
      <span class="bar-label">${new Date(entry.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
    </div>`).join("");
}

function renderTimeline() {
  const entries = state.entries;
  document.querySelector("#timeline-empty").classList.toggle("hidden", entries.length > 0);
  document.querySelector("#timeline-content").classList.toggle("hidden", entries.length === 0);
  if (!entries.length) return;
  const trend = getTrend(entries);
  document.querySelector("#timeline-summary").innerHTML = `
    <div class="summary-stat"><span>Photos</span><strong>${entries.length}</strong></div>
    <div class="summary-stat"><span>Latest coverage</span><strong>${getCoverage(entries[0])}%</strong></div>
    <div class="summary-stat"><span>Visual trend</span><strong>${trend.title}</strong></div>`;
  document.querySelector("#timeline-list").innerHTML = entries.map((entry, index) => {
    const model = entry.modelAnalysis;
    return `<article class="panel timeline-card">
      <img class="timeline-thumb" src="${entry.photo}" alt="Wound upload from ${formatFullDate(entry.date)}" />
      <div><div class="timeline-card-top"><div><span class="eyebrow muted">${index === 0 ? "Latest photo" : "Journal photo"}</span><h3>${formatFullDate(entry.date)}</h3></div><span class="trend-badge">${formatClass(model.classification.label)}</span></div>
      <p>${index < entries.length - 1 ? compareEntries(entry, entries[index + 1]) : "Baseline image for future visual comparisons."}</p>
      <div class="tag-row"><span class="mini-tag">${model.segmentation.coverage_percent}% coverage</span><span class="mini-tag">${model.segmentation.perimeter_pixels} px perimeter</span><span class="mini-tag">${Math.round(model.classification.confidence * 100)}% class confidence</span>${model.tissue_color_analysis ? `<span class="mini-tag">${formatTissueGroup(model.tissue_color_analysis.dominant_group)}</span>` : ""}</div></div>
    </article>`;
  }).join("");
}

function renderTissueComposition(tissue) {
  if (!tissue?.total_segmented_pixels) return '<div class="tissue-empty">Tissue-color estimate unavailable because no wound mask was detected.</div>';
  const groups = [
    ["red_pink_like", "red-pink"],
    ["yellow_tan_like", "yellow-tan"],
    ["dark_like", "dark"],
    ["pale_like", "pale"],
    ["unclassified", "other"],
  ];
  return `<section class="tissue-panel">
    <div class="tissue-panel-copy"><span class="eyebrow muted">Explainable color evidence</span><h3>Segmented color composition</h3><p>${tissue.interpretation}</p></div>
    <div class="tissue-bars">${groups.map(([group, cssClass]) => `<div class="tissue-row"><span>${formatTissueGroup(group)}</span><div class="tissue-track"><i class="${cssClass}" style="width:${tissue.percentages[group]}%"></i></div><strong>${tissue.percentages[group]}%</strong></div>`).join("")}</div>
  </section>`;
}

function renderProvider() {
  const latest = state.entries[0];
  const localTrend = latest ? getTrend(state.entries).title : "Awaiting baseline";
  const localIndicator = latest ? `${getCoverage(latest)}% frame coverage` : "No image analysis yet";
  const patients = [
    { name: "N. Perera", code: "WD-1042", date: "Today, 08:45", trend: "Deterioration signal", indicator: "Coverage increased 11%", priority: "High" },
    { name: "My photo journal", code: "LOCAL-001", date: latest ? relativeDate(latest.date) : "Not started", trend: localTrend, indicator: localIndicator, priority: latest && getTrend(state.entries).key === "deteriorating" ? "High" : "Routine" },
    { name: "S. Fernando", code: "WD-1038", date: "Yesterday", trend: "Improvement signal", indicator: "Coverage decreased 8%", priority: "Routine" },
  ];
  document.querySelector("#provider-table-body").innerHTML = patients.map((patient) => `<tr><td><strong>${patient.name}</strong><small>${patient.code}</small></td><td>${patient.date}</td><td>${patient.trend}</td><td>${patient.indicator}</td><td><span class="priority-badge ${patient.priority.toLowerCase()}">${patient.priority}</span></td></tr>`).join("");
  document.querySelector("#provider-patient-count").textContent = `${patients.length} patients`;
  document.querySelector("#provider-review-count").textContent = `${patients.filter((patient) => patient.priority !== "Routine").length} cases`;
}

function setTodayLabel() {
  document.querySelector("#today-label").textContent = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
}

export function setNextCheckinDate() {
  const next = new Date();
  next.setDate(next.getDate() + 3);
  document.querySelector("#next-day").textContent = String(next.getDate()).padStart(2, "0");
  document.querySelector("#next-month").textContent = next.toLocaleDateString("en-US", { month: "short" }).toUpperCase();
}
