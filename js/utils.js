

export function formatTissueGroup(value) {
  return {
    red_pink_like: "Red / pink-like",
    yellow_tan_like: "Yellow / tan-like",
    dark_like: "Dark-like",
    pale_like: "Pale-like",
    unclassified: "Other colors",
  }[value] || "Unavailable";
}

export function relativeDate(value) {
  const days = Math.floor((Date.now() - new Date(value).getTime()) / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return `${days} days ago`;
}

export function formatShortDate(value) {
  return new Date(value).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatFullDate(value) {
  return new Date(value).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" });
}

let toastTimer;
export function showToast(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3200);
}
