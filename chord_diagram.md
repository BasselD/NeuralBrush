Yes. Do it this way.

## 1. Main changes you need

### Replace your color logic with fixed role colors

Add this near the top of your script:

```js
const PCP_COLOR = "#A7D8F0";        // light blue
const PROVIDER_COLOR = "#0B3D91";   // darker blue
```

Then after `names` is created, add role detection:

```js
const pcps = new Set(data.map(d => d.pcp));
const providers = new Set(data.map(d => d.specialist));

function nodeColor(name) {
  if (pcps.has(name)) return PCP_COLOR;
  if (providers.has(name)) return PROVIDER_COLOR;
  return "#9ca3af";
}
```

Then replace this:

```js
.attr("fill", d => color(names[d.index]))
```

With this:

```js
.attr("fill", d => nodeColor(names[d.index]))
```

You can remove this block entirely:

```js
const color = d3.scaleOrdinal()
  .domain(names)
  .range(d3.schemeTableau10.concat(d3.schemeSet3));
```

---

## 2. Color ribbons from light gray to red by CPC

Assuming `CPC` is numeric, update your parser:

```js
cpc: +String(d["CPC"] ?? "").replace(/[$,]/g, "")
```

Then create a lookup after filtering/slicing data:

```js
const flowStats = new Map();

data.forEach(d => {
  const key = `${d.pcp}|||${d.specialist}`;

  if (!flowStats.has(key)) {
    flowStats.set(key, {
      cost: 0,
      cpcWeightedSum: 0
    });
  }

  const item = flowStats.get(key);
  item.cost += d.cost;

  if (Number.isFinite(d.cpc)) {
    item.cpcWeightedSum += d.cpc * d.cost;
  }
});

flowStats.forEach(v => {
  v.avgCpc = v.cost > 0 ? v.cpcWeightedSum / v.cost : null;
});
```

Then add the CPC color scale:

```js
const cpcValues = Array.from(flowStats.values())
  .map(d => d.avgCpc)
  .filter(d => Number.isFinite(d));

const cpcColor = d3.scaleLinear()
  .domain(d3.extent(cpcValues))
  .range(["#d1d5db", "#dc2626"]);
```

Then replace the ribbon fill:

```js
.attr("fill", d => color(names[d.source.index]))
.attr("stroke", d => d3.rgb(color(names[d.source.index])).darker())
```

With:

```js
.attr("fill", d => {
  const sourceName = names[d.source.index];
  const targetName = names[d.target.index];
  const key = `${sourceName}|||${targetName}`;
  const avgCpc = flowStats.get(key)?.avgCpc;

  return Number.isFinite(avgCpc) ? cpcColor(avgCpc) : "#d1d5db";
})
.attr("stroke", d => {
  const sourceName = names[d.source.index];
  const targetName = names[d.target.index];
  const key = `${sourceName}|||${targetName}`;
  const avgCpc = flowStats.get(key)?.avgCpc;
  const base = Number.isFinite(avgCpc) ? cpcColor(avgCpc) : "#d1d5db";

  return d3.rgb(base).darker();
})
```

Also update the tooltip:

```js
const key = `${sourceName}|||${targetName}`;
const avgCpc = flowStats.get(key)?.avgCpc;
```

Then inside the tooltip HTML:

```js
Avg CPC: ${Number.isFinite(avgCpc) ? formatCost(avgCpc) : "N/A"}<br>
```

---

## 3. Add legend top right

Add this after defining `svg`:

```js
const legend = svg.append("g")
  .attr("transform", `translate(${width / 2 - 220}, ${-height / 2 + 35})`);

legend.append("rect")
  .attr("x", -12)
  .attr("y", -18)
  .attr("width", 190)
  .attr("height", 92)
  .attr("rx", 10)
  .attr("fill", "#ffffff")
  .attr("stroke", "#e5e7eb");

legend.append("circle")
  .attr("cx", 0)
  .attr("cy", 0)
  .attr("r", 7)
  .attr("fill", PCP_COLOR);

legend.append("text")
  .attr("x", 16)
  .attr("y", 4)
  .style("font-size", "12px")
  .text("PCP");

legend.append("circle")
  .attr("cx", 0)
  .attr("cy", 24)
  .attr("r", 7)
  .attr("fill", PROVIDER_COLOR);

legend.append("text")
  .attr("x", 16)
  .attr("y", 28)
  .style("font-size", "12px")
  .text("Specialist / Provider");

const gradientId = "cpcLegendGradient";

const defs = svg.append("defs");

const gradient = defs.append("linearGradient")
  .attr("id", gradientId)
  .attr("x1", "0%")
  .attr("x2", "100%");

gradient.append("stop")
  .attr("offset", "0%")
  .attr("stop-color", "#d1d5db");

gradient.append("stop")
  .attr("offset", "100%")
  .attr("stop-color", "#dc2626");

legend.append("rect")
  .attr("x", 0)
  .attr("y", 48)
  .attr("width", 90)
  .attr("height", 10)
  .attr("fill", `url(#${gradientId})`);

legend.append("text")
  .attr("x", 100)
  .attr("y", 58)
  .style("font-size", "12px")
  .text("CPC");
```

---

## 4. Cleaner Streamlit setup

Yes, make the chart independent. Best structure:

```text
referral_app/
  app.py
  radiology_referrals.csv
  chord_diagram.html
```

### `app.py`

```python
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

st.set_page_config(page_title="Radiology Referral Chord Diagram", layout="wide")

st.title("Radiology Referral Cost Flow")

html = Path("chord_diagram.html").read_text(encoding="utf-8")

components.html(html, height=850, scrolling=True)
```

### Why this works

Your Streamlit app becomes only the **container**. The actual D3 logic stays in:

```text
chord_diagram.html
```

That is cleaner and easier to debug.

One warning: if `chord_diagram.html` still uses:

```js
d3.csv("radiology_referrals.csv")
```

the CSV may not always resolve correctly inside Streamlit’s iframe. The more reliable version is to have Python read the CSV and inject it into the HTML, but for simple local usage, keeping the HTML separate is fine.

## My recommendation

Use Streamlit as the wrapper, but keep the D3 in a separate HTML file. That gives you:

```text
Python = app shell
HTML/D3 = visualization logic
CSV = data
```

Clean separation. Less spaghetti. More “analytics director,” less “I duct-taped JavaScript to a dashboard at 1 AM.”

```js
const topN = 25;
const topN = 50;
const topN = 75;
```
-----
## Best columns to add later

To make this more executive-ready, add:

| Field                | Why it helps                                      |
| -------------------- | ------------------------------------------------- |
| Referral Count       | Separates high-cost flow from high-volume flow    |
| Avg Cost             | Shows expensive referral patterns                 |
| PCP Group            | Lets you color PCPs by market/group               |
| Specialist Specialty | Lets you group radiology, ortho, cardiology, etc. |
| Member Count         | Helps normalize referral intensity                |

The D3 version is the best choice here. Python can do chord-like visuals, but D3 gives you cleaner interactivity and better executive storytelling.
