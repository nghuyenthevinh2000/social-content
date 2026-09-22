const form = document.getElementById("form");
const textEl = document.getElementById("text");
const submitBtn = document.getElementById("submit");
const skillsChartEl = document.getElementById("skillsChart");
const resourceSectionsEl = document.getElementById("resourceSections");
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

function renderSection(chartEl, items, emptyText, hasStrongPrimary) {
  chartEl.innerHTML = "";

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "chart-empty";
    empty.textContent = emptyText;
    chartEl.appendChild(empty);
    return;
  }

  if (!hasStrongPrimary) {
    const banner = document.createElement("div");
    banner.className = "no-strong-candidate";
    banner.textContent = "No strong existing candidate — LLM decides";
    chartEl.appendChild(banner);
  }

  const maxConfidence = items[0].confidence || 1;
  const minConfidence = items[items.length - 1].confidence || 0;
  const spread = maxConfidence - minConfidence || 1; // avoid divide-by-zero

  items.forEach((item, i) => {
    // Only crown a "top" bar with the bold/glow treatment when Jev
    // actually landed on a strong winner — otherwise every option is
    // genuinely close/weak and singling one out would be misleading.
    const isTop = i === 0 && hasStrongPrimary;

    const row = document.createElement("div");
    row.className = "bar-row";
    row.style.animationDelay = `${i * 60}ms`;

    const label = document.createElement("div");
    label.className = "bar-label" + (isTop ? " top" : "");
    label.textContent = shortLabel(item.name);

    const track = document.createElement("div");
    track.className = "bar-track";

    const fill = document.createElement("div");
    fill.className = "bar-fill" + (isTop ? " glow" : "");
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
    // Fixed 0-100% scale against the true confidence value — NOT relative
    // to the batch's max. A 0.37 confidence always fills 37% of the bar,
    // even if it's the highest-scoring item in a weak batch, so bar length
    // always shows how far that candidate genuinely got, not just its rank.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const width = (item.confidence || 0) * 100;
        fill.style.width = `${Math.max(2, width)}%`;
      });
    });
  });
}

function renderResourceGroups(groups) {
  resourceSectionsEl.innerHTML = "";

  if (!groups.length) {
    const section = document.createElement("section");
    section.className = "chart-section";
    section.innerHTML = `
      <div class="section-title">2 · Resource within that skill</div>
      <div class="chart"><div class="chart-empty">waiting on a skill first</div></div>
    `;
    resourceSectionsEl.appendChild(section);
    return;
  }

  // A single group is the common case (one resource domain). Multiple
  // groups mean the skill needs several *independent* picks at once (e.g.
  // a layout AND a design style) — each gets its own numbered section so
  // they never read as mutually-exclusive alternatives of one another.
  groups.forEach((group, i) => {
    const section = document.createElement("section");
    section.className = "chart-section";

    const title = document.createElement("div");
    title.className = "section-title";
    title.textContent =
      groups.length > 1 ? `${2 + i} · ${group.group}` : `2 · ${group.group}`;

    const chart = document.createElement("div");
    chart.className = "chart";

    section.appendChild(title);
    section.appendChild(chart);
    resourceSectionsEl.appendChild(section);

    renderSection(
      chart,
      group.items,
      "no sub-resources found for this skill",
      group.has_strong_primary
    );
  });
}

function renderCharts(data) {
  const skills = data.skills || { group: "", items: [], has_strong_primary: false };
  const resourceGroups = data.resource_groups || [];

  renderSection(
    skillsChartEl,
    skills.items,
    "nothing stood out for that one",
    skills.has_strong_primary
  );
  renderResourceGroups(resourceGroups);
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
