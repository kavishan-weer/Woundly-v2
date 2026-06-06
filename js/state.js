const STORAGE_KEY = "woundly-photo-checkins-v2";

export const state = {
  entries: loadEntries(),
  currentPhoto: "",
};

export function addEntry(entry) {
  state.entries.unshift(entry);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.entries));
}

export function setCurrentPhoto(photo) {
  state.currentPhoto = photo;
}

function loadEntries() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}
