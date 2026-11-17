const button = document.getElementById("copy");
const ip = document.getElementById("ip").textContent.trim();

button.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(ip);
    button.textContent = "Copied!";
  } catch {
    button.textContent = "Copy failed";
  }
  setTimeout(() => (button.textContent = "Copy"), 1500);
});
