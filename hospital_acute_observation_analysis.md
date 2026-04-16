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

If you want, next I can give you a **single polished Python script** that generates a full 4-chart executive report from `df`.
