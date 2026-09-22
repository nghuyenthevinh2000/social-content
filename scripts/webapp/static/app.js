const form = document.getElementById("form");
const textEl = document.getElementById("text");
const submitBtn = document.getElementById("submit");
const skillsChartEl = document.getElementById("skillsChart");
const resourcesChartEl = document.getElementById("resourcesChart");
const statusEl = document.getElementById("status");

// Cool -> warm spectrum. Normalized per-batch (min..max of the current
// results) rather than against the raw 0-1 scale, so the hues always
// spread across the full range even when every score is clustered near
// the top (e.g. 0.75-1.0) — otherwise they'd all come out the same amber.
function colorFor(rank01) {
  const hue = 265 - rank01 * 245; // 265 violet -> ~20 amber
  const light = 55 + rank01 * 8;
  return { hue, light };
}

function gradientFor(rank01) {
  const { hue, light } = colorFor(rank01);
  const solid = `hsl(${hue}, 85%, ${light}%)`;
  const soft = `hsl(${hue}, 85%, ${Math.max(light - 14, 18)}%)`;
  return { solid, css: `linear-gradient(90deg, ${soft}, ${solid})` };
}

function shortLabel(name) {
  // Trim long resource paths down to something readable without losing
  // the meaningful tail (e.g. "references/naming/principles.md").
  return name.length > 42 ? "…" + name.slice(-40) : name;
}

function renderSection(chartEl, group, items, emptyText) {
  chartEl.innerHTML = "";

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = emptyText;
    chartEl.appendChild(empty);
    return;
  }

  if (group) {
    const tag = document.createElement("div");
    tag.className = "group-tag";
    tag.textContent = `within: ${group}`;
    chartEl.appendChild(tag);
  }

  const maxConfidence = items[0].confidence || 1;
  const minConfidence = items[items.length - 1].confidence || 0;
  const spread = maxConfidence - minConfidence || 1; // avoid divide-by-zero

  items.forEach((item, i) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.style.animationDelay = `${i * 60}ms`;

    const label = document.createElement("div");
    label.className = "bar-label" + (i === 0 ? " top" : "");
    label.textContent = shortLabel(item.name);

    const track = document.createElement("div");
    track.className = "bar-track";

    const fill = document.createElement("div");
    fill.className = "bar-fill" + (i === 0 ? " glow" : "");
    // Rank (0..1) within this batch, not raw confidence — keeps colors
    // spread across the full spectrum even when scores are clustered.
    const rank01 = (item.confidence - minConfidence) / spread;
    const { solid, css } = gradientFor(rank01);
    fill.style.background = css;
    fill.style.color = solid; // drives the glow's box-shadow (currentColor)

    track.appendChild(fill);
    row.appendChild(label);
    row.appendChild(track);
    chartEl.appendChild(row);

    // Animate the width in on the next frame so the CSS transition fires.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const relative = maxConfidence
          ? (item.confidence / maxConfidence) * 100
          : 0;
        fill.style.width = `${Math.max(4, relative)}%`;
      });
    });
  });
}

function renderCharts(data) {
  const skills = data.skills || { group: "", items: [] };
  const resources = data.resources || { group: "", items: [] };

  renderSection(skillsChartEl, "", skills.items, "nothing stood out for that one");
  renderSection(
    resourcesChartEl,
    resources.group,
    resources.items,
    resources.group
      ? "no sub-resources found for this skill"
      : "waiting on a skill first"
  );
}

async function analyze(text) {
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    throw new Error("request failed");
  }
  return res.json();
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = textEl.value.trim();
  if (!text) return;

  submitBtn.disabled = true;
  statusEl.textContent = "listening…";

  try {
    const data = await analyze(text);
    renderCharts(data);
    statusEl.textContent = "\u00A0";
  } catch (err) {
    statusEl.textContent = "Jev is unreachable — is the server running?";
  } finally {
    submitBtn.disabled = false;
  }
});
