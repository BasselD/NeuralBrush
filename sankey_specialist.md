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
