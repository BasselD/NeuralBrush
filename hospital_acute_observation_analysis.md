With **these fields**, you can already build a strong **utilization + attribution story**.

## First. What your current field set is good for

You can answer:

* **Which facilities drive the most volume**
* **How Acute vs OBS mix differs by facility**
* **Which hospitalist groups/providers are getting the business**
* **How facility volume is distributed across groups**
* **Which diagnoses are most common overall and by BedType**
* **Whether certain facilities are more concentrated in one group vs spread across many**

## What you cannot fully answer yet

Not with this field set alone:

* LOS
* readmissions
* conversion from OBS to Acute
* time trends, unless you also have service dates
* outcome/performance metrics beyond mix and volume

So this is a **great first wave for volume, mix, attribution, and concentration**. Not yet a full performance scorecard.

---

# Recommended visual set

I would build these 6 first.

## 1. Facility Acute vs OBS mix

**Why:** fastest high-level picture of utilization pattern by hospital.

### Best chart

* stacked horizontal bar
* and a second version as **100% stacked** for rates

### Metric

* `nunique(AuthznKey)`

```python
import pandas as pd
import plotly.express as px

# event-level base
dfe = df.drop_duplicates(subset='AuthznKey').copy()

facility_bed = (
    dfe.groupby(['AdmittingFacilityNameClean', 'BedType'])['AuthznKey']
    .nunique()
    .reset_index(name='events')
)

fig = px.bar(
    facility_bed,
    x='events',
    y='AdmittingFacilityNameClean',
    color='BedType',
    orientation='h',
    title='Authorization Events by Facility and Bed Type',
    barmode='stack'
)
fig.update_layout(height=900, yaxis={'categoryorder': 'total ascending'})
fig.show()
```

### 100% stacked version

```python
facility_bed_pct = facility_bed.copy()
facility_totals = facility_bed_pct.groupby('AdmittingFacilityNameClean')['events'].transform('sum')
facility_bed_pct['pct'] = facility_bed_pct['events'] / facility_totals

fig = px.bar(
    facility_bed_pct,
    x='pct',
    y='AdmittingFacilityNameClean',
    color='BedType',
    orientation='h',
    title='Acute vs OBS Mix by Facility',
    barmode='stack',
    text=facility_bed_pct['pct'].map(lambda x: f'{x:.0%}')
)
fig.update_layout(height=900, xaxis_tickformat='.0%')
fig.show()
```

---

## 2. Hospitalist group share within each facility

**Why:** this is probably the most important business visual for Dr. T.

### Best chart

* **100% stacked horizontal bar**

### Metric

* event share by `AttendingProviderHospitalGroupName_VOP` within each facility

```python
facility_group = (
    dfe.groupby(['AdmittingFacilityNameClean', 'AttendingProviderHospitalGroupName_VOP'])['AuthznKey']
    .nunique()
    .reset_index(name='events')
)

facility_group['AttendingProviderHospitalGroupName_VOP'] = (
    facility_group['AttendingProviderHospitalGroupName_VOP']
    .fillna('Unassigned / Unknown')
)

totals = facility_group.groupby('AdmittingFacilityNameClean')['events'].transform('sum')
facility_group['pct'] = facility_group['events'] / totals

fig = px.bar(
    facility_group,
    x='pct',
    y='AdmittingFacilityNameClean',
    color='AttendingProviderHospitalGroupName_VOP',
    orientation='h',
    title='Hospitalist Group Share by Facility',
    barmode='stack'
)
fig.update_layout(height=950, xaxis_tickformat='.0%')
fig.show()
```

### Why this matters

This tells you:

* who is getting the business
* whether one group dominates a facility
* whether preferred routing is actually happening

---

## 3. Facility × hospitalist group heatmap

**Why:** this gets you a consulting-style comparison slide fast.

### Good metric choices

Pick one per chart:

* event count
* Acute %
* OBS %
* share of facility business

### My favorite

**OBS rate by Facility × Group**, with only high-volume combinations shown.

```python
# count events by facility, group, bedtype
fgb = (
    dfe.groupby(['AdmittingFacilityNameClean', 'AttendingProviderHospitalGroupName_VOP', 'BedType'])['AuthznKey']
    .nunique()
    .reset_index(name='events')
)

pivot = fgb.pivot_table(
    index=['AdmittingFacilityNameClean', 'AttendingProviderHospitalGroupName_VOP'],
    columns='BedType',
    values='events',
    fill_value=0
).reset_index()

pivot['total'] = pivot.get('Acute', 0) + pivot.get('OBS', 0)
pivot = pivot[pivot['total'] >= 10].copy()  # optional volume threshold
pivot['obs_rate'] = pivot.get('OBS', 0) / pivot['total']

heat = pivot.pivot(
    index='AttendingProviderHospitalGroupName_VOP',
    columns='AdmittingFacilityNameClean',
    values='obs_rate'
)

fig = px.imshow(
    heat,
    aspect='auto',
    color_continuous_scale='Blues',
    title='OBS Rate by Facility and Hospitalist Group'
)
fig.update_layout(height=700)
fig.show()
```

### Why this works

This immediately shows:

* where OBS-heavy patterns cluster
* whether a group behaves differently by facility
* which facility-group combos deserve attention

---

## 4. Sankey. Facility → Group → BedType

Yes. With your current fields, this is the best Sankey.

### Why

You currently have:

* facility
* attributed group
* acute/obs

That is enough for a clean flow story.

### Use it for

* top facilities only
* top groups only
* otherwise it turns into pasta

```python
import plotly.graph_objects as go

# keep top facilities and groups to control clutter
top_facilities = (
    dfe['AdmittingFacilityNameClean']
    .value_counts()
    .head(8)
    .index
)

top_groups = (
    dfe['AttendingProviderHospitalGroupName_VOP']
    .fillna('Unassigned / Unknown')
    .value_counts()
    .head(6)
    .index
)

sdf = dfe.copy()
sdf['AttendingProviderHospitalGroupName_VOP'] = sdf['AttendingProviderHospitalGroupName_VOP'].fillna('Unassigned / Unknown')
sdf = sdf[
    sdf['AdmittingFacilityNameClean'].isin(top_facilities) &
    sdf['AttendingProviderHospitalGroupName_VOP'].isin(top_groups)
].copy()

# stage 1: facility -> group
fg = (
    sdf.groupby(['AdmittingFacilityNameClean', 'AttendingProviderHospitalGroupName_VOP'])['AuthznKey']
    .nunique()
    .reset_index(name='value')
)

# stage 2: group -> bedtype
gb = (
    sdf.groupby(['AttendingProviderHospitalGroupName_VOP', 'BedType'])['AuthznKey']
    .nunique()
    .reset_index(name='value')
)

nodes = list(pd.Index(
    list(fg['AdmittingFacilityNameClean'].unique()) +
    list(fg['AttendingProviderHospitalGroupName_VOP'].unique()) +
    list(gb['BedType'].unique())
).unique())

node_map = {n: i for i, n in enumerate(nodes)}

source = [node_map[x] for x in fg['AdmittingFacilityNameClean']] + [node_map[x] for x in gb['AttendingProviderHospitalGroupName_VOP']]
target = [node_map[x] for x in fg['AttendingProviderHospitalGroupName_VOP']] + [node_map[x] for x in gb['BedType']]
value = fg['value'].tolist() + gb['value'].tolist()

fig = go.Figure(go.Sankey(
    node=dict(label=nodes, pad=15, thickness=18),
    link=dict(source=source, target=target, value=value)
))
fig.update_layout(title_text='Flow of Authorization Events: Facility → Hospitalist Group → Bed Type', font_size=11)
fig.show()
```

### Use this as a story chart, not the primary comparison chart.

---

## 5. Provider concentration within hospitalist groups

**Why:** useful to see whether a group is carried by one or two providers, or broadly distributed.

### Best chart

* treemap or packed bubble
* or simpler. horizontal bar by provider, faceted by group

```python
provider_group = (
    dfe.groupby(['AttendingProviderHospitalGroupName_VOP', 'AttendingProviderName'])['AuthznKey']
    .nunique()
    .reset_index(name='events')
)

provider_group['AttendingProviderHospitalGroupName_VOP'] = (
    provider_group['AttendingProviderHospitalGroupName_VOP']
    .fillna('Unassigned / Unknown')
)
provider_group['AttendingProviderName'] = provider_group['AttendingProviderName'].fillna('Unknown Provider')

fig = px.treemap(
    provider_group,
    path=['AttendingProviderHospitalGroupName_VOP', 'AttendingProviderName'],
    values='events',
    title='Provider Concentration Within Hospitalist Groups'
)
fig.show()
```

### Why it matters

This can reveal:

* one provider doing most of the work
* whether the group mapping looks believable
* whether mid-levels are carrying a lot of apparent attribution

---

## 6. Top diagnoses by BedType

**Why:** this gives clinical texture without getting too deep.

### Best chart

* grouped bar for top diagnoses
* or dumbbell if you want a cleaner compare chart

### Important

You will probably want to **collapse rare or vague diagnoses**.

```python
top_dx = dfe['PrimaryDiagnosis'].fillna('Unknown').value_counts().head(12).index

dx_bed = dfe.copy()
dx_bed['PrimaryDiagnosis'] = dx_bed['PrimaryDiagnosis'].fillna('Unknown')
dx_bed['PrimaryDiagnosis'] = dx_bed['PrimaryDiagnosis'].where(
    dx_bed['PrimaryDiagnosis'].isin(top_dx), 'Other'
)

dx_bed = (
    dx_bed.groupby(['PrimaryDiagnosis', 'BedType'])['AuthznKey']
    .nunique()
    .reset_index(name='events')
)

fig = px.bar(
    dx_bed,
    x='events',
    y='PrimaryDiagnosis',
    color='BedType',
    orientation='h',
    barmode='group',
    title='Top Diagnoses by Bed Type'
)
fig.update_layout(height=700, yaxis={'categoryorder': 'total ascending'})
fig.show()
```

---

# Two very useful derived metrics

These are simple and valuable.

## A. Unique members vs unique events

Sometimes a group has many events driven by fewer members.

```python
summary = (
    dfe.groupby(['AdmittingFacilityNameClean', 'AttendingProviderHospitalGroupName_VOP'])
    .agg(
        events=('AuthznKey', 'nunique'),
        members=('MemberID', 'nunique')
    )
    .reset_index()
)

summary['events_per_member'] = summary['events'] / summary['members']
```

### Why this helps

* distinguishes repeat utilization from broad patient reach
* good for an appendix or tooltip

---

## B. Concentration index by facility

This tells you if one group dominates a facility.

```python
shares = facility_group.copy()
shares['share_sq'] = shares['pct'] ** 2

concentration = (
    shares.groupby('AdmittingFacilityNameClean')['share_sq']
    .sum()
    .reset_index(name='hhi_like_index')
    .sort_values('hhi_like_index', ascending=False)
)
```

### Why this matters

* high value = concentrated routing
* low value = fragmented routing
* useful for “who owns this hospital?” style discussions

---

# Best storyboards you can make with your current data

## Storyboard A. Facility utilization

1. stacked bar . facility Acute vs OBS
2. heatmap . OBS rate by facility × group
3. treemap . volume by facility → group

## Storyboard B. Hospitalist attribution

1. 100% stacked bar . group share by facility
2. treemap . provider concentration within groups
3. Sankey . facility → group → BedType

## Storyboard C. Clinical texture

1. top diagnoses overall
2. diagnosis × BedType grouped bars
3. facility-specific diagnosis mix for top 3 hospitals

---

# My blunt recommendation on what to build first

With your fields, the **most insightful first 4 visuals** are:

## 1. 100% stacked bar

**Hospitalist group share by facility**

## 2. Heatmap

**OBS rate by facility × group**

## 3. Sankey

**Facility → Hospitalist Group → BedType**

## 4. Treemap

**Facility → Group volume hierarchy**

That combo gives you:

* business share
* utilization mix
* flow story
* hierarchy / concentration

That is already a strong deck.

---

# A few practical notes

## Use `AuthznKey` as the event unit

Not raw row count.

## Standardize BedType first

Make sure it is only something like:

* `Acute`
* `OBS`

## Fill unknowns intentionally

Do not leave blanks:

* `Unknown Facility`
* `Unassigned Group`
* `Unknown Provider`

## Limit categories for presentation

For charts:

* top 8 to 10 facilities
* top 5 to 8 groups
* top 10 to 12 diagnoses

Everything else becomes `Other`.

---

# If you want a reusable prep block, start here

```python
import pandas as pd
import numpy as np

dfe = df.copy()

# event-level dedupe
dfe = dfe.drop_duplicates(subset='AuthznKey')

# clean key fields
dfe['BedType'] = dfe['BedType'].astype(str).str.strip().str.upper().replace({
    'OBSERVATION': 'OBS',
    'OBS': 'OBS',
    'ACUTE': 'Acute',
    'INPATIENT': 'Acute'
})

dfe['AdmittingFacilityNameClean'] = dfe['AdmittingFacilityNameClean'].fillna('Unknown Facility')
dfe['PrimaryDiagnosis'] = dfe['PrimaryDiagnosis'].fillna('Unknown')
dfe['AttendingProviderName'] = dfe['AttendingProviderName'].fillna('Unknown Provider')
dfe['AttendingProviderHospital_VOP'] = dfe['AttendingProviderHospital_VOP'].fillna('Unknown Hospital')
dfe['AttendingProviderHospitalGroupName_VOP'] = dfe['AttendingProviderHospitalGroupName_VOP'].fillna('Unassigned / Unknown')
```

---

# Bottom line

With this field list, you are in a very good place to build **volume, mix, routing, and attribution** visuals.

The strongest Python visuals for your current dataset are:

* **stacked bars**
* **100% stacked bars**
* **heatmaps**
* **treemaps**
* **Sankey**
* **diagnosis comparison bars**

Once you add:

* admit date
* discharge date
* LOS
* readmit flag
* maybe claim support flag

then the analysis gets much nastier, in a good way.

----
Below is a clean way to build the **actual slide content in Python** from the SQL output.

Assume your Teradata result is loaded into a dataframe called `scorecard_df` with these columns:

* `AdmittingFacilityNameClean`
* `AttendingProviderHospitalGroupName_VOP`
* `acute_events`
* `obs_events`
* `total_events`
* `unique_members`
* `events_per_member`
* `facility_total_events`
* `facility_share_pct`
* `obs_rate_pct`
* `acute_rate_pct`
* `group_rank_in_facility`

---

# 1. Setup and styling

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from textwrap import fill

# ---------- Style ----------
ACCENT = "#002850"         # RGB(0,40,80)
ACCENT_2 = "#3E6C8F"
LIGHT_BLUE = "#9DB7C8"
PALE_BLUE = "#D9E6EE"
OBS_COLOR = "#2CB1BC"
ACUTE_COLOR = ACCENT
GRID = "#D9DDE3"
TEXT = "#243447"
MUTED = "#6B7280"
BG = "white"

plt.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "axes.edgecolor": GRID,
    "axes.labelcolor": TEXT,
    "text.color": TEXT,
    "xtick.color": TEXT,
    "ytick.color": TEXT,
    "font.size": 11,
    "axes.titleweight": "bold",
    "axes.titlesize": 18
})

# ---------- Clean ----------
df = scorecard_df.copy()

df["AdmittingFacilityNameClean"] = df["AdmittingFacilityNameClean"].fillna("Unknown Facility")
df["AttendingProviderHospitalGroupName_VOP"] = df["AttendingProviderHospitalGroupName_VOP"].fillna("Unassigned / Unknown")

# optional: keep only meaningful rows
df = df[df["total_events"] > 0].copy()

# facility order by total volume
facility_order = (
    df.groupby("AdmittingFacilityNameClean")["facility_total_events"]
      .max()
      .sort_values(ascending=True)
      .index
      .tolist()
)

group_order = (
    df.groupby("AttendingProviderHospitalGroupName_VOP")["total_events"]
      .sum()
      .sort_values(ascending=False)
      .index
      .tolist()
)

df["AdmittingFacilityNameClean"] = pd.Categorical(
    df["AdmittingFacilityNameClean"], categories=facility_order, ordered=True
)
df["AttendingProviderHospitalGroupName_VOP"] = pd.Categorical(
    df["AttendingProviderHospitalGroupName_VOP"], categories=group_order, ordered=True
)
```

---

# 2. Helper functions for slide headlines and takeaways

This is the part most people skip, then end up manually typing vague slide titles at midnight.

```python
def top_facility_group_takeaway(data: pd.DataFrame) -> str:
    x = data.sort_values("total_events", ascending=False).iloc[0]
    return (
        f"{x['AttendingProviderHospitalGroupName_VOP']} has the largest identified footprint "
        f"at {x['AdmittingFacilityNameClean']}, with {int(x['total_events'])} events "
        f"representing {x['facility_share_pct']:.0%} of that facility's observed volume."
    )

def highest_obs_takeaway(data: pd.DataFrame, min_events: int = 10) -> str:
    x = data[data["total_events"] >= min_events].sort_values("obs_rate_pct", ascending=False).iloc[0]
    return (
        f"{x['AdmittingFacilityNameClean']} / {x['AttendingProviderHospitalGroupName_VOP']} shows the highest "
        f"observation mix among meaningful-volume combinations, with an OBS rate of {x['obs_rate_pct']:.0%}."
    )

def highest_concentration_takeaway(data: pd.DataFrame) -> str:
    conc = (
        data.groupby("AdmittingFacilityNameClean")
            .apply(lambda g: (g["facility_share_pct"]**2).sum())
            .sort_values(ascending=False)
    )
    fac = conc.index[0]
    return f"{fac} appears most concentrated, with volume flowing disproportionately through a smaller set of hospitalist groups."

def focused_facility_takeaway(data: pd.DataFrame, facility: str) -> str:
    x = (data[data["AdmittingFacilityNameClean"] == facility]
         .sort_values("total_events", ascending=False))
    if x.empty:
        return f"No rows found for {facility}."
    leader = x.iloc[0]
    if len(x) > 1:
        runner_up = x.iloc[1]
        return (
            f"At {facility}, {leader['AttendingProviderHospitalGroupName_VOP']} leads with {int(leader['total_events'])} events "
            f"vs. {int(runner_up['total_events'])} for {runner_up['AttendingProviderHospitalGroupName_VOP']}."
        )
    return f"At {facility}, {leader['AttendingProviderHospitalGroupName_VOP']} accounts for nearly all identified attributed volume."

print(top_facility_group_takeaway(df))
print(highest_obs_takeaway(df))
print(highest_concentration_takeaway(df))
```

---

# 3. Slide 1. Share of business by facility

This is the slide Dr. T probably cares about most.

## What it says

At each facility, which hospitalist group is getting the business.

```python
def slide1_share_of_business(data: pd.DataFrame, top_n_groups_per_facility: int = 4):
    plot_df = data[data["group_rank_in_facility"] <= top_n_groups_per_facility].copy()
    
    pivot = plot_df.pivot_table(
        index="AdmittingFacilityNameClean",
        columns="AttendingProviderHospitalGroupName_VOP",
        values="facility_share_pct",
        fill_value=0
    )
    
    fig, ax = plt.subplots(figsize=(14, 8))
    left = np.zeros(len(pivot))
    
    palette = [ACCENT, ACCENT_2, LIGHT_BLUE, OBS_COLOR, "#7A9E7E", "#E7A977", "#A78BFA", "#94A3B8"]
    
    for i, col in enumerate(pivot.columns):
        vals = pivot[col].values
        ax.barh(
            pivot.index.astype(str),
            vals,
            left=left,
            label=col,
            color=palette[i % len(palette)],
            edgecolor="white",
            height=0.75
        )
        
        for y, (l, v) in enumerate(zip(left, vals)):
            if v >= 0.08:
                ax.text(l + v/2, y, f"{v:.0%}", ha="center", va="center", color="white", fontsize=9, fontweight="bold")
        
        left += vals

    ax.set_title("Hospitalist Group Share of Business by Facility", loc="left", pad=16)
    ax.text(
        0, 1.04,
        fill(highest_concentration_takeaway(data), 105),
        transform=ax.transAxes, fontsize=11, color=MUTED
    )
    ax.set_xlabel("Share of Facility Volume")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(title="Hospitalist Group", bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False)
    plt.tight_layout()
    return fig

fig1 = slide1_share_of_business(df)
plt.show()
```

---

# 4. Slide 2. Volume scorecard by facility and group

This is the direct count view. Less pretty than the share chart, more operationally useful.

```python
def slide2_volume_by_facility_group(data: pd.DataFrame, top_n_groups_per_facility: int = 3):
    plot_df = data[data["group_rank_in_facility"] <= top_n_groups_per_facility].copy()
    plot_df = plot_df.sort_values(["AdmittingFacilityNameClean", "total_events"], ascending=[True, False])

    facilities = plot_df["AdmittingFacilityNameClean"].astype(str).unique()
    fig, axes = plt.subplots(len(facilities), 1, figsize=(14, 2.6 * len(facilities)), sharex=False)
    if len(facilities) == 1:
        axes = [axes]

    palette = [ACCENT, ACCENT_2, LIGHT_BLUE, OBS_COLOR, "#7A9E7E", "#E7A977"]

    for ax, fac in zip(axes, facilities):
        sub = plot_df[plot_df["AdmittingFacilityNameClean"].astype(str) == fac].copy()
        sub = sub.sort_values("total_events", ascending=True)

        colors = [palette[i % len(palette)] for i in range(len(sub))]
        ax.barh(sub["AttendingProviderHospitalGroupName_VOP"].astype(str), sub["total_events"], color=colors, edgecolor="white")

        for i, (_, row) in enumerate(sub.iterrows()):
            label = f"{int(row['total_events'])} | {row['facility_share_pct']:.0%}"
            ax.text(row["total_events"] + max(sub["total_events"]) * 0.01, i, label, va="center", fontsize=10)

        ax.set_title(fac, loc="left", fontsize=13, color=TEXT, pad=8)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_ylabel("")

    fig.suptitle("Comparative Hospitalist Group Volume Within Each Facility", x=0.01, ha="left", fontsize=18, fontweight="bold")
    fig.text(0.01, 0.98, fill(top_facility_group_takeaway(data), 110), fontsize=11, color=MUTED, va="top")
    fig.supxlabel("Authorization Events | label shows count and share of facility volume")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    return fig

fig2 = slide2_volume_by_facility_group(df)
plt.show()
```

---

# 5. Slide 3. Acute vs OBS mix by facility-group

This is your sharper version of the heatmap. I would focus on **OBS rate** since that is the more interesting differentiator.

```python
def slide3_obs_heatmap(data: pd.DataFrame, min_events: int = 10):
    plot_df = data[data["total_events"] >= min_events].copy()

    heat = plot_df.pivot_table(
        index="AdmittingFacilityNameClean",
        columns="AttendingProviderHospitalGroupName_VOP",
        values="obs_rate_pct",
        fill_value=np.nan
    )

    ann = plot_df.pivot_table(
        index="AdmittingFacilityNameClean",
        columns="AttendingProviderHospitalGroupName_VOP",
        values="total_events",
        fill_value=0
    )

    fig, ax = plt.subplots(figsize=(14, 7))
    im = ax.imshow(heat.values, aspect="auto", cmap="YlOrRd", vmin=0, vmax=max(0.5, np.nanmax(heat.values)))

    ax.set_xticks(np.arange(len(heat.columns)))
    ax.set_yticks(np.arange(len(heat.index)))
    ax.set_xticklabels(heat.columns, rotation=45, ha="right")
    ax.set_yticklabels(heat.index)

    for i in range(len(heat.index)):
        for j in range(len(heat.columns)):
            val = heat.iloc[i, j]
            n = ann.iloc[i, j]
            if pd.notna(val):
                txt = f"{val:.0%}\n(n={int(n)})"
                ax.text(j, i, txt, ha="center", va="center", fontsize=9, color=TEXT)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("OBS Rate")

    ax.set_title("Observation Mix by Facility and Hospitalist Group", loc="left", pad=16)
    ax.text(
        0, 1.04,
        fill(highest_obs_takeaway(data, min_events=min_events), 105),
        transform=ax.transAxes, fontsize=11, color=MUTED
    )

    plt.tight_layout()
    return fig

fig3 = slide3_obs_heatmap(df, min_events=10)
plt.show()
```

---

# 6. Slide 4. Focus slide for key hospitals

This is where you can give Dr. T the exact “Harlingen Medical Center. Beyond vs Catalyst” style view.

```python
def slide4_facility_focus(data: pd.DataFrame, facilities: list, top_n: int = 4):
    plot_df = data[data["AdmittingFacilityNameClean"].astype(str).isin(facilities)].copy()
    plot_df = plot_df.sort_values(["AdmittingFacilityNameClean", "total_events"], ascending=[True, False])

    n = len(facilities)
    fig, axes = plt.subplots(1, n, figsize=(6 * n, 6), sharey=False)
    if n == 1:
        axes = [axes]

    palette = [ACCENT, ACCENT_2, LIGHT_BLUE, OBS_COLOR, "#7A9E7E", "#E7A977"]

    for ax, fac in zip(axes, facilities):
        sub = plot_df[plot_df["AdmittingFacilityNameClean"].astype(str) == fac].head(top_n).copy()
        sub = sub.sort_values("total_events", ascending=True)

        colors = [palette[i % len(palette)] for i in range(len(sub))]
        ax.barh(sub["AttendingProviderHospitalGroupName_VOP"].astype(str), sub["total_events"], color=colors)

        for i, (_, row) in enumerate(sub.iterrows()):
            ax.text(
                row["total_events"] + max(sub["total_events"]) * 0.02,
                i,
                f"{int(row['total_events'])} | {row['facility_share_pct']:.0%}",
                va="center",
                fontsize=10
            )

        ax.set_title(fac, loc="left", fontsize=14, pad=10)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_ylabel("")

    fig.suptitle("Focused Facility Comparisons", x=0.01, ha="left", fontsize=18, fontweight="bold")
    lines = [focused_facility_takeaway(data, f) for f in facilities]
    fig.text(0.01, 0.98, "\n".join(lines), fontsize=11, color=MUTED, va="top")
    fig.supxlabel("Authorization Events | label shows count and share of facility volume")
    plt.tight_layout(rect=[0, 0, 1, 0.92])
    return fig

fig4 = slide4_facility_focus(df, facilities=["Harlingen Medical Center", "Knapp Medical Center"])
plt.show()
```

---

# 7. Slide 5. Executive table

Sometimes a clean styled table wins the room.

```python
def slide5_exec_table(data: pd.DataFrame, top_n_groups_per_facility: int = 3):
    table_df = data[data["group_rank_in_facility"] <= top_n_groups_per_facility].copy()
    table_df = table_df.sort_values(["AdmittingFacilityNameClean", "group_rank_in_facility"])

    out = table_df[[
        "AdmittingFacilityNameClean",
        "AttendingProviderHospitalGroupName_VOP",
        "acute_events",
        "obs_events",
        "total_events",
        "facility_share_pct",
        "obs_rate_pct"
    ]].copy()

    out["facility_share_pct"] = out["facility_share_pct"].map(lambda x: f"{x:.0%}")
    out["obs_rate_pct"] = out["obs_rate_pct"].map(lambda x: f"{x:.0%}")

    return out.style \
        .hide(axis="index") \
        .set_caption("Facility-by-Hospitalist Group Scorecard") \
        .set_table_styles([
            {"selector": "caption", "props": [("font-size", "16px"), ("font-weight", "bold"), ("color", ACCENT)]},
            {"selector": "th", "props": [("background-color", ACCENT), ("color", "white"), ("padding", "8px")]},
            {"selector": "td", "props": [("padding", "6px")]},
        ]) \
        .background_gradient(subset=["acute_events", "obs_events", "total_events"], cmap="Blues")

slide5_exec_table(df, top_n_groups_per_facility=3)
```

---

# 8. Export charts for PowerPoint

```python
fig1.savefig("slide_1_share_of_business.png", dpi=300, bbox_inches="tight")
fig2.savefig("slide_2_volume_by_facility_group.png", dpi=300, bbox_inches="tight")
fig3.savefig("slide_3_obs_heatmap.png", dpi=300, bbox_inches="tight")
fig4.savefig("slide_4_facility_focus.png", dpi=300, bbox_inches="tight")
```

---

# 9. Slide storyline I would use

## Slide 1

**Headline:** Hospitalist group share varies materially by facility, with some hospitals showing much higher routing concentration than others
**Visual:** 100% stacked bar
**Takeaway:** use `highest_concentration_takeaway(df)`

## Slide 2

**Headline:** Within each hospital, a small number of groups account for most identified hospitalized volume
**Visual:** grouped bars by facility
**Takeaway:** use `top_facility_group_takeaway(df)`

## Slide 3

**Headline:** Observation mix is not uniform. Certain facility-group combinations are materially more OBS-heavy
**Visual:** OBS heatmap
**Takeaway:** use `highest_obs_takeaway(df)`

## Slide 4

**Headline:** Key hospital comparisons make the routing pattern immediately actionable
**Visual:** focused facility comparisons for Harlingen, Knapp, Valley Baptist, etc.
**Takeaway:** use `focused_facility_takeaway(df, "Harlingen Medical Center")`

## Slide 5

**Headline:** The underlying scorecard supports deeper drill-down into volume, mix, and later outcomes
**Visual:** styled table

---

# 10. If you want slide-ready text blocks generated automatically

```python
slide_text = {
    "slide_1_title": "Hospitalist Group Share of Business by Facility",
    "slide_1_takeaway": highest_concentration_takeaway(df),
    "slide_2_title": "Comparative Hospitalist Group Volume Within Each Facility",
    "slide_2_takeaway": top_facility_group_takeaway(df),
    "slide_3_title": "Observation Mix by Facility and Hospitalist Group",
    "slide_3_takeaway": highest_obs_takeaway(df),
    "slide_4_title": "Focused Facility Comparisons",
    "slide_4_takeaway_harlingen": focused_facility_takeaway(df, "Harlingen Medical Center"),
    "slide_4_takeaway_knapp": focused_facility_takeaway(df, "Knapp Medical Center"),
}

slide_text
```

---

# My blunt recommendation

Do **not** lead with the heatmap.
Lead with:

1. **share of business**
2. **comparative counts**
3. **facility focus**
4. then OBS mix

That sequence is much closer to what Dr. T actually asked for.

