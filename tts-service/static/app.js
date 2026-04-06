// static/app.js
const textEl = document.getElementById("text");
const readBtn = document.getElementById("readBtn");
const normalizeBtn = document.getElementById("normalizeBtn");
const normPanel = document.getElementById("normPanel");
const normResult = document.getElementById("normResult");
const closeNorm = document.getElementById("closeNorm");
const useNorm = document.getElementById("useNorm");
const playerWrap = document.getElementById("playerWrap");
const player = document.getElementById("player");

normalizeBtn.addEventListener("click", async () => {
  const text = textEl.value;
  if (!text.trim()) { alert("Inserisci del testo prima."); return; }

  normalizeBtn.disabled = true;
//   normalizeBtn.textContent = "Caricamento...";
  try {
    const res = await fetch("/normalize", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({text})
    });
    if (!res.ok) throw new Error("Errore normalize");
    const data = await res.json();
    normResult.textContent = `Original:\n${data.original}\n\nNormalized:\n${data.normalized}`;
    normPanel.classList.remove("hidden");
  } catch (err) {
    alert("Errore nella normalizzazione: " + err.message);
  } finally {
    normalizeBtn.disabled = false;
    // normalizeBtn.textContent = "Mostra normalizzazione";
  }
});

closeNorm.addEventListener("click", () => normPanel.classList.add("hidden"));
useNorm.addEventListener("click", () => {
  const parts = normResult.textContent.split("\n\nNormalized:\n");
  if (parts.length === 2) {
    textEl.value = parts[1];
  }
  normPanel.classList.add("hidden");
});



readBtn.addEventListener("click", async () => {
  const text = textEl.value;
  if (!text.trim()) { alert("Inserisci del testo prima."); return; }

  const readBtn = document.getElementById("readIcon");
  readBtn.classList.remove("fa-play");
  readBtn.classList.add("fa-spinner", "loading"); // fa-spinner is Font Awesome spinner

  readBtn.disabled = true;
  //   readBtn.textContent = "Generazione in corso...";


  try {
    const res = await fetch("/tts", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({text})
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "TTS failed");
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    player.src = url;
    playerWrap.classList.remove("hidden");
    await player.play();
  } catch (err) {
    alert("Errore TTS: " + err.message);
  } finally {
    readBtn.classList.remove("fa-spinner", "loading");
    readBtn.classList.add("fa-play");
    readBtn.disabled = false;
  }
});
