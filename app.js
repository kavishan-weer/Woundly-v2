import { analyzePhoto } from "./js/api.js";
import { bindNavigation, showView } from "./js/navigation.js";
import { addEntry, state } from "./js/state.js";
import { bindUpload, resetUpload } from "./js/upload.js";
import { renderAll, renderResult, setNextCheckinDate } from "./js/views.js";
import { showToast } from "./js/utils.js";

const submitButton = document.querySelector('#checkin-form button[type="submit"]');

bindNavigation();
bindUpload();
bindPhotoAnalysis();
setNextCheckinDate();
renderAll();

function bindPhotoAnalysis() {
  document.querySelector("#checkin-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.currentPhoto) return showToast("Add a clear wound photo before running the analysis.");
    if (!document.querySelector("#prototype-consent").checked) {
      return showToast("Please confirm that you understand the prototype's limits.");
    }

    setLoading(true);
    try {
      const entry = {
        id: Date.now(),
        date: new Date().toISOString(),
        photo: state.currentPhoto,
        modelAnalysis: await analyzePhoto(state.currentPhoto),
      };
      addEntry(entry);
      renderAll();
      renderResult(entry);
      resetUpload();
      document.querySelector("#checkin-form").reset();
      showView("result");
    } catch (error) {
      showToast(error.message);
    } finally {
      setLoading(false);
    }
  });
}

function setLoading(loading) {
  submitButton.disabled = loading;
  submitButton.innerHTML = loading
    ? "Running AI models..."
    : 'Analyze and save check-in <svg viewBox="0 0 24 24"><path d="m9 18 6-6-6-6" /></svg>';
}
