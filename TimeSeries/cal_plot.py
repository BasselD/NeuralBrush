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

# --------------------------------------------------
# 4. Resize figure to accommodate bar chart
# --------------------------------------------------

n_years = df_tb.index.year.nunique()

fig.set_size_inches(
    16,
    max(9, n_years * 2.2 + 4)
)

# Move calendar upward to create space below
for axis in fig.axes:
    pos = axis.get_position()

    axis.set_position([
        pos.x0,
        0.40 + pos.y0 * 0.52,
        pos.width,
        pos.height * 0.52
    ])

# --------------------------------------------------
# 5. Add bar chart subplot
# --------------------------------------------------

ax_bar = fig.add_axes([
    0.10,   # Left
    0.08,   # Bottom
    0.80,   # Width
    0.24    # Height
])

bars = ax_bar.bar(
    last_21.index,
    last_21.values,

    color='#7852A3',
    edgecolor='white',
    linewidth=0.5,
    width=0.8
)

# --------------------------------------------------
# 6. Add value labels above bars
# --------------------------------------------------

ax_bar.bar_label(
    bars,
    labels=[
        f'{value/1000:,.1f}K'
        for value in last_21.values
    ],
    padding=3,
    fontsize=8,
    color='#002850'
)

# --------------------------------------------------
# 7. Customize bar chart
# --------------------------------------------------

ax_bar.set_title(
    'Daily Claims Volume | Last 21 Refreshes',
    fontsize=13,
    color='#002850',
    fontweight='bold',
    pad=15
)

ax_bar.set_ylabel(
    'Claims Volume',
    color='#002850'
)

# Format Y-axis in thousands
ax_bar.yaxis.set_major_formatter(
    ticker.FuncFormatter(
        lambda x, pos: f'{x/1000:,.0f}K'
    )
)

# Format X-axis as dates
ax_bar.xaxis.set_major_formatter(
    mdates.DateFormatter('%b %d')
)

plt.setp(
    ax_bar.get_xticklabels(),
    rotation=45,
    ha='right'
)

# Add space above tallest bar for labels
ax_bar.set_ylim(
    0,
    last_21.max() * 1.18
)

# Background and grid
ax_bar.set_facecolor('#F8F9FC')

ax_bar.grid(
    axis='y',
    color='#D9DDE5',
    linestyle='--',
    linewidth=0.6,
    alpha=0.7
)

ax_bar.set_axisbelow(True)

# Remove unnecessary borders
ax_bar.spines['top'].set_visible(False)
ax_bar.spines['right'].set_visible(False)

plt.show()