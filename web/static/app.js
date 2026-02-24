const sampleName = window.DEMO?.sampleName;

const $ = (id) => document.getElementById(id);

const btnDenoise = $("btnDenoise");
const btnResetZoom = $("btnResetZoom");
const btnErase = $("btnErase");
const btnPlayNoisy = $("btnPlayNoisy");
const btnPlayDenoised = $("btnPlayDenoised");

const modelSelect = $("modelSelect");
const metaBox = $("metaBox");

const imgNoisy = $("imgNoisy");
const imgDenoised = $("imgDenoised");
const imgZoomNoisy = $("imgZoomNoisy");
const imgZoomDenoised = $("imgZoomDenoised");

const noisySpinner = $("noisySpinner");
const denoisedSpinner = $("denoisedSpinner");
const denoisedPlaceholder = $("denoisedPlaceholder");

const toast = $("toast");

let zoomStartS = 0.0;
const zoomLenS = 1.0;

function showToastOnce(key, msg) {
  try {
    if (localStorage.getItem(key)) return;
    localStorage.setItem(key, "1");
  } catch (_) {}

  toast.textContent = msg;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 2600);
}

function setBusy(isBusy) {
  btnDenoise.disabled = isBusy;
  modelSelect.disabled = isBusy;
  btnResetZoom.disabled = isBusy;
  btnErase.disabled = isBusy;

  if (isBusy) {
    btnDenoise.textContent = "Denoising…";
    denoisedSpinner.classList.remove("hidden");
  } else {
    btnDenoise.textContent = "Denoise";
    denoisedSpinner.classList.add("hidden");
  }
}

function bust(url) {
  const u = new URL(url, window.location.origin);
  u.searchParams.set("_t", String(Date.now()));
  return u.toString();
}

async function loadMeta() {
  const r = await fetch(`/api/sample/${encodeURIComponent(sampleName)}/meta`, { cache: "no-store" });
  if (!r.ok) throw new Error("meta failed");
  const meta = await r.json();

  const model = modelSelect.value || "";
  metaBox.textContent =
`Sample: ${meta.sample}
Duration: ${meta.duration_ms} ms
Rate: ${meta.rate_hz} Hz
Model:
${model}
Zoom start: ${zoomStartS.toFixed(3)} s`;
}

function setNoisyImages() {
  imgNoisy.src = bust(`/api/sample/${encodeURIComponent(sampleName)}/spectrogram/noisy.png`);
  imgZoomNoisy.src = bust(`/api/sample/${encodeURIComponent(sampleName)}/spectrogram/zoom/noisy.png?zoom_start_s=${zoomStartS}&zoom_len_s=${zoomLenS}`);
}

function setDenoisedImages() {
  imgDenoised.src = bust(`/api/sample/${encodeURIComponent(sampleName)}/spectrogram/denoised.png`);
  imgZoomDenoised.src = bust(`/api/sample/${encodeURIComponent(sampleName)}/spectrogram/zoom/denoised.png?zoom_start_s=${zoomStartS}&zoom_len_s=${zoomLenS}`);
}

async function denoise() {
  setBusy(true);
  try {
    const payload = {
      model: modelSelect.value,
      zoom_start_s: zoomStartS,
      zoom_len_s: zoomLenS
    };

    const r = await fetch(`/api/sample/${encodeURIComponent(sampleName)}/denoise`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!r.ok) throw new Error("denoise failed");

    denoisedPlaceholder.classList.add("hidden");
    imgDenoised.classList.remove("placeholder");
    setDenoisedImages();
    btnPlayDenoised.disabled = false;

    await loadMeta();
  } finally {
    setBusy(false);
  }
}

async function resetZoom() {
  zoomStartS = 0.0;
  await fetch(`/api/sample/${encodeURIComponent(sampleName)}/reset_zoom`, { method: "POST" }).catch(() => {});
  setNoisyImages();
  setDenoisedImages();
  await loadMeta();
}

async function eraseEdits() {
  await fetch(`/api/sample/${encodeURIComponent(sampleName)}/erase_edits`, { method: "POST" }).catch(() => {});
  btnPlayDenoised.disabled = true;
  denoisedPlaceholder.classList.remove("hidden");
  imgDenoised.classList.add("placeholder");
  imgDenoised.removeAttribute("src");
  imgZoomDenoised.removeAttribute("src");
}

function attachTapToZoom() {
  imgNoisy.addEventListener("click", (ev) => {
    const rect = imgNoisy.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, ev.clientX - rect.left));
    const rel = rect.width > 0 ? (x / rect.width) : 0;
    const assumedDurationS = 20.0;
    zoomStartS = Math.max(0, rel * assumedDurationS);

    setNoisyImages();
    setDenoisedImages();
    loadMeta();
  });
}

async function main() {
  showToastOnce("tap_to_zoom_toast", "Tip: tap the long spectrogram to select a 1s window.");

  noisySpinner.classList.remove("hidden");
  try {
    await loadMeta();
    setNoisyImages();
    attachTapToZoom();
  } finally {
    noisySpinner.classList.add("hidden");
  }

  btnDenoise.addEventListener("click", denoise);
  btnResetZoom.addEventListener("click", resetZoom);
  btnErase.addEventListener("click", eraseEdits);

  modelSelect.addEventListener("change", async () => {
    await loadMeta();
  });

  btnPlayNoisy.addEventListener("click", () => {
    const a = new Audio(`/api/sample/${encodeURIComponent(sampleName)}/audio`);
    a.play().catch(() => {});
  });

  btnPlayDenoised.addEventListener("click", () => {
  });
}

main().catch((e) => {
  console.error(e);
});
