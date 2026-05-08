Yes. A **directed chord diagram** is a strong fit here because your data is naturally:

**PCP → Specialist**, weighted by **Cost(SUM)**

Below is a clean **D3.js version** you can run locally.

## Expected data

Save your data as `radiology_referrals.csv`:

```csv
PCP Name,Provider Name,Cost(SUM)
Dr. Smith,Dr. Patel,12500
Dr. Smith,Dr. Nguyen,8400
Dr. Jones,Dr. Patel,10200
Dr. Lee,Dr. Gomez,7600
```

## Full D3.js example

Save this as `index.html` in the same folder as your CSV.

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Radiology PCP to Specialist Directed Chord Diagram</title>
  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>

  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      background: #f7f9fb;
      color: #1f2937;
    }

    h2 {
      text-align: center;
      margin-top: 24px;
      margin-bottom: 4px;
    }

    .subtitle {
      text-align: center;
      color: #6b7280;
      font-size: 14px;
      margin-bottom: 16px;
    }

    svg {
      display: block;
      margin: auto;
      background: white;
      border-radius: 18px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.08);
    }

    .group path {
      stroke: #fff;
      stroke-width: 1px;
    }

    .group text {
      font-size: 11px;
      font-weight: 600;
    }

    .ribbon {
      fill-opacity: 0.65;
      stroke-opacity: 0.35;
    }

    .ribbon:hover {
      fill-opacity: 0.95;
      stroke-opacity: 0.8;
    }

    .tooltip {
      position: absolute;
      padding: 10px 12px;
      background: rgba(17, 24, 39, 0.92);
      color: white;
      border-radius: 8px;
      font-size: 13px;
      pointer-events: none;
      opacity: 0;
      line-height: 1.4;
    }
  </style>
</head>

<body>

<h2>Radiology Referral Cost Flow</h2>
<div class="subtitle">Directed flow from PCPs to specialists, weighted by Cost(SUM)</div>

<div class="tooltip"></div>
<svg width="950" height="850"></svg>

<script>
const width = 950;
const height = 850;
const outerRadius = Math.min(width, height) * 0.42;
const innerRadius = outerRadius - 22;

const svg = d3.select("svg")
  .attr("viewBox", [-width / 2, -height / 2, width, height]);

const tooltip = d3.select(".tooltip");

const formatCost = d3.format("$,.0f");

d3.csv("radiology_referrals.csv").then(data => {

  // Clean and standardize fields
  data = data
    .map(d => ({
      pcp: d["PCP Name"]?.trim(),
      specialist: d["Provider Name"]?.trim(),
      cost: +String(d["Cost(SUM)"]).replace(/[$,]/g, "")
    }))
    .filter(d => d.pcp && d.specialist && !isNaN(d.cost) && d.cost > 0);

  // Optional: keep top flows only so the chart does not become spaghetti soup
  const topN = 40;
  data = data
    .sort((a, b) => d3.descending(a.cost, b.cost))
    .slice(0, topN);

  // Create unique node list
  const names = Array.from(new Set([
    ...data.map(d => d.pcp),
    ...data.map(d => d.specialist)
  ]));

  const index = new Map(names.map((name, i) => [name, i]));

  // Build square matrix
  const matrix = Array.from({ length: names.length }, () =>
    Array(names.length).fill(0)
  );

  data.forEach(d => {
    matrix[index.get(d.pcp)][index.get(d.specialist)] += d.cost;
  });

  const chord = d3.chordDirected()
    .padAngle(0.04)
    .sortSubgroups(d3.descending)
    .sortChords(d3.descending);

  const chords = chord(matrix);

  const color = d3.scaleOrdinal()
    .domain(names)
    .range(d3.schemeTableau10.concat(d3.schemeSet3));

  const arc = d3.arc()
    .innerRadius(innerRadius)
    .outerRadius(outerRadius);

  const ribbon = d3.ribbonArrow()
    .radius(innerRadius - 2)
    .padAngle(0.01);

  // Draw outer arcs
  const group = svg.append("g")
    .selectAll("g")
    .data(chords.groups)
    .join("g")
    .attr("class", "group");

  group.append("path")
    .attr("fill", d => color(names[d.index]))
    .attr("d", arc)
    .on("mouseover", function(event, d) {
      const name = names[d.index];

      const sent = d3.sum(matrix[d.index]);
      const received = d3.sum(matrix, row => row[d.index]);

      tooltip
        .style("opacity", 1)
        .html(`
          <strong>${name}</strong><br>
          Outgoing: ${formatCost(sent)}<br>
          Incoming: ${formatCost(received)}
        `);
    })
    .on("mousemove", event => {
      tooltip
        .style("left", `${event.pageX + 14}px`)
        .style("top", `${event.pageY - 20}px`);
    })
    .on("mouseout", () => tooltip.style("opacity", 0));

  // Add labels
  group.append("text")
    .each(d => d.angle = (d.startAngle + d.endAngle) / 2)
    .attr("dy", "0.35em")
    .attr("transform", d => `
      rotate(${(d.angle * 180 / Math.PI - 90)})
      translate(${outerRadius + 12})
      ${d.angle > Math.PI ? "rotate(180)" : ""}
    `)
    .attr("text-anchor", d => d.angle > Math.PI ? "end" : "start")
    .text(d => names[d.index]);

  // Draw directed ribbons
  svg.append("g")
    .attr("fill-opacity", 0.75)
    .selectAll("path")
    .data(chords)
    .join("path")
    .attr("class", "ribbon")
    .attr("d", ribbon)
    .attr("fill", d => color(names[d.source.index]))
    .attr("stroke", d => d3.rgb(color(names[d.source.index])).darker())
    .on("mouseover", function(event, d) {
      d3.select(this).raise();

      tooltip
        .style("opacity", 1)
        .html(`
          <strong>${names[d.source.index]}</strong> → <strong>${names[d.target.index]}</strong><br>
          Cost: ${formatCost(d.source.value)}
        `);
    })
    .on("mousemove", event => {
      tooltip
        .style("left", `${event.pageX + 14}px`)
        .style("top", `${event.pageY - 20}px`);
    })
    .on("mouseout", () => tooltip.style("opacity", 0));

});
</script>

</body>
</html>
```

## How to run it locally

Because browsers block local CSV loading, run a tiny local server:

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

## Important recommendation

For healthcare referral data, do **not** show every PCP and specialist. That becomes a visual lasagna. Start with:

```js
const topN = 40;
```

Then tune it to:

```js
const topN = 25;
const topN = 50;
const topN = 75;
```

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
