export function getTrend(entries) {
  if (entries.length < 2) return { key: "baseline", title: "Baseline saved", note: "Add another photo to compare" };
  const change = getCoverageChange(entries[0], entries[1]);
  const tissue = getTissueChange(entries[0], entries[1]);
  if (tissue?.reviewSuggested) return { key: "review", title: "Visual review suggested", note: tissue.summary };
  if (!change) return { key: "unknown", title: "Comparison unavailable", note: "A visible mask is needed in both images" };
  if (change.percent <= -8) return { key: "improving", title: "Improvement signal", note: "Segmented frame coverage decreased" };
  if (change.percent >= 8) return { key: "deteriorating", title: "Deterioration signal", note: "Segmented frame coverage increased" };
  return { key: "stable", title: "No major change", note: "Segmented frame coverage is similar" };
}

export function compareEntries(current, previous) {
  const change = getCoverageChange(current, previous);
  const tissue = getTissueChange(current, previous);
  if (!change) return "A mask comparison is unavailable. Add another clear photo using the same angle and distance.";
  const direction = change.percent < 0 ? "lower" : "higher";
  const tissueNote = tissue ? ` ${tissue.summary}` : "";
  return `Segmented frame coverage is ${Math.abs(change.percent).toFixed(1)}% ${direction} than the previous upload.${tissueNote} Camera distance, angle, and lighting can affect these estimates.`;
}

export function getCoverage(entry) {
  return Number(entry?.modelAnalysis?.segmentation?.coverage_percent) || 0;
}

export function getTissuePercent(entry, group) {
  return Number(entry?.modelAnalysis?.tissue_color_analysis?.percentages?.[group]) || 0;
}

function getCoverageChange(current, previous) {
  const currentCoverage = getCoverage(current);
  const previousCoverage = getCoverage(previous);
  if (!currentCoverage || !previousCoverage) return null;
  return { percent: ((currentCoverage - previousCoverage) / previousCoverage) * 100 };
}

function getTissueChange(current, previous) {
  if (!current?.modelAnalysis?.tissue_color_analysis || !previous?.modelAnalysis?.tissue_color_analysis) return null;
  const darkChange = getTissuePercent(current, "dark_like") - getTissuePercent(previous, "dark_like");
  const yellowChange = getTissuePercent(current, "yellow_tan_like") - getTissuePercent(previous, "yellow_tan_like");
  const changes = [];
  if (Math.abs(darkChange) >= 5) changes.push(`dark-like pixels ${formatDirection(darkChange)}`);
  if (Math.abs(yellowChange) >= 10) changes.push(`yellow/tan-like pixels ${formatDirection(yellowChange)}`);
  return {
    reviewSuggested: darkChange >= 5 || yellowChange >= 10,
    summary: changes.length ? `Color-group change: ${changes.join(" and ")}.` : "No large color-group change was detected.",
  };
}

function formatDirection(change) {
  return `${Math.abs(change).toFixed(1)} percentage points ${change < 0 ? "lower" : "higher"}`;
}
