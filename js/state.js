import { authFetch } from "./auth.js";

export const state = {
  entries: [],
  currentPhoto: "",
};

export async function loadEntries() {
  try {
    const response = await authFetch("/api/entries");
    if (!response.ok) throw new Error("Failed to load entries.");
    state.entries = await response.json();
  } catch {
    state.entries = [];
  }
}

export async function addEntry(entry) {
  const response = await authFetch("/api/entries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entry),
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.error || "Failed to save entry.");
  }
  state.entries.unshift(entry);
}

export function setCurrentPhoto(photo) {
  state.currentPhoto = photo;
}

export async function deleteEntry(entryId) {
  const response = await authFetch(`/api/entries/${entryId}`, { method: "DELETE" });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.error || "Failed to delete entry.");
  }
  state.entries = state.entries.filter((e) => String(e.id) !== String(entryId));
}
