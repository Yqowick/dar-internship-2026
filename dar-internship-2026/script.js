const gallery = document.querySelector("#gallery");
const galleryCount = document.querySelector("#gallery-count");

function entryLabel(entry) {
  return entry.name || entry.file.replace(/\.html$/i, "");
}

function setCount(count) {
  galleryCount.textContent = count === 1 ? "1 entry" : `${count} entries`;
}

function renderEmptyState() {
  gallery.innerHTML = '<p class="empty-state">No pages yet.</p>';
  setCount(0);
}

function renderGallery(entries) {
  gallery.innerHTML = "";

  if (!entries.length) {
    renderEmptyState();
    return;
  }

  const fragment = document.createDocumentFragment();

  entries.forEach((entry) => {
    const link = document.createElement("a");
    const label = entryLabel(entry);

    link.className = "gallery-card";
    link.href = entry.path;
    link.setAttribute("aria-label", `Open ${label}`);

    const name = document.createElement("span");
    name.textContent = label;
    link.append(name);
    fragment.append(link);
  });

  gallery.append(fragment);
  setCount(entries.length);
}

async function loadGallery() {
  try {
    const response = await fetch("pages/index.json", { cache: "no-store" });

    if (!response.ok) {
      throw new Error(`Manifest request failed: ${response.status}`);
    }

    const entries = await response.json();
    renderGallery(Array.isArray(entries) ? entries : []);
  } catch (error) {
    gallery.innerHTML = '<p class="error-state">Could not load the intern gallery.</p>';
    galleryCount.textContent = "Unavailable";
    console.error(error);
  }
}

loadGallery();