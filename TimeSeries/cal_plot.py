import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates
import calplot

# --------------------------------------------------
# 1. Prepare the data
# --------------------------------------------------

# Ensure the index is datetime
df_tb.index = pd.to_datetime(df_tb.index)

# Sort by date
df_tb = df_tb.sort_index()

# Get the last 21 available refresh dates
last_21 = df_tb['CLMS_CA_CAP'].dropna().tail(21)

# --------------------------------------------------
# 2. Create calendar heatmap
# --------------------------------------------------

fig, ax = calplot.calplot(
    df_tb['CLMS_CA_CAP'],

    fillcolor='white',
    cmap='BuPu',
    colorbar=True,

    suptitle='CareAllies Stars Part-D Daily Claims Volume',

    suptitle_kws={
        'fontsize': 16,
        'color': '#002850'
    },

    linewidth=0.5,
    textcolor='gray',

    yearlabel_kws={
        'fontsize': 16,
        'color': '#002850',
        'fontweight': 'bold',
        'fontname': font_name
    }
)

# --------------------------------------------------
# 3. Customize calendar colorbar
# --------------------------------------------------

cax = fig.axes[-1]

cax.yaxis.set_major_formatter(
    ticker.FuncFormatter(
        lambda x, pos: f'{x/1000:,.0f}K'
    )
)

cax.set_ylabel(
    'Claims in K',
    rotation=270,
    labelpad=15
)

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates

# --------------------------------------------------
# 1. Dynamic claims formatter
# --------------------------------------------------

def format_claims(value):
    if abs(value) >= 1000:
        return f'{value/1000:,.1f}K'
    return f'{value:,.0f}'


# --------------------------------------------------
# 2. Prepare last 21 refreshes
# --------------------------------------------------

last_21 = (
    df_tb['CLMS_CA_CAP']
    .sort_index()
    .dropna()
    .tail(21)
)


# --------------------------------------------------
# 3. Resize the figure
# --------------------------------------------------

n_years = df_tb.index.year.nunique()

fig.set_size_inches(
    18,
    max(10, n_years * 2.5 + 3)
)

# Adjust the calendar axes
# Preserve their original relative positions

calendar_axes = fig.axes[:-1]

for axis in calendar_axes:

    pos = axis.get_position()

    axis.set_position([
        0.10,
        0.38 + pos.y0 * 0.58,
        0.80,
        pos.height * 0.58
    ])


# --------------------------------------------------
# 4. Customize calendar colorbar
# --------------------------------------------------

cax = fig.axes[-1]

cax.yaxis.set_major_formatter(
    ticker.FuncFormatter(
        lambda x, pos: format_claims(x)
    )
)

cax.set_ylabel(
    'Claims Volume',
    rotation=270,
    labelpad=15
)


# --------------------------------------------------
# 5. Add last 21 refreshes bar chart
# --------------------------------------------------

ax_bar = fig.add_axes([
    0.10,   # Left
    0.08,   # Bottom
    0.80,   # Width
    0.23    # Height
])

# Highlight latest refresh
colors = ['#7852A3'] * len(last_21)

colors[-1] = '#002850'

bars = ax_bar.bar(
    last_21.index,
    last_21.values,
    color=colors,
    edgecolor='white',
    linewidth=0.5,
    width=0.8
)


# --------------------------------------------------
# 6. Display actual values above bars
# --------------------------------------------------

ax_bar.bar_label(
    bars,
    labels=[
        format_claims(value)
        for value in last_21.values
    ],
    padding=3,
    fontsize=8,
    color='#002850'
)


# --------------------------------------------------
# 7. Format axes
# --------------------------------------------------

ax_bar.set_title(
    'Daily Claims Volume | Last 21 Refreshes',
    fontsize=13,
    color='#002850',
    fontweight='bold',
    pad=15
)

ax_bar.set_ylabel('Claims Volume')

ax_bar.yaxis.set_major_formatter(
    ticker.FuncFormatter(
        lambda x, pos: format_claims(x)
    )
)

ax_bar.xaxis.set_major_formatter(
    mdates.DateFormatter('%b %d')
)

plt.setp(
    ax_bar.get_xticklabels(),
    rotation=45,
    ha='right'
)

ax_bar.set_ylim(
    0,
    last_21.max() * 1.18
)

ax_bar.grid(
    axis='y',
    color='#D9DDE5',
    linestyle='--',
    linewidth=0.6,
    alpha=0.7
)

ax_bar.set_axisbelow(True)

ax_bar.spines['top'].set_visible(False)
ax_bar.spines['right'].set_visible(False)

plt.show()
