export async function analyzePhoto(photo) {
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image: photo }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "The model service could not analyze this image.");
  return payload;
}
