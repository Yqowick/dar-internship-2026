const fs = require("node:fs");
const path = require("node:path");

const root = __dirname;
const pagesDir = path.join(root, "pages");
const manifestPath = path.join(pagesDir, "index.json");
const excludedFiles = new Set(["example.html"]);

function displayName(filename) {
  const stem = path.basename(filename, ".html");
  const words = stem.split(/[-_]+/).filter(Boolean);
  return words.map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ") || stem;
}

function buildEntries() {
  if (!fs.existsSync(pagesDir)) {
    fs.mkdirSync(pagesDir, { recursive: true });
  }

  return fs
    .readdirSync(pagesDir, { withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => entry.name)
    .filter((filename) => filename.toLowerCase().endsWith(".html"))
    .filter((filename) => !excludedFiles.has(filename.toLowerCase()))
    .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }))
    .map((filename) => ({
      file: filename,
      name: displayName(filename),
      path: `pages/${filename}`,
    }));
}

fs.writeFileSync(manifestPath, `${JSON.stringify(buildEntries(), null, 2)}\n`, "utf8");