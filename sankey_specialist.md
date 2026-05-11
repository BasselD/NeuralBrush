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
Below is a full `sankey_app.py` version that accounts for the transcript:

* **Ribbon thickness** = referral volume, default `claims`
* **Node color** = normalized cost intensity, default `cost per claim`
* **No summing ratios**
* **CPC/CPUM calculated after filters**
* **Outlier color cap** so one provider does not turn the whole chart into navy soup
* **Optional filters** for year, procedure category, procedure code, specialty
* **Procedure mix included** so oncology/specialty radiology does not get unfairly compared to routine imaging
* **Trend table included** if a `year` column exists

Copy this into `sankey_app.py`.

````python
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from pathlib import Path


# ============================================================
# Page setup
# ============================================================

st.set_page_config(
    page_title="Radiology Referral Sankey",
    page_icon="🩻",
    layout="wide"
)


# ============================================================
# Helper functions
# ============================================================

def clean_col(col: str) -> str:
    """
    Standardizes a column name for matching.
    Example:
        'Cost(SUM)' -> 'costsum'
        'Provider Name' -> 'providername'
    """
    return "".join(ch for ch in str(col).lower().strip() if ch.isalnum())


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renames common column variations to expected canonical names.

    Required canonical columns:
        pcpname
        providername
        cost
        claims

    Optional canonical columns:
        members
        procedurecode
        procedurecategory
        specialty
        year
    """

    aliases = {
        "pcpname": [
            "pcpname", "pcp", "pcp_name", "pcp name", "pcpfullname",
            "pcpprovidername", "pcp provider name", "referringpcp"
        ],
        "providername": [
            "providername", "provider name", "specialistname", "specialist name",
            "radiologistname", "radiologist name", "renderingprovidername",
            "rendering provider name", "referredprovider", "referred provider"
        ],
        "cost": [
            "cost", "costsum", "cost_sum", "cost sum", "totalcost",
            "total cost", "paidamount", "paid amount", "allowedamount",
            "allowed amount"
        ],
        "claims": [
            "claims", "claimcount", "claim count", "claimcnt", "claim cnt",
            "visits", "procedures", "procedurecount", "procedure count"
        ],
        "members": [
            "members", "uniquemembers", "unique members", "membercount",
            "member count", "mbrcnt", "mbr cnt"
        ],
        "procedurecode": [
            "procedurecode", "procedure code", "cpt", "cptcode",
            "cpt code", "hcpcs", "hcpcscode", "proc_cd", "proccd"
        ],
        "procedurecategory": [
            "procedurecategory", "procedure category", "proccategory",
            "proc category", "modality", "servicecategory", "service category"
        ],
        "specialty": [
            "specialty", "providerspecialty", "provider specialty",
            "taxonomy", "providertaxonomy", "provider taxonomy"
        ],
        "year": [
            "year", "serviceyear", "service year", "claimyear",
            "claim year", "paidyear", "paid year"
        ],
    }

    cleaned_to_original = {clean_col(c): c for c in df.columns}
    rename_map = {}

    for canonical, possible_names in aliases.items():
        for possible in possible_names:
            possible_clean = clean_col(possible)
            if possible_clean in cleaned_to_original:
                original = cleaned_to_original[possible_clean]
                rename_map[original] = canonical
                break

    return df.rename(columns=rename_map)


def load_data(source) -> pd.DataFrame:
    """
    Loads CSV or Excel.
    """
    if source is None:
        return pd.DataFrame()

    if isinstance(source, str):
        suffix = Path(source).suffix.lower()
    else:
        suffix = Path(source.name).suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(source)

    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(source)

    raise ValueError("Unsupported file type. Use CSV or Excel.")


def to_number(series: pd.Series) -> pd.Series:
    """
    Converts currency/number-like strings into numeric values.
    """
    return (
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace({"": np.nan, "nan": np.nan, "None": np.nan})
        .pipe(pd.to_numeric, errors="coerce")
    )


def safe_divide(numerator, denominator):
    """
    Safe division that returns NaN when denominator is zero.
    """
    denominator = denominator.replace({0: np.nan})
    return numerator / denominator


def prepare_base_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and validates the base referral data.
    """
    df = standardize_columns(df).copy()

    required_cols = ["pcpname", "providername", "cost", "claims"]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        st.error(
            f"Missing required column(s): {missing}. "
            "Expected at least PCP name, provider name, cost, and claims."
        )
        st.stop()

    df["pcpname"] = df["pcpname"].fillna("Unknown PCP").astype(str)
    df["providername"] = df["providername"].fillna("Unknown Provider").astype(str)

    df["cost"] = to_number(df["cost"]).fillna(0)
    df["claims"] = to_number(df["claims"]).fillna(0)

    if "members" in df.columns:
        df["members"] = to_number(df["members"]).fillna(0)
    else:
        df["members"] = np.nan

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    return df


def aggregate_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates the filtered data at PCP-provider level.

    This is the key correction:
        CPC = SUM(cost) / SUM(claims)

    Not:
        SUM(CPC)
    """

    pair_df = (
        df
        .groupby(["pcpname", "providername"], as_index=False, dropna=False)
        .agg(
            cost=("cost", "sum"),
            claims=("claims", "sum"),
            members=("members", "sum")
        )
    )

    pair_df["cpc2"] = safe_divide(pair_df["cost"], pair_df["claims"])
    pair_df["cpum2"] = safe_divide(pair_df["cost"], pair_df["members"])

    pair_df["pcp_node_id"] = "PCP | " + pair_df["pcpname"].astype(str)
    pair_df["provider_node_id"] = "Provider | " + pair_df["providername"].astype(str)

    return pair_df


def add_procedure_mix(pair_df: pd.DataFrame, source_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds top procedure/modality mix per PCP-provider pair if procedure category exists.
    This helps avoid falsely calling specialized providers expensive.
    """

    if "procedurecategory" not in source_df.columns:
        pair_df["top_procedure_mix"] = "Not available"
        return pair_df

    proc_df = (
        source_df
        .groupby(["pcpname", "providername", "procedurecategory"], as_index=False)
        .agg(claims=("claims", "sum"))
        .sort_values(["pcpname", "providername", "claims"], ascending=[True, True, False])
    )

    top_proc = (
        proc_df
        .groupby(["pcpname", "providername"])
        .head(3)
        .assign(
            proc_text=lambda x: x["procedurecategory"].astype(str) + " (" + x["claims"].round(0).astype(int).astype(str) + ")"
        )
        .groupby(["pcpname", "providername"], as_index=False)
        .agg(top_procedure_mix=("proc_text", lambda s: "; ".join(s)))
    )

    pair_df = pair_df.merge(
        top_proc,
        on=["pcpname", "providername"],
        how="left"
    )

    pair_df["top_procedure_mix"] = pair_df["top_procedure_mix"].fillna("Not available")

    return pair_df


def build_node_table(pair_df: pd.DataFrame) -> pd.DataFrame:
    """
    Builds node-level metrics separately for PCPs and providers.

    Important:
        Node CPC = SUM(cost) / SUM(claims)
        Node CPUM = SUM(cost) / SUM(members)
    """

    pcp_nodes = (
        pair_df
        .groupby("pcp_node_id", as_index=False)
        .agg(
            label=("pcpname", "first"),
            cost=("cost", "sum"),
            claims=("claims", "sum"),
            members=("members", "sum")
        )
        .rename(columns={"pcp_node_id": "node_id"})
    )
    pcp_nodes["role"] = "PCP"
    pcp_nodes["display_label"] = "PCP: " + pcp_nodes["label"].astype(str)

    provider_nodes = (
        pair_df
        .groupby("provider_node_id", as_index=False)
        .agg(
            label=("providername", "first"),
            cost=("cost", "sum"),
            claims=("claims", "sum"),
            members=("members", "sum")
        )
        .rename(columns={"provider_node_id": "node_id"})
    )
    provider_nodes["role"] = "Provider"
    provider_nodes["display_label"] = "Rad: " + provider_nodes["label"].astype(str)

    node_df = pd.concat([pcp_nodes, provider_nodes], ignore_index=True)

    node_df["cpc2"] = safe_divide(node_df["cost"], node_df["claims"])
    node_df["cpum2"] = safe_divide(node_df["cost"], node_df["members"])

    return node_df


def make_node_colors(
    values: pd.Series,
    cap_percentile: float = 0.95,
    use_log_scale: bool = False
) -> list:
    """
    Creates blue node colors.

    Color cap prevents one extreme outlier from making everyone else pale.
    """

    values = pd.to_numeric(values, errors="coerce").fillna(0).clip(lower=0)

    positive = values[values > 0]

    if positive.empty:
        return ["rgba(210,210,210,0.75)"] * len(values)

    cap_value = np.quantile(positive, cap_percentile)

    if cap_value <= 0:
        return ["rgba(210,210,210,0.75)"] * len(values)

    scaled = (values / cap_value).clip(0, 1)

    if use_log_scale:
        scaled = np.log1p(scaled * 9) / np.log1p(9)

    # Keep low values visible. Otherwise light blue can look almost white.
    scaled = 0.15 + (scaled * 0.85)

    return sample_colorscale("Blues", scaled.tolist())


def build_sankey_figure(
    pair_df: pd.DataFrame,
    node_df: pd.DataFrame,
    link_metric: str,
    color_metric: str,
    color_cap_percentile: float,
    use_log_scale: bool,
    height: int,
    node_pad: int,
    node_thickness: int
) -> go.Figure:
    """
    Builds the Plotly Sankey visual.

    Link width:
        claims, members, or cost

    Node color:
        cost, claims, members, cpc2, or cpum2
    """

    all_nodes = (
        pd.concat([pair_df["pcp_node_id"], pair_df["provider_node_id"]])
        .drop_duplicates()
        .tolist()
    )

    node_df = (
        node_df
        .set_index("node_id")
        .reindex(all_nodes)
        .reset_index()
    )

    node_map = {node_id: i for i, node_id in enumerate(all_nodes)}

    pair_df = pair_df.copy()
    pair_df["source"] = pair_df["pcp_node_id"].map(node_map)
    pair_df["target"] = pair_df["provider_node_id"].map(node_map)

    pair_df = pair_df[pair_df[link_metric] > 0].copy()

    node_colors = make_node_colors(
        node_df[color_metric],
        cap_percentile=color_cap_percentile,
        use_log_scale=use_log_scale
    )

    node_customdata = np.stack(
        [
            node_df["role"].fillna(""),
            node_df["cost"].fillna(0),
            node_df["claims"].fillna(0),
            node_df["members"].fillna(0),
            node_df["cpc2"].fillna(0),
            node_df["cpum2"].fillna(0),
            node_df[color_metric].fillna(0),
        ],
        axis=-1
    )

    link_customdata = np.stack(
        [
            pair_df["pcpname"].fillna(""),
            pair_df["providername"].fillna(""),
            pair_df["cost"].fillna(0),
            pair_df["claims"].fillna(0),
            pair_df["members"].fillna(0),
            pair_df["cpc2"].fillna(0),
            pair_df["cpum2"].fillna(0),
            pair_df["top_procedure_mix"].fillna("Not available"),
        ],
        axis=-1
    )

    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node=dict(
                    pad=node_pad,
                    thickness=node_thickness,
                    line=dict(color="rgba(30,30,30,0.25)", width=0.5),
                    label=node_df["display_label"].fillna("").tolist(),
                    color=node_colors,
                    customdata=node_customdata,
                    hovertemplate=(
                        "<b>%{label}</b><br>"
                        "Role: %{customdata[0]}<br>"
                        "Total Cost: $%{customdata[1]:,.0f}<br>"
                        "Claims: %{customdata[2]:,.0f}<br>"
                        "Members: %{customdata[3]:,.0f}<br>"
                        "Cost / Claim: $%{customdata[4]:,.2f}<br>"
                        "Cost / Member: $%{customdata[5]:,.2f}<br>"
                        "<extra></extra>"
                    )
                ),
                link=dict(
                    source=pair_df["source"].astype(int),
                    target=pair_df["target"].astype(int),
                    value=pair_df[link_metric],
                    color="rgba(150,150,150,0.35)",
                    customdata=link_customdata,
                    hovertemplate=(
                        "<b>%{customdata[0]} → %{customdata[1]}</b><br>"
                        "Flow Value: %{value:,.0f}<br>"
                        "Total Cost: $%{customdata[2]:,.0f}<br>"
                        "Claims: %{customdata[3]:,.0f}<br>"
                        "Members: %{customdata[4]:,.0f}<br>"
                        "Cost / Claim: $%{customdata[5]:,.2f}<br>"
                        "Cost / Member: $%{customdata[6]:,.2f}<br>"
                        "Top Procedure Mix: %{customdata[7]}<br>"
                        "<extra></extra>"
                    )
                )
            )
        ]
    )

    fig.update_layout(
        title=dict(
            text="PCP → Radiology Provider Referral Flow",
            x=0.01,
            xanchor="left"
        ),
        font=dict(size=11),
        height=height,
        margin=dict(l=10, r=10, t=55, b=10)
    )

    return fig


def build_trend_table(df: pd.DataFrame, min_claims: int = 5) -> pd.DataFrame:
    """
    Optional trend view if year exists.
    Shows whether CPC changed from prior year to current year.
    """

    if "year" not in df.columns:
        return pd.DataFrame()

    trend = (
        df
        .dropna(subset=["year"])
        .groupby(["pcpname", "providername", "year"], as_index=False)
        .agg(
            cost=("cost", "sum"),
            claims=("claims", "sum"),
            members=("members", "sum")
        )
    )

    trend["cpc2"] = safe_divide(trend["cost"], trend["claims"])

    years = sorted(trend["year"].dropna().unique())

    if len(years) < 2:
        return pd.DataFrame()

    prior_year = years[-2]
    current_year = years[-1]

    prior = (
        trend[trend["year"] == prior_year]
        .rename(columns={
            "cost": "prior_cost",
            "claims": "prior_claims",
            "members": "prior_members",
            "cpc2": "prior_cpc"
        })
        [["pcpname", "providername", "prior_cost", "prior_claims", "prior_members", "prior_cpc"]]
    )

    current = (
        trend[trend["year"] == current_year]
        .rename(columns={
            "cost": "current_cost",
            "claims": "current_claims",
            "members": "current_members",
            "cpc2": "current_cpc"
        })
        [["pcpname", "providername", "current_cost", "current_claims", "current_members", "current_cpc"]]
    )

    out = current.merge(prior, on=["pcpname", "providername"], how="left")

    out["cpc_change"] = out["current_cpc"] - out["prior_cpc"]
    out["cpc_change_pct"] = safe_divide(out["cpc_change"], out["prior_cpc"])

    out = out[out["current_claims"] >= min_claims]

    return out.sort_values("cpc_change", ascending=False)


def format_currency_cols(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """
    Returns a copy with rounded numeric values for display.
    """
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").round(2)
    return out


# ============================================================
# App
# ============================================================

st.title("Radiology PCP → Provider Referral Sankey")
st.caption(
    "Thickness shows referral volume. Node color shows normalized cost intensity. "
    "That separation is the whole ballgame."
)

with st.sidebar:
    st.header("Data")

    uploaded_file = st.file_uploader(
        "Upload referral file",
        type=["csv", "xlsx", "xls"]
    )

    local_path = st.text_input(
        "Optional local file path",
        value="",
        placeholder=r"C:\path\to\referrals.xlsx"
    )

    st.divider()

    st.header("Sankey Controls")

    link_metric = st.selectbox(
        "Ribbon thickness",
        options=["claims", "members", "cost"],
        index=0,
        help="Use claims or members to show referral volume. Cost can overstate utilization because high-cost services dominate."
    )

    color_metric = st.selectbox(
        "Color nodes by",
        options=["cpc2", "cpum2", "cost", "claims", "members"],
        index=0,
        help="Use CPC or CPUM to show cost intensity. Avoid summing ratios."
    )

    min_claims = st.slider(
        "Minimum claims per PCP-provider pair",
        min_value=0,
        max_value=100,
        value=5,
        step=1
    )

    max_links = st.slider(
        "Maximum links to render",
        min_value=25,
        max_value=1000,
        value=250,
        step=25,
        help="Large Sankey diagrams get messy fast. 3,500 links is not a visual. It is spaghetti with a medical degree."
    )

    color_cap_percentile = st.slider(
        "Color cap percentile",
        min_value=0.80,
        max_value=1.00,
        value=0.95,
        step=0.01,
        help="Caps extreme values so one outlier does not flatten the rest of the color scale."
    )

    use_log_scale = st.checkbox(
        "Use log color scale",
        value=True,
        help="Helpful when one oncology/specialty provider has extreme cost intensity."
    )

    diagram_height = st.slider(
        "Diagram height",
        min_value=500,
        max_value=1600,
        value=900,
        step=50
    )

    node_pad = st.slider("Node spacing", 5, 40, 15, 1)
    node_thickness = st.slider("Node thickness", 10, 50, 25, 1)


# ============================================================
# Load data
# ============================================================

if uploaded_file is not None:
    raw_df = load_data(uploaded_file)
elif local_path.strip():
    raw_df = load_data(local_path.strip())
else:
    st.info("Upload a CSV or Excel file to begin.")
    st.stop()

df = prepare_base_data(raw_df)

# Remove empty/invalid rows
df = df[
    (df["pcpname"].notna()) &
    (df["providername"].notna()) &
    (df["claims"].fillna(0) >= 0) &
    (df["cost"].fillna(0) >= 0)
].copy()


# ============================================================
# Sidebar filters
# ============================================================

with st.sidebar:
    st.divider()
    st.header("Filters")

    filtered_base = df.copy()

    if "year" in filtered_base.columns:
        year_options = sorted(filtered_base["year"].dropna().unique())
        selected_years = st.multiselect(
            "Year",
            options=year_options,
            default=year_options
        )

        if selected_years:
            filtered_base = filtered_base[filtered_base["year"].isin(selected_years)]

    if "procedurecategory" in filtered_base.columns:
        proc_cat_options = sorted(filtered_base["procedurecategory"].dropna().astype(str).unique())
        selected_proc_cats = st.multiselect(
            "Procedure category / modality",
            options=proc_cat_options,
            default=[]
        )

        if selected_proc_cats:
            filtered_base = filtered_base[
                filtered_base["procedurecategory"].astype(str).isin(selected_proc_cats)
            ]

    if "procedurecode" in filtered_base.columns:
        proc_code_text = st.text_input(
            "Procedure code filter",
            value="",
            placeholder="Example: 70450, 70553"
        )

        if proc_code_text.strip():
            proc_codes = [
                x.strip()
                for x in proc_code_text.split(",")
                if x.strip()
            ]

            filtered_base = filtered_base[
                filtered_base["procedurecode"].astype(str).isin(proc_codes)
            ]

    if "specialty" in filtered_base.columns:
        specialty_options = sorted(filtered_base["specialty"].dropna().astype(str).unique())
        selected_specialties = st.multiselect(
            "Provider specialty",
            options=specialty_options,
            default=[]
        )

        if selected_specialties:
            filtered_base = filtered_base[
                filtered_base["specialty"].astype(str).isin(selected_specialties)
            ]

    pcp_rank = (
        filtered_base
        .groupby("pcpname", as_index=False)
        .agg(rank_value=(link_metric, "sum"))
        .sort_values("rank_value", ascending=False)
    )

    pcp_options = pcp_rank["pcpname"].tolist()
    default_pcps = pcp_options[: min(10, len(pcp_options))]

    selected_pcps = st.multiselect(
        "Filter PCP",
        options=pcp_options,
        default=default_pcps
    )

    if selected_pcps:
        filtered_base = filtered_base[filtered_base["pcpname"].isin(selected_pcps)]


# ============================================================
# Aggregate after filters
# ============================================================

pair_df = aggregate_pairs(filtered_base)
pair_df = add_procedure_mix(pair_df, filtered_base)

# Apply pair-level volume threshold
pair_df = pair_df[pair_df["claims"] >= min_claims].copy()

# Keep the chart readable
if len(pair_df) > max_links:
    st.warning(
        f"Showing top {max_links:,} PCP-provider links by {link_metric}. "
        f"The filtered data has {len(pair_df):,} links."
    )
    pair_df = (
        pair_df
        .sort_values(link_metric, ascending=False)
        .head(max_links)
        .copy()
    )

if pair_df.empty:
    st.warning("No data left after filters. Lower the minimum claims or change filters.")
    st.stop()

node_df = build_node_table(pair_df)


# ============================================================
# KPI summary
# ============================================================

total_cost = pair_df["cost"].sum()
total_claims = pair_df["claims"].sum()
total_members = pair_df["members"].sum()
overall_cpc = total_cost / total_claims if total_claims else np.nan
overall_cpum = total_cost / total_members if total_members else np.nan

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("PCPs", f"{pair_df['pcpname'].nunique():,}")
k2.metric("Radiology Providers", f"{pair_df['providername'].nunique():,}")
k3.metric("Claims", f"{total_claims:,.0f}")
k4.metric("Total Cost", f"${total_cost:,.0f}")
k5.metric("Overall CPC", f"${overall_cpc:,.2f}" if pd.notna(overall_cpc) else "N/A")


# ============================================================
# Sankey visual
# ============================================================

fig = build_sankey_figure(
    pair_df=pair_df,
    node_df=node_df,
    link_metric=link_metric,
    color_metric=color_metric,
    color_cap_percentile=color_cap_percentile,
    use_log_scale=use_log_scale,
    height=diagram_height,
    node_pad=node_pad,
    node_thickness=node_thickness
)

st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Business interpretation sections
# ============================================================

st.subheader("High-cost referral relationships")

table_cols = [
    "pcpname",
    "providername",
    "cost",
    "claims",
    "members",
    "cpc2",
    "cpum2",
    "top_procedure_mix"
]

high_cost_pairs = (
    pair_df
    .sort_values(["cpc2", "claims"], ascending=[False, False])
    [table_cols]
    .head(25)
)

st.dataframe(
    format_currency_cols(
        high_cost_pairs,
        ["cost", "cpc2", "cpum2"]
    ),
    use_container_width=True,
    hide_index=True
)


st.subheader("High-volume referral relationships")

high_volume_pairs = (
    pair_df
    .sort_values(["claims", "cost"], ascending=[False, False])
    [table_cols]
    .head(25)
)

st.dataframe(
    format_currency_cols(
        high_volume_pairs,
        ["cost", "cpc2", "cpum2"]
    ),
    use_container_width=True,
    hide_index=True
)


# ============================================================
# Optional trend view
# ============================================================

if "year" in filtered_base.columns:
    st.subheader("Trend check")

    trend_table = build_trend_table(filtered_base, min_claims=min_claims)

    if trend_table.empty:
        st.caption("Trend table not available. Need at least two years of data after filters.")
    else:
        display_trend = trend_table[
            [
                "pcpname",
                "providername",
                "prior_claims",
                "current_claims",
                "prior_cpc",
                "current_cpc",
                "cpc_change",
                "cpc_change_pct"
            ]
        ].head(25)

        st.dataframe(
            format_currency_cols(
                display_trend,
                ["prior_cpc", "current_cpc", "cpc_change", "cpc_change_pct"]
            ),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# Methodology note
# ============================================================

with st.expander("Methodology"):
    st.markdown(
        """
### What the visual means

| Element | Meaning |
|---|---|
| Ribbon thickness | Referral volume, usually claims or members |
| Node color | Normalized cost intensity, usually cost per claim |
| Tooltip cost | Total allowed/paid cost depending on your input |
| CPC | `SUM(cost) / SUM(claims)` |
| CPUM | `SUM(cost) / SUM(members)` |

### Why CPC is calculated this way

The app does **not** sum pre-calculated CPC values.  
That would be wrong because ratios should not be added together.

Correct:

```text
Cost per Claim = SUM(Cost) / SUM(Claims)
````

Wrong:

```text
Cost per Claim = SUM(Cost per Claim)
```

### Why procedure filtering matters

A provider who performs oncology or specialized radiology may naturally have higher cost intensity.
Before recommending that a PCP redirect referrals, compare providers within similar procedure categories or procedure codes.

Good comparison:

```text
MRI vs MRI
CT vs CT
Routine imaging vs routine imaging
Oncology imaging vs oncology imaging
```

Bad comparison:

```text
Routine X-ray provider vs oncology radiologist
```

```
    """
)
```

````

## Key change from your original code

Your earlier line created one global value across all filtered rows:

```python
filtered_df["cpc2"] = filtered_df["cost"].sum() / filtered_df["claims"].sum()
````

The corrected version calculates CPC at the right grain:

```python
pair_df["cpc2"] = pair_df["cost"] / pair_df["claims"]
```

after grouping by:

```python
["pcpname", "providername"]
```

That is the main fix. Everything else is making the visual behave like an analytic tool instead of a very expensive spaghetti machine.
