import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt
import math
import datetime

PAN_LOOKAHEAD_X = 0.15
PAN_LOOKAHEAD_Y = 0.05
FRAMES = 2000
FRAMES_SKIPPED = 0
CHART_TEXT_COLOR = 'lawngreen'
LINE_COLOR = 'cyan'
CHART_BACKGROUND_COLOR = 'black'
TRANSPARENT_COLOR = 'magenta'
PLOT_DF = None

fig, ax = plt.subplots(ncols=3, figsize=(64, 36), gridspec_kw={'width_ratios': [5, 10, 5]})
# Init PNL Text Objects
pnl_font = {'family': 'serif',
            'color': 'lawngreen',
            'weight': 'bold',
            'size': 80,
            }
title_font = {'fontsize':130, 'weight':'bold', 'color':CHART_TEXT_COLOR}
rsi_pnl_text = ax[2].text(0.01, 0.1,
                          "RSI 1m: $0\n\nRSI 5m: $0\n\nRSI 15m: $0\n\nRSI 1h: $0\n\nRSI 1d: $0",
                          bbox=dict(boxstyle='round', facecolor='black'),
                          fontdict=pnl_font)
buyhold_pnl_text = ax[0].text(0.0, 0.3, "Buy and hold: $0",
                              bbox=dict(boxstyle='round', facecolor='black'),
                              fontdict=pnl_font)
line, = ax[1].plot([], [], color=LINE_COLOR, linewidth=3.0)

class Chart:
    def __init__(self, df):
        global PLOT_DF
        PLOT_DF = df
        fig.tight_layout()
        plt.subplots_adjust(top=0.9, bottom=0.05)
        fig.patch.set_facecolor(TRANSPARENT_COLOR)

        plt.rcParams.update({'font.size': 24})
        fmt_month = mdates.MonthLocator(interval=1)
        fmt_year = mdates.YearLocator()
        ax[1].xaxis.set_major_locator(fmt_year)
        ax[1].xaxis.set_minor_locator(fmt_month)

        ax[1].xaxis.set_minor_formatter(mdates.DateFormatter('%m'))
        ax[1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax[1].tick_params(axis='both', which='minor', labelsize=30, colors=CHART_TEXT_COLOR)
        ax[1].tick_params(axis='both', which='major', labelsize=65, colors=CHART_TEXT_COLOR)

        ax[1].set_xlabel("Date", fontweight='bold', fontsize=70, color=CHART_TEXT_COLOR)
        ax[1].set_ylabel("Price", fontweight='bold', fontsize=70, color=CHART_TEXT_COLOR)

        ax[0].axis('off')
        ax[2].axis('off')

        ax[1].set_facecolor(CHART_BACKGROUND_COLOR)
        ax[1].grid(True)


    def draw(self):
        global FRAMES_SKIPPED
        total_rows = len(PLOT_DF.index)
        FRAMES_SKIPPED = math.floor(total_rows / FRAMES)
        anim = FuncAnimation(fig, animate, interval=50, frames=min(total_rows, FRAMES), blit=True)
        #plt.show()
        anim.save("{}_wildersRSI.mp4".format(PLOT_DF.iloc[0]['ticker']), writer="ffmpeg")

def animate(i):
    # Only plot line 1 every FRAMES_SKIPPED interval
    i  = i * FRAMES_SKIPPED

    # Graph PAN logic
    total_rows = len(PLOT_DF.index)
    look_ahead_x = i + math.floor(total_rows * PAN_LOOKAHEAD_X)
    look_behind_x = max(0, i - math.floor(total_rows * PAN_LOOKAHEAD_X))
    look_ahead_y = min(total_rows, i + math.floor(total_rows * PAN_LOOKAHEAD_Y))
    look_behind_y = max(0, i - math.floor(total_rows * PAN_LOOKAHEAD_Y))
    if look_ahead_x <= total_rows:
        end_t = PLOT_DF.iloc[i:look_ahead_x]['t'].max()
    else:
        end_t = PLOT_DF.iloc[-1]['t']
    end_c = PLOT_DF.iloc[look_behind_y:look_ahead_y]['close'].max()

    start_t = PLOT_DF.iloc[look_behind_x]['t']
    start_c = PLOT_DF['close'].min()

    ax[1].set_ylim(start_c, end_c)
    ax[1].set_xlim(start_t, end_t)

    ax[1].set_title("{} - ${:.2f}".format(PLOT_DF.iloc[i]['ticker'], PLOT_DF.iloc[i]['close']), loc='center', fontdict=title_font)

    rsi_pnl_text.set_text("RSI 1m: ${:.2f}\n\nRSI 5m: ${:.2f}\n\nRSI 15m: ${:.2f}\n\nRSI 1h: ${:.2f}\n\nRSI 1d: ${:.2f}"
                          .format(PLOT_DF.iloc[i]['cash_pnl_minute_1'],PLOT_DF.iloc[i]['cash_pnl_minute_5'],
                                  PLOT_DF.iloc[i]['cash_pnl_minute_15'], PLOT_DF.iloc[i]['cash_pnl_hour_1'],PLOT_DF.iloc[i]['cash_pnl_day_1']),
                          )
    buyhold_pnl_text.set_text("Buy and hold: ${}".format( round((40000 / PLOT_DF.iloc[0]['close']) * PLOT_DF.iloc[i]['close']), 2))
    line.set_data(PLOT_DF.iloc[0:i:FRAMES_SKIPPED]['t'], PLOT_DF.iloc[0:i:FRAMES_SKIPPED]['close'])

    ax[2].figure.canvas.draw()
    return (line,rsi_pnl_text)