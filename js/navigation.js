const pageTitles = {
  dashboard: "Wound overview",
  "check-in": "New check-in",
  result: "Image analysis",
  timeline: "Progress timeline",
  provider: "Provider review",
  guidance: "Photo guide",
};

export function bindNavigation() {
  document.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.go));
  });
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });
  document.querySelector("#menu-toggle").addEventListener("click", () => {
    document.querySelector("#sidebar").classList.toggle("open");
  });
}

export function showView(view) {
  document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
  document.querySelector(`#${view}-view`).classList.add("active");
  document.querySelector("#page-title").textContent = pageTitles[view];
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.querySelector("#sidebar").classList.remove("open");
  window.scrollTo({ top: 0, behavior: "smooth" });
}
