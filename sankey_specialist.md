## Main problem

Your Sankey/chord visual is mixing **two different concepts**:

| Visual element                 |                                                  Should represent | Why                                                   |
| ------------------------------ | ----------------------------------------------------------------: | ----------------------------------------------------- |
| **Cord / flow thickness**      |                   Referral volume, claims, members, or total cost | Shows “how much traffic” flows from PCP → radiologist |
| **Cord / node color darkness** | Cost intensity, such as **cost per claim** or **cost per member** | Shows “how expensive” that relationship is            |

The issue: the chart was treating the PCP-side value like a **sum**, so Armando’s PCP node looked very dark because all downstream referral costs were being added up.

That is why the color got skewed.

## The calculation you were trying to derive

You do **not** want this:

```text
PCP color = SUM(Cost per Claim)
```

That is wrong because ratios should not be summed. It creates nonsense math. Classic dashboard crime scene.

You want this:

```text
PCP Cost per Claim = SUM(Cost) / SUM(Claims)
```

Same for each PCP → Radiologist link:

```text
Referral Relationship CPC = SUM(Cost for that PCP/Radiologist pair) 
                            / SUM(Claims for that PCP/Radiologist pair)
```

## Simple example

Suppose Armando referred to 3 radiologists:

| PCP     | Radiologist |   Cost | Claims |  CPC |
| ------- | ----------: | -----: | -----: | ---: |
| Armando |       Rad A | $1,000 |     10 | $100 |
| Armando |       Rad B |   $500 |      5 | $100 |
| Armando |       Rad C |   $300 |      1 | $300 |

Wrong method:

```text
100 + 100 + 300 = 500
```

Correct method:

```text
(1000 + 500 + 300) / (10 + 5 + 1)
= 1800 / 16
= $112.50 CPC
```

So Armando’s true average cost intensity is **$112.50**, not **$500**.

## What needs to be calculated

You need two separate derived metrics:

### 1. Flow size metric

Use one of these:

```text
Claims
```

or

```text
Unique Members
```

or

```text
Total Cost
```

For referral optimization, I would use:

```text
Flow thickness = Claims or Unique Members
```

because you want volume to show referral behavior.

### 2. Color metric

Use:

```text
Cost per Claim = SUM(Cost) / SUM(Claims)
```

or better, if member-level cost matters:

```text
Cost per Unique Member = SUM(Cost) / COUNT(DISTINCT Member)
```

Since your current fields are `Cost(SUM)` and likely `Claims`, the cleanest one is:

```text
Color = SUM(Cost) / SUM(Claims)
```

## Why the calculation must happen after filtering

If the user filters to one PCP, one procedure family, or one year, the CPC should recalculate only for that filtered population.

So the logic is:

```text
1. Apply filters
2. Group by PCP + Radiologist
3. Calculate:
   Total Cost = SUM(Cost)
   Total Claims = SUM(Claims)
   CPC = Total Cost / Total Claims
4. Use:
   value/thickness = Total Claims
   color = CPC
```

## Business meaning

The question you are trying to answer is:

> “Which PCPs are sending meaningful referral volume to radiologists or radiology groups with unusually high cost intensity, after accounting for claim volume and procedure mix?”

That is the real analytic problem.

Not just:

> “Who has high total cost?”

Because high total cost could simply mean high volume.

## The next-level version

To avoid falsely blaming oncology or specialized radiology, you need procedure adjustment:

```text
Compare radiologists only within similar procedure codes / procedure categories
```

Example:

```text
MRI vs MRI
CT vs CT
Oncology imaging vs oncology imaging
Routine radiology vs routine radiology
```

Otherwise, an oncology radiologist will look “expensive” even when they are doing appropriate high-complexity work.

## Best final metric stack

For each PCP → Provider pair:

| Metric          | Formula                            | Use                      |
| --------------- | ---------------------------------- | ------------------------ |
| Referral Volume | `SUM(Claims)`                      | Cord thickness           |
| Total Cost      | `SUM(Cost)`                        | Tooltip                  |
| Cost per Claim  | `SUM(Cost) / SUM(Claims)`          | Color                    |
| Cost per Member | `SUM(Cost) / COUNTD(Member)`       | Optional color toggle    |
| Procedure Mix   | Top procedure categories           | Explain why cost is high |
| Trend           | Current year CPC vs prior year CPC | Detect changes           |

## Best wording for the proof of concept

> The purpose of this visual is to identify high-volume PCP referral patterns where the receiving radiology provider or group has materially higher cost intensity. Flow thickness should represent referral volume, while color should represent normalized cost, such as cost per claim. This prevents high-volume PCPs from looking expensive simply because they send more referrals. The next step is to normalize by procedure category so specialized providers, such as oncology radiologists, are compared fairly against similar services.


You need to change **two sections**.

## 1. Replace the node totals loop

Your current logic is still summing the selected color metric:

```python
node_totals[row["pcpname"]] += row[color_metric]
node_totals[row["providername"]] += row[color_metric]
```

That breaks when `color_metric = cpc2`.

Replace the whole **Calculate totals** section with this:

```python
# Aggregate PCP-provider pairs first
pair_df = (
    filtered_df
    .groupby(["pcpname", "providername"], as_index=False)
    .agg(
        cost=("cost", "sum"),
        claims=("claims", "sum"),
        members=("members", "sum")
    )
)

pair_df["cpc2"] = pair_df["cost"] / pair_df["claims"]
pair_df["cpum2"] = pair_df["cost"] / pair_df["members"]

# Build node-level metric table
pcp_nodes = (
    pair_df
    .groupby("pcpname", as_index=False)
    .agg(cost=("cost", "sum"), claims=("claims", "sum"), members=("members", "sum"))
    .rename(columns={"pcpname": "node"})
)

provider_nodes = (
    pair_df
    .groupby("providername", as_index=False)
    .agg(cost=("cost", "sum"), claims=("claims", "sum"), members=("members", "sum"))
    .rename(columns={"providername": "node"})
)

node_df = pd.concat([pcp_nodes, provider_nodes], ignore_index=True)

node_df["cpc2"] = node_df["cost"] / node_df["claims"]
node_df["cpum2"] = node_df["cost"] / node_df["members"]

node_totals = dict(zip(node_df["node"], node_df[color_metric]))
```

## 2. Change the Sankey link source/value

Right now you are still using `filtered_df` here:

```python
source=filtered_df["pcpname"].map(node_map),
target=filtered_df["providername"].map(node_map),
value=filtered_df["cost"],
```

Replace that with `pair_df`:

```python
source=pair_df["pcpname"].map(node_map),
target=pair_df["providername"].map(node_map),
value=pair_df["claims"],  # ribbon width = referral volume
```

So the link section becomes:

```python
link=dict(
    source=pair_df["pcpname"].map(node_map),
    target=pair_df["providername"].map(node_map),
    value=pair_df["claims"],
    color="rgba(200, 200, 200, 0.4)"
)
```

## One more important fix

Move this line **after** `pair_df` is created:

```python
all_nodes = list(pd.concat([pair_df["pcpname"], pair_df["providername"]]).unique())
node_map = {name: i for i, name in enumerate(all_nodes)}
```

## Final structure should be

```python
filtered_df = df[df["pcpname"].isin(selected_pcps)].copy()

pair_df = (
    filtered_df
    .groupby(["pcpname", "providername"], as_index=False)
    .agg(
        cost=("cost", "sum"),
        claims=("claims", "sum"),
        members=("members", "sum")
    )
)

pair_df["cpc2"] = pair_df["cost"] / pair_df["claims"]
pair_df["cpum2"] = pair_df["cost"] / pair_df["members"]

all_nodes = list(pd.concat([pair_df["pcpname"], pair_df["providername"]]).unique())
node_map = {name: i for i, name in enumerate(all_nodes)}

# Build node totals for color
# Then use pair_df in the Sankey
```

That gets you the right behavior:

```text
Ribbon thickness = referral volume
Node color = normalized cost intensity
```

Your current version is still letting ratio math sneak into a summing machine. Sankey is basically a blender. Ratios don’t survive blender mode.

---
---
---
Below is a full replacement for `sankey_app.py`. It accounts for the transcript discussion:

* **Ribbon thickness** = referral volume, default `claims`
* **Node/ribbon color** = normalized cost intensity, default recalculated `CPC`
* **CPC is recalculated correctly** as `SUM(cost) / SUM(claims)`
* **Procedure-adjusted excess cost** is included when `procedurecategory` or `procedurecode` exists
* **Outlier color skew** is controlled with a percentile cap
* **Trend check** appears automatically when a `year` field exists

````python
import re
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.colors import sample_colorscale

st.set_page_config(page_title="Radiology Referral Sankey", layout="wide")


# ============================================================
# Helpers
# ============================================================

def clean_col(x):
    return re.sub(r"[^a-z0-9]+", "", str(x).strip().lower())


ALIASES = {
    "pcpname": ["pcpname", "pcp name", "pcp", "referring provider", "primary care provider"],
    "providername": ["providername", "provider name", "radiologist", "specialist", "rendering provider"],
    "providergroup": ["provider group", "providergroup", "radiology group", "tin name", "billing tin"],
    "providerspecialty": ["provider specialty", "providerspecialty", "specialty", "taxonomy"],
    "cost": ["cost", "cost(sum)", "costsum", "total cost", "paid amount", "allowed amount", "dollars"],
    "claims": ["claims", "claim count", "claimcount", "number of claims", "claims_sum"],
    "members": ["members", "member count", "membercount", "unique members", "uniquemembers"],
    "memberid": ["member id", "memberid", "patient id", "patientid", "person id", "personid"],
    "procedurecode": ["procedure code", "procedurecode", "proc code", "proccode", "cpt", "hcpcs"],
    "procedurecategory": ["procedure category", "procedurecategory", "proc category", "service category", "modality"],
    "year": ["year", "service year", "claim year", "dos year"],
    "servicedate": ["service date", "servicedate", "date of service", "dos", "claim date"],
}


def standardize_columns(df):
    lookup = {}
    for standard, aliases in ALIASES.items():
        for a in aliases:
            lookup[clean_col(a)] = standard

    rename = {}
    used = set()

    for c in df.columns:
        standard = lookup.get(clean_col(c))
        if standard and standard not in used:
            rename[c] = standard
            used.add(standard)

    df = df.rename(columns=rename).copy()

    if "year" not in df.columns and "servicedate" in df.columns:
        df["servicedate"] = pd.to_datetime(df["servicedate"], errors="coerce")
        df["year"] = df["servicedate"].dt.year

    return df


def load_file(file):
    name = getattr(file, "name", str(file)).lower()

    if name.endswith(".csv"):
        return pd.read_csv(file)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(file)

    raise ValueError("Use a CSV, XLSX, or XLS file.")


def to_num(s):
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")

    return pd.to_numeric(
        s.astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .str.replace("%", "", regex=False),
        errors="coerce"
    )


def safe_div(a, b):
    if hasattr(b, "replace"):
        b = b.replace(0, np.nan)
    elif b == 0:
        b = np.nan

    return a / b


def fmt_money(x):
    return "N/A" if pd.isna(x) else f"${x:,.0f}"


def fmt_num(x):
    return "N/A" if pd.isna(x) else f"{x:,.0f}"


METRIC_LABELS = {
    "cost": "Total Cost",
    "claims": "Claims",
    "members": "Members",
    "cpc2": "Cost per Claim, recalculated",
    "cpum2": "Cost per Member, recalculated",
    "expected_cost": "Expected Cost",
    "excess_cost": "Excess Cost vs Benchmark",
    "cost_ratio": "Cost Ratio vs Benchmark",
    "none": "None, gray",
}


def label_metric(x):
    return METRIC_LABELS.get(x, x)


def colors_from_metric(values, percentile=95, opacity=0.9, min_strength=0.12):
    s = (
        pd.to_numeric(pd.Series(values), errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
    )

    positive = s[s > 0]

    if positive.empty:
        return [f"rgba(180,180,180,{opacity})"] * len(s)

    cap = np.nanpercentile(positive, percentile)

    if pd.isna(cap) or cap <= 0:
        cap = positive.max()

    z = (s / cap).clip(0, 1)
    z = min_strength + z * (1 - min_strength)

    rgb = sample_colorscale("Blues", z.tolist())

    return [
        c.replace("rgb(", "rgba(").replace(")", f", {opacity})")
        if c.startswith("rgb(")
        else c
        for c in rgb
    ]


# ============================================================
# Core calculation
# ============================================================

def aggregate_pairs(df, source_col, target_col, member_id_col=None):
    agg_spec = {
        "cost": ("cost", "sum"),
        "claims": ("claims", "sum"),
    }

    if member_id_col and member_id_col in df.columns:
        agg_spec["members"] = (member_id_col, "nunique")
    elif "members" in df.columns:
        agg_spec["members"] = ("members", "sum")

    pair_df = (
        df.groupby([source_col, target_col], dropna=False, as_index=False)
        .agg(**agg_spec)
    )

    if "members" not in pair_df.columns:
        pair_df["members"] = np.nan

    # Correct ratio math. Do not sum CPC.
    pair_df["cpc2"] = safe_div(pair_df["cost"], pair_df["claims"])
    pair_df["cpum2"] = safe_div(pair_df["cost"], pair_df["members"])

    return pair_df


def add_context(pair_df, filtered_df, source_col, target_col, procedure_col=None, specialty_col=None):
    out = pair_df.copy()

    if procedure_col and procedure_col in filtered_df.columns:
        tmp = filtered_df.copy()
        tmp["_proc"] = tmp[procedure_col].fillna("Unknown").astype(str)

        proc_rank = (
            tmp.groupby([source_col, target_col, "_proc"], dropna=False, as_index=False)
            .agg(proc_claims=("claims", "sum"))
            .sort_values([source_col, target_col, "proc_claims"], ascending=[True, True, False])
        )

        top_proc = (
            proc_rank.groupby([source_col, target_col], dropna=False)
            .head(3)
            .groupby([source_col, target_col], dropna=False)["_proc"]
            .apply(lambda x: ", ".join(x.tolist()))
            .reset_index(name="top_procedures")
        )

        out = out.merge(top_proc, on=[source_col, target_col], how="left")
    else:
        out["top_procedures"] = "N/A"

    if specialty_col and specialty_col in filtered_df.columns:
        spec = (
            filtered_df.assign(_spec=filtered_df[specialty_col].fillna("Unknown").astype(str))
            .groupby([source_col, target_col], dropna=False)["_spec"]
            .agg(lambda x: ", ".join(sorted(set(x))[:3]))
            .reset_index(name="provider_specialty")
        )

        out = out.merge(spec, on=[source_col, target_col], how="left")
    else:
        out["provider_specialty"] = "N/A"

    return out


def add_benchmark(pair_df, filtered_df, benchmark_df, source_col, target_col, procedure_col=None):
    """
    If procedure is available:
        benchmark CPC by procedure = SUM(cost) / SUM(claims)
        expected cost = SUM(pair procedure claims * procedure benchmark CPC)

    If not:
        expected cost = pair claims * overall CPC
    """
    out = pair_df.copy()

    if procedure_col and procedure_col in filtered_df.columns and procedure_col in benchmark_df.columns:
        proc_bench = (
            benchmark_df.groupby(procedure_col, dropna=False, as_index=False)
            .agg(
                bench_cost=("cost", "sum"),
                bench_claims=("claims", "sum")
            )
        )

        proc_bench["bench_cpc"] = safe_div(
            proc_bench["bench_cost"],
            proc_bench["bench_claims"]
        )

        pair_proc = (
            filtered_df.groupby([source_col, target_col, procedure_col], dropna=False, as_index=False)
            .agg(
                pair_proc_cost=("cost", "sum"),
                pair_proc_claims=("claims", "sum")
            )
            .merge(
                proc_bench[[procedure_col, "bench_cpc"]],
                on=procedure_col,
                how="left"
            )
        )

        pair_proc["expected_cost"] = pair_proc["pair_proc_claims"] * pair_proc["bench_cpc"]

        adj = (
            pair_proc.groupby([source_col, target_col], dropna=False, as_index=False)
            .agg(expected_cost=("expected_cost", "sum"))
        )

        out = out.merge(adj, on=[source_col, target_col], how="left")
        out["benchmark_method"] = f"Procedure-adjusted using {procedure_col}"

    else:
        overall_cpc = safe_div(benchmark_df["cost"].sum(), benchmark_df["claims"].sum())
        out["expected_cost"] = out["claims"] * overall_cpc
        out["benchmark_method"] = "Overall CPC benchmark"

    out["excess_cost"] = out["cost"] - out["expected_cost"]
    out["cost_ratio"] = safe_div(out["cost"], out["expected_cost"])

    return out


def build_nodes(pair_df, source_col, target_col):
    pcp_nodes = (
        pair_df.groupby(source_col, dropna=False, as_index=False)
        .agg(
            cost=("cost", "sum"),
            claims=("claims", "sum"),
            members=("members", "sum")
        )
        .rename(columns={source_col: "label"})
    )

    pcp_nodes["role"] = "PCP"
    pcp_nodes["node_id"] = "PCP::" + pcp_nodes["label"].astype(str)

    provider_nodes = (
        pair_df.groupby(target_col, dropna=False, as_index=False)
        .agg(
            cost=("cost", "sum"),
            claims=("claims", "sum"),
            members=("members", "sum")
        )
        .rename(columns={target_col: "label"})
    )

    provider_nodes["role"] = "Provider"
    provider_nodes["node_id"] = "PROVIDER::" + provider_nodes["label"].astype(str)

    node_df = pd.concat([pcp_nodes, provider_nodes], ignore_index=True)

    node_df["cpc2"] = safe_div(node_df["cost"], node_df["claims"])
    node_df["cpum2"] = safe_div(node_df["cost"], node_df["members"])

    return node_df


# ============================================================
# Plot
# ============================================================

def make_sankey(
    pair_df,
    source_col,
    target_col,
    flow_metric,
    node_color_metric,
    link_color_metric,
    color_cap_percentile,
    height,
    node_pad,
    node_thickness
):
    node_df = build_nodes(pair_df, source_col, target_col)

    node_map = {
        node_id: i
        for i, node_id in enumerate(node_df["node_id"])
    }

    source_ids = "PCP::" + pair_df[source_col].astype(str)
    target_ids = "PROVIDER::" + pair_df[target_col].astype(str)

    sources = source_ids.map(node_map).tolist()
    targets = target_ids.map(node_map).tolist()

    node_colors = colors_from_metric(
        node_df[node_color_metric],
        percentile=color_cap_percentile,
        opacity=0.95
    )

    if link_color_metric == "none":
        link_colors = ["rgba(150,150,150,0.28)"] * len(pair_df)
    else:
        link_colors = colors_from_metric(
            pair_df[link_color_metric],
            percentile=color_cap_percentile,
            opacity=0.45
        )

    node_customdata = np.column_stack([
        node_df["role"].astype(str),
        node_df["cost"].fillna(0),
        node_df["claims"].fillna(0),
        node_df["members"].fillna(0),
        node_df["cpc2"].fillna(0),
        node_df["cpum2"].fillna(0),
    ])

    link_customdata = np.column_stack([
        pair_df[source_col].astype(str),
        pair_df[target_col].astype(str),
        pair_df["cost"].fillna(0),
        pair_df["claims"].fillna(0),
        pair_df["members"].fillna(0),
        pair_df["cpc2"].fillna(0),
        pair_df["cpum2"].fillna(0),
        pair_df["expected_cost"].fillna(0),
        pair_df["excess_cost"].fillna(0),
        pair_df["cost_ratio"].fillna(0),
        pair_df["top_procedures"].fillna("N/A").astype(str),
        pair_df["provider_specialty"].fillna("N/A").astype(str),
    ])

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            valueformat=",.0f",
            node=dict(
                pad=node_pad,
                thickness=node_thickness,
                label=node_df["label"].astype(str).tolist(),
                color=node_colors,
                line=dict(color="rgba(30,30,30,0.35)", width=0.5),
                customdata=node_customdata,
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Role: %{customdata[0]}<br>"
                    "Total cost: $%{customdata[1]:,.0f}<br>"
                    "Claims: %{customdata[2]:,.0f}<br>"
                    "Members: %{customdata[3]:,.0f}<br>"
                    "CPC: $%{customdata[4]:,.2f}<br>"
                    "CPUM: $%{customdata[5]:,.2f}"
                    "<extra></extra>"
                ),
            ),
            link=dict(
                source=sources,
                target=targets,
                value=pair_df[flow_metric].fillna(0).tolist(),
                color=link_colors,
                customdata=link_customdata,
                hovertemplate=(
                    "<b>%{customdata[0]} → %{customdata[1]}</b><br>"
                    f"Ribbon width: {label_metric(flow_metric)} = "
                    "%{value:,.0f}<br>"
                    "Total cost: $%{customdata[2]:,.0f}<br>"
                    "Claims: %{customdata[3]:,.0f}<br>"
                    "Members: %{customdata[4]:,.0f}<br>"
                    "CPC: $%{customdata[5]:,.2f}<br>"
                    "CPUM: $%{customdata[6]:,.2f}<br>"
                    "Expected cost: $%{customdata[7]:,.0f}<br>"
                    "Excess cost: $%{customdata[8]:,.0f}<br>"
                    "Cost ratio: %{customdata[9]:.2f}x<br>"
                    "Top procedures: %{customdata[10]}<br>"
                    "Specialty: %{customdata[11]}"
                    "<extra></extra>"
                ),
            ),
        )
    )

    fig.update_layout(
        title=(
            "Radiology Referral Sankey"
            f"<br><sup>Width = {label_metric(flow_metric)}. "
            f"Node color = {label_metric(node_color_metric)}. "
            f"Ribbon color = {label_metric(link_color_metric)}.</sup>"
        ),
        height=height,
        font=dict(size=11),
        margin=dict(l=10, r=10, t=70, b=10),
    )

    return fig


# ============================================================
# Trend
# ============================================================

def make_trend(filtered_df, source_col, target_col, year_col, min_claims):
    years = sorted(filtered_df[year_col].dropna().astype(int).unique())

    if len(years) < 2:
        return None

    prior_year, current_year = years[-2], years[-1]

    y = (
        filtered_df[filtered_df[year_col].astype(int).isin([prior_year, current_year])]
        .groupby([source_col, target_col, year_col], dropna=False, as_index=False)
        .agg(
            cost=("cost", "sum"),
            claims=("claims", "sum")
        )
    )

    y["cpc2"] = safe_div(y["cost"], y["claims"])

    prior = (
        y[y[year_col].astype(int) == prior_year]
        .rename(columns={
            "cost": "prior_cost",
            "claims": "prior_claims",
            "cpc2": "prior_cpc"
        })
        [[source_col, target_col, "prior_cost", "prior_claims", "prior_cpc"]]
    )

    current = (
        y[y[year_col].astype(int) == current_year]
        .rename(columns={
            "cost": "current_cost",
            "claims": "current_claims",
            "cpc2": "current_cpc"
        })
        [[source_col, target_col, "current_cost", "current_claims", "current_cpc"]]
    )

    trend = current.merge(prior, on=[source_col, target_col], how="left")

    trend["cpc_delta"] = trend["current_cpc"] - trend["prior_cpc"]
    trend["cpc_pct_change"] = safe_div(trend["cpc_delta"], trend["prior_cpc"])
    trend["prior_year"] = prior_year
    trend["current_year"] = current_year

    trend = trend[trend["current_claims"].fillna(0) >= min_claims]

    return trend.sort_values(["cpc_delta", "current_claims"], ascending=[False, False])


# ============================================================
# Main app
# ============================================================

def build_plotly_s1(file=None):
    st.title("Radiology PCP to Provider Referral Optimization")

    st.caption(
        "Ribbon thickness shows referral volume. Color shows normalized cost intensity. "
        "CPC and CPUM are recalculated after filters, not summed."
    )

    if file is None:
        st.info("Upload a CSV or Excel file from the sidebar.")
        return

    raw = load_file(file)
    df = standardize_columns(raw)

    required = ["pcpname", "providername", "cost"]
    missing = [c for c in required if c not in df.columns]

    if missing:
        st.error(f"Missing required columns after standardization: {missing}")
        st.write("Columns found:", list(raw.columns))
        return

    if "claims" not in df.columns:
        df["claims"] = 1
        st.warning("No claims column found. Each row is being counted as one claim.")

    for c in ["cost", "claims", "members", "year"]:
        if c in df.columns:
            df[c] = to_num(df[c])

    df["pcpname"] = df["pcpname"].fillna("Unknown PCP").astype(str)
    df["providername"] = df["providername"].fillna("Unknown Provider").astype(str)

    df = df[df["cost"].notna()].copy()
    df["claims"] = df["claims"].fillna(0)

    source_col = "pcpname"
    target_col = "providername"

    member_id_col = "memberid" if "memberid" in df.columns else None
    has_members = "members" in df.columns or member_id_col is not None
    specialty_col = "providerspecialty" if "providerspecialty" in df.columns else None
    year_col = "year" if "year" in df.columns else None

    procedure_candidates = [
        c for c in ["procedurecategory", "procedurecode"]
        if c in df.columns
    ]

    with st.sidebar:
        st.header("Dashboard Controls")

        st.subheader("Benchmark and Filters")

        procedure_col = None

        if procedure_candidates:
            procedure_col = st.selectbox(
                "Procedure field for apples-to-apples adjustment",
                ["None"] + procedure_candidates,
                index=1
            )
            procedure_col = None if procedure_col == "None" else procedure_col
        else:
            st.info("No procedure field found. Benchmark will use overall CPC.")

        global_df = df.copy()

        if year_col:
            years = sorted(global_df[year_col].dropna().astype(int).unique())

            selected_years = st.multiselect(
                "Year",
                years,
                default=years
            )

            if selected_years:
                global_df = global_df[
                    global_df[year_col].astype("Int64").isin(selected_years)
                ]

        if procedure_col:
            proc_vals = sorted(global_df[procedure_col].dropna().astype(str).unique())

            selected_proc = st.multiselect(
                f"{procedure_col}",
                proc_vals,
                default=proc_vals
            )

            if selected_proc:
                global_df = global_df[
                    global_df[procedure_col].astype(str).isin(selected_proc)
                ]

        if specialty_col:
            specs = sorted(global_df[specialty_col].dropna().astype(str).unique())

            selected_specs = st.multiselect(
                "Provider specialty",
                specs,
                default=specs
            )

            if selected_specs:
                global_df = global_df[
                    global_df[specialty_col].astype(str).isin(selected_specs)
                ]

        st.subheader("PCP and Provider Selection")

        pcp_volume = (
            global_df.groupby(source_col)["claims"]
            .sum()
            .sort_values(ascending=False)
        )

        all_pcps = pcp_volume.index.astype(str).tolist()

        pcp_mode = st.radio(
            "PCP selection",
            ["Top N by claims", "Manual"],
            horizontal=True
        )

        if pcp_mode == "Top N by claims":
            n = st.slider(
                "Number of PCPs",
                1,
                max(1, min(100, len(all_pcps))),
                min(25, max(1, len(all_pcps)))
            )
            selected_pcps = all_pcps[:n]
        else:
            selected_pcps = st.multiselect(
                "PCPs",
                all_pcps,
                default=all_pcps[:min(25, len(all_pcps))]
            )

        provider_volume = (
            global_df.groupby(target_col)["claims"]
            .sum()
            .sort_values(ascending=False)
        )

        all_providers = provider_volume.index.astype(str).tolist()

        restrict_providers = st.checkbox(
            "Restrict providers manually",
            value=False
        )

        if restrict_providers:
            selected_providers = st.multiselect(
                "Providers",
                all_providers,
                default=all_providers[:min(50, len(all_providers))]
            )
        else:
            selected_providers = all_providers

        st.subheader("Visual Metrics")

        flow_options = ["claims", "cost"]

        if has_members:
            flow_options.insert(1, "members")

        flow_metric = st.selectbox(
            "Ribbon width",
            flow_options,
            index=0,
            format_func=label_metric
        )

        node_color_options = ["cost", "claims", "cpc2"]

        if has_members:
            node_color_options.insert(2, "members")
            node_color_options.append("cpum2")

        node_color_metric = st.selectbox(
            "Node color",
            node_color_options,
            index=node_color_options.index("cpc2"),
            format_func=label_metric
        )

        link_color_options = [
            "none",
            "cost",
            "claims",
            "cpc2",
            "excess_cost",
            "cost_ratio"
        ]

        if has_members:
            link_color_options.insert(3, "members")
            link_color_options.append("cpum2")

        link_color_metric = st.selectbox(
            "Ribbon color",
            link_color_options,
            index=link_color_options.index("cpc2"),
            format_func=label_metric
        )

        min_claims = st.slider(
            "Minimum claims per PCP/provider pair",
            0,
            100,
            3
        )

        max_links = st.slider(
            "Maximum visible links",
            25,
            3500,
            500,
            step=25
        )

        color_cap = st.slider(
            "Color scale cap percentile",
            80,
            100,
            95
        )

        st.subheader("Layout")

        height = st.slider(
            "Chart height",
            500,
            1800,
            900,
            step=50
        )

        node_pad = st.slider(
            "Node padding",
            5,
            50,
            15
        )

        node_thickness = st.slider(
            "Node thickness",
            5,
            50,
            25
        )

    filtered_df = global_df[
        global_df[source_col].astype(str).isin(selected_pcps)
        & global_df[target_col].astype(str).isin(selected_providers)
    ].copy()

    if filtered_df.empty:
        st.warning("No rows remain after filters.")
        return

    pair_df = aggregate_pairs(
        filtered_df,
        source_col,
        target_col,
        member_id_col
    )

    pair_df = add_context(
        pair_df,
        filtered_df,
        source_col,
        target_col,
        procedure_col,
        specialty_col
    )

    pair_df = add_benchmark(
        pair_df,
        filtered_df,
        global_df,
        source_col,
        target_col,
        procedure_col
    )

    pair_df = pair_df.replace([np.inf, -np.inf], np.nan)

    pair_df = pair_df[
        pair_df["claims"].fillna(0) >= min_claims
    ].copy()

    if pair_df.empty:
        st.warning("No PCP/provider pairs meet the minimum claims threshold.")
        return

    pair_plot = (
        pair_df.sort_values(flow_metric, ascending=False)
        .head(max_links)
        .copy()
    )

    if len(pair_df) > len(pair_plot):
        st.warning(
            f"Showing top {len(pair_plot):,} links by {label_metric(flow_metric)} "
            f"out of {len(pair_df):,} eligible links."
        )

    total_cost = pair_df["cost"].sum()
    total_claims = pair_df["claims"].sum()

    total_members = (
        pair_df["members"].sum()
        if pair_df["members"].notna().any()
        else np.nan
    )

    overall_cpc = safe_div(total_cost, total_claims)

    k1, k2, k3, k4, k5 = st.columns(5)

    k1.metric("Total Cost", fmt_money(total_cost))
    k2.metric("Claims", fmt_num(total_claims))
    k3.metric("Members", fmt_num(total_members))
    k4.metric("CPC", f"${overall_cpc:,.2f}" if pd.notna(overall_cpc) else "N/A")
    k5.metric("Visible Links", f"{len(pair_plot):,}")

    st.markdown(
        "**Read this correctly:** thick plus dark means high volume and high normalized cost. "
        "Thin plus dark means costly but probably lower priority. "
        "Procedure adjustment helps avoid blaming specialty mix."
    )

    fig = make_sankey(
        pair_plot,
        source_col,
        target_col,
        flow_metric,
        node_color_metric,
        link_color_metric,
        color_cap,
        height,
        node_pad,
        node_thickness
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("High-Cost Referral Opportunities")

    view_cols = [
        source_col,
        target_col,
        "cost",
        "claims",
        "members",
        "cpc2",
        "cpum2",
        "expected_cost",
        "excess_cost",
        "cost_ratio",
        "top_procedures",
        "provider_specialty",
        "benchmark_method"
    ]

    view_cols = [
        c for c in view_cols
        if c in pair_df.columns
    ]

    opportunity = (
        pair_df[view_cols]
        .sort_values(["excess_cost", "claims"], ascending=[False, False])
        .head(50)
    )

    st.dataframe(
        opportunity.style.format({
            "cost": "${:,.0f}",
            "claims": "{:,.0f}",
            "members": "{:,.0f}",
            "cpc2": "${:,.2f}",
            "cpum2": "${:,.2f}",
            "expected_cost": "${:,.0f}",
            "excess_cost": "${:,.0f}",
            "cost_ratio": "{:,.2f}x",
        }),
        use_container_width=True,
        hide_index=True
    )

    if year_col:
        st.subheader("Trend Check")

        trend = make_trend(
            filtered_df,
            source_col,
            target_col,
            year_col,
            max(1, min_claims)
        )

        if trend is None or trend.empty:
            st.info("Trend requires at least two years after filters.")
        else:
            trend_view = trend[[
                source_col,
                target_col,
                "prior_year",
                "current_year",
                "prior_claims",
                "current_claims",
                "prior_cpc",
                "current_cpc",
                "cpc_delta",
                "cpc_pct_change"
            ]].head(30)

            st.dataframe(
                trend_view.style.format({
                    "prior_claims": "{:,.0f}",
                    "current_claims": "{:,.0f}",
                    "prior_cpc": "${:,.2f}",
                    "current_cpc": "${:,.2f}",
                    "cpc_delta": "${:,.2f}",
                    "cpc_pct_change": "{:.1%}",
                }),
                use_container_width=True,
                hide_index=True
            )

    with st.expander("Calculation notes"):
        st.markdown(
            """
### Main calculations

```text
CPC = SUM(Cost) / SUM(Claims)
CPUM = SUM(Cost) / SUM(Members)
````

Never calculate PCP cost intensity by summing CPC values.

```text
Wrong:   PCP CPC = CPC A + CPC B + CPC C
Correct: PCP CPC = SUM(Cost across referrals) / SUM(Claims across referrals)
```

### Procedure-adjusted benchmark

When a procedure field is available:

```text
Procedure Benchmark CPC = SUM(Cost by Procedure) / SUM(Claims by Procedure)
Expected Cost = SUM(Pair Claims by Procedure * Procedure Benchmark CPC)
Excess Cost = Actual Cost - Expected Cost
Cost Ratio = Actual Cost / Expected Cost
```

This is the guardrail for oncology radiology or other specialized providers. It prevents the visual from labeling specialized work as inefficient just because the procedure mix is expensive.
"""
)

# ============================================================

# App entry

# ============================================================

with st.sidebar:
st.header("Data")

```
uploaded = st.file_uploader(
    "Upload referral file",
    type=["csv", "xlsx", "xls"]
)

path = st.text_input(
    "Or local file path",
    value=""
)
```

file_input = uploaded if uploaded is not None else (
path.strip() if path.strip() else None
)

try:
build_plotly_s1(file_input)
except Exception as e:
st.error("The app hit an error.")
st.exception(e)

````

Run it with:

```bash
streamlit run sankey_app.py
````

The biggest change from your current code is this: the Sankey is no longer summing `cpc` or `cpc2`. It aggregates `cost` and `claims` first, then recalculates the ratio at the pair and node levels. That is the fix.

