import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const appDir = path.join(root, "myApp");
const outFile = path.join(root, "docs", "FUNCTIONS_AND_ACE.md");

const pyFiles = [];
const htmlFiles = [];

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "__pycache__") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full);
    } else if (entry.isFile()) {
      if (full.endsWith(".py")) pyFiles.push(full);
      if (full.endsWith(".html") && full.includes(`${path.sep}templates${path.sep}`)) htmlFiles.push(full);
    }
  }
}

walk(appDir);

const pyRegex = /^\s*(async\s+def|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/gm;
const pyEntries = [];

for (const file of pyFiles.sort()) {
  const text = fs.readFileSync(file, "utf8");
  let match;
  while ((match = pyRegex.exec(text)) !== null) {
    const line = text.slice(0, match.index).split("\n").length;
    const signature = `${match[1].startsWith("async") ? "async " : ""}${match[2]}(${match[3].trim()})`;
    pyEntries.push({
      file: path.relative(root, file).replaceAll("\\", "/"),
      line,
      name: match[2],
      signature,
    });
  }
}

const jsFnRegex = /^\s*(async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/gm;
const jsArrowRegex = /^\s*(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>/gm;
const jsEntries = [];

for (const file of htmlFiles.sort()) {
  const text = fs.readFileSync(file, "utf8");
  let match;
  while ((match = jsFnRegex.exec(text)) !== null) {
    const line = text.slice(0, match.index).split("\n").length;
    const signature = `${match[1] ? "async " : ""}${match[2]}(${match[3].trim()})`;
    jsEntries.push({
      file: path.relative(root, file).replaceAll("\\", "/"),
      line,
      name: match[2],
      signature,
      kind: "function",
    });
  }
  while ((match = jsArrowRegex.exec(text)) !== null) {
    const line = text.slice(0, match.index).split("\n").length;
    const signature = `${match[1]}(${match[2].trim()})`;
    jsEntries.push({
      file: path.relative(root, file).replaceAll("\\", "/"),
      line,
      name: match[1],
      signature,
      kind: "arrow-function",
    });
  }
}

const urlsFile = path.join(appDir, "urls.py");
const endpoints = [];
if (fs.existsSync(urlsFile)) {
  const urlsText = fs.readFileSync(urlsFile, "utf8");
  const endpointRegex = /path\("([^"]+)",\s*views\.([A-Za-z_][A-Za-z0-9_]*)/g;
  let match;
  while ((match = endpointRegex.exec(urlsText)) !== null) {
    endpoints.push({ route: match[1], view: match[2] });
  }
}
endpoints.sort((a, b) => a.route.localeCompare(b.route));

const endpointGroups = {
  "Authentication": [],
  "Admin APIs": [],
  "Chat APIs": [],
  "Core APIs": [],
  "Admin UI Routes": [],
  "Web UI Routes": [],
};

for (const { route } of endpoints) {
  if (route.startsWith("api/auth/")) endpointGroups["Authentication"].push(route);
  else if (route.startsWith("api/admin/")) endpointGroups["Admin APIs"].push(route);
  else if (route.startsWith("api/chat/")) endpointGroups["Chat APIs"].push(route);
  else if (route.startsWith("api/")) endpointGroups["Core APIs"].push(route);
  else if (route.startsWith("admin-dashboard")) endpointGroups["Admin UI Routes"].push(route);
  else endpointGroups["Web UI Routes"].push(route);
}

const lines = [];
lines.push("# Functions & ACE Documentation", "");
lines.push("Auto-generated inventory of current backend and frontend functions.", "");
lines.push("## Snapshot", "");
lines.push(`- Python functions/methods: **${pyEntries.length}**`);
lines.push(`- Template JavaScript functions: **${jsEntries.length}**`);
lines.push(`- URL endpoints mapped in \`myApp/urls.py\`: **${endpoints.length}**`, "");
lines.push("## ACE (Architecture, Capabilities, Entry Points)", "");
lines.push("- **Architecture:** Django monolith (`myProject`) with server-rendered templates and JSON API endpoints in `myApp/views.py`.");
lines.push("- **Capabilities:** authentication, onboarding, profiles, agents, prompts, chat, industries, events, tools, banners, admin operations, and impersonation.");
lines.push("- **Entry points:** routes in `myApp/urls.py` and client-side template JavaScript.", "");
lines.push("### Endpoint Groups", "");

for (const [group, routes] of Object.entries(endpointGroups)) {
  lines.push(`#### ${group} (${routes.length})`);
  for (const route of routes) {
    lines.push(`- \`${route}\``);
  }
  lines.push("");
}

lines.push("## Python Function Inventory", "");
const pyByFile = new Map();
for (const item of pyEntries) {
  if (!pyByFile.has(item.file)) pyByFile.set(item.file, []);
  pyByFile.get(item.file).push(item);
}
for (const file of [...pyByFile.keys()].sort()) {
  const items = pyByFile.get(file);
  lines.push(`### \`${file}\` (${items.length})`);
  for (const item of items) {
    lines.push(`- \`${item.signature}\``);
  }
  lines.push("");
}

lines.push("## Frontend Template JS Function Inventory", "");
const jsByFile = new Map();
for (const item of jsEntries) {
  if (!jsByFile.has(item.file)) jsByFile.set(item.file, []);
  jsByFile.get(item.file).push(item);
}
for (const file of [...jsByFile.keys()].sort()) {
  const items = jsByFile.get(file);
  lines.push(`### \`${file}\` (${items.length})`);
  for (const item of items) {
    lines.push(`- \`${item.signature}\` - ${item.kind}`);
  }
  lines.push("");
}

lines.push("## Notes", "");
lines.push("- This file is generated; refresh it whenever function signatures change.");
lines.push("- Includes Python `def`/`async def` declarations and JS template function declarations/arrow functions.", "");

fs.mkdirSync(path.dirname(outFile), { recursive: true });
fs.writeFileSync(outFile, lines.join("\n"), "utf8");

console.log(`Wrote ${outFile}`);
console.log(`Python entries: ${pyEntries.length}`);
console.log(`JS entries: ${jsEntries.length}`);
console.log(`Endpoints: ${endpoints.length}`);
