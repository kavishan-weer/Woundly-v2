import { setCurrentPhoto } from "./state.js";
import { showToast } from "./utils.js";

const fileInput = document.querySelector("#wound-photo");
const uploadZone = document.querySelector("#upload-zone");
const preview = document.querySelector("#upload-preview");
const changeButton = document.querySelector("#change-photo");

export function bindUpload() {
  fileInput.addEventListener("change", () => handleFile(fileInput.files[0]));
  changeButton.addEventListener("click", (event) => {
    event.preventDefault();
    fileInput.click();
  });
  ["dragenter", "dragover"].forEach((name) => uploadZone.addEventListener(name, showDropTarget));
  ["dragleave", "drop"].forEach((name) => uploadZone.addEventListener(name, hideDropTarget));
  uploadZone.addEventListener("drop", (event) => handleFile(event.dataTransfer.files[0]));
}

export function resetUpload() {
  setCurrentPhoto("");
  fileInput.value = "";
  preview.removeAttribute("src");
  uploadZone.classList.remove("has-image");
  changeButton.classList.add("hidden");
}

function handleFile(file) {
  if (!file || !file.type.startsWith("image/")) return showToast("Please choose an image file.");
  const reader = new FileReader();
  reader.onload = (event) => compressImage(event.target.result);
  reader.readAsDataURL(file);
}

function compressImage(source) {
  const image = new Image();
  image.onload = () => {
    const scale = Math.min(1, 1000 / Math.max(image.width, image.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(image.width * scale);
    canvas.height = Math.round(image.height * scale);
    canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
    const photo = canvas.toDataURL("image/jpeg", 0.84);
    setCurrentPhoto(photo);
    preview.src = photo;
    uploadZone.classList.add("has-image");
    changeButton.classList.remove("hidden");
  };
  image.src = source;
}

function showDropTarget(event) {
  event.preventDefault();
  uploadZone.classList.add("dragging");
}

function hideDropTarget(event) {
  event.preventDefault();
  uploadZone.classList.remove("dragging");
}
