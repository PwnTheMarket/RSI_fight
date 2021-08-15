import requests
import json
import datetime
import fight_chart
import math
import pandas as pd

RSI_LENGTH = 14
QUANDL_API_KEY = #'API_KEY_HERE'
STARTING_CASH = 40000
START_DATE = "2016-08-01"
CHART_PERIODS = [("minute", 1), ("minute", 5), ("minute", 15), ("hour", 1), ("day", 1)]
# in order to simulate bid/ask spread of market orders, these are percentages of average bid/ask spread of a given stock
# with respect to stock price. first element is average in-hour trading spread and second element is average extended hour bid/ask spread
BID_ASK_SPREADS = {"AMC": [0.0008, 0.01], "JPM": [0.0001, 0.001], "TSLA": [0.0003, 0.001], "SLV": [0.0004, 0.005], "SPY": [0.00002, 0.0001], "GE": [0.0003, 0.004], "AAL":[0.0003, 0.004]}

# 0.3% worst spread


def calculate_rsi(df, rsi_type, _window):
    """[RSI function]

    Args:
        df ([DataFrame]): [DataFrame with a column 'Close' for the close price]
        _window ([int]): [The lookback window.](default : {14})
        _plot ([int]): [1 if you want to see the plot](default : {0})
        _start ([Date]):[if _plot=1, start of plot](default : {None})
        _end ([Date]):[if _plot=1, end of plot](default : {None})
    """
    df.drop(df[df['close'] <= 0].index, inplace=True)
    ##### Diff for the différences between last close and now
    df['Diff'] = df['close'].transform(lambda x: x.diff())
    df['Diff'] = df['Diff'].fillna(0)
    ##### In 'Up', just keep the positive values
    df['Up'] = df['Diff']
    df.loc[(df['Up'] < 0), 'Up'] = 0
    ##### Diff for the différences between last close and now
    df['Down'] = df['Diff']
    ##### In 'Down', just keep the negative values
    df.loc[(df['Down'] > 0), 'Down'] = 0
    df['Down'] = abs(df['Down'])

    if rsi_type == "wilders":
        df['avg_up' + str(_window)] = df['Up'].ewm(alpha=1.0 / _window, adjust=False).mean()
        df['avg_down' + str(_window)] = df['Down'].ewm(alpha=1.0 / _window, adjust=False).mean()
    else:
        ##### Moving average on Up & Down
        df['avg_up' + str(_window)] = df['Up'].transform(lambda x: x.rolling(window=_window).mean())
        df['avg_down' + str(_window)] = df['Down'].transform(lambda x: x.rolling(window=_window).mean())

    ##### RS is the ratio of the means of Up & Down
    df['RS_' + str(_window)] = df['avg_up' + str(_window)] / df['avg_down' + str(_window)]

    ##### RSI Calculation
    ##### 100 - (100/(1 + RS))
    df['rsi'] = 100 - (100 / (1 + df['RS_' + str(_window)]))

    ##### Drop useless columns
    df = df.drop(['Diff', 'Up', 'Down', 'avg_up' + str(_window), 'avg_down' + str(_window), 'RS_' + str(_window)],
                 axis=1)
    return df

def add_rsi_pnl(ticker_df, cash_tag="cash"):
    price_bought = None
    shares_bought = None
    cash_available = STARTING_CASH
    profits_df = pd.DataFrame([])
    time = []
    cash = []
    # generate buy/sell signals
    ticker_df['signal'] = ticker_df['rsi'].apply(
        lambda rsi: 'buy' if rsi < 30 else ('sell' if rsi > 70 else 'noAction'))

    # compute pnl for buy/sell signals
    for index, row in ticker_df.iterrows():
        if row['signal'] == 'buy' and price_bought is None:
            price_bought = row['close']
            remaining_cash = cash_available % price_bought
            shares_bought = math.floor(cash_available / price_bought)
        elif row['signal'] == 'sell' and price_bought is not None:
            if datetime.datetime.utcfromtimestamp(row['t']).hour > 3 and datetime.datetime.utcfromtimestamp(row['t']).hour < 20:
                sell_price = row['close'] * (1-BID_ASK_SPREADS[row['ticker']][1]) # apply after hours spread
            else:
                sell_price = row['close'] * (1-BID_ASK_SPREADS[row['ticker']][0])
            if row['close'] - sell_price < 0.01: # cap minimum spread to $0.01
                sell_price = row['close'] - 0.01
            cash_available = round(remaining_cash + shares_bought*sell_price, 2)
            price_bought = None
            time.append(row['t'])
            cash.append(cash_available)

    #profits_df = profits_df.append({'t':row['t'], "cash_pnl_{}".format(cash_tag):cash_available}, ignore_index=True)
    profits_df['t'] = time
    profits_df["cash_pnl_{}".format(cash_tag)] = cash
    return ticker_df.set_index('t').join(profits_df.set_index('t')).reset_index()

def get_ticker_data(ticker, time_series, timeseries_interval, date, rsi_type):
    # number of days to grab for each api request
    query_window = 100
    # RSI (esp. wilders) needs more historical data to work with in order to
    # generate a more precise rsi value, so move start date up.
    start_date = datetime.datetime.strptime(date, "%Y-%m-%d") - datetime.timedelta(days=query_window)
    ticker_df = pd.DataFrame([])
    now = datetime.datetime.now()

    # download stock data and build dataframe in 'query_window' amounts
    while start_date <= now:
        end_date = start_date + datetime.timedelta(days=query_window)
        response = requests.get(
            "https://api.polygon.io/v2/aggs/ticker/{}/range/{}/{}/{}/{}?unadjusted=false&sort=asc&limit=50000&apiKey={}".format(
                ticker, timeseries_interval, time_series, start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"), QUANDL_API_KEY))
        json_response = json.loads(response.text)
        stock_tmp = pd.DataFrame(json_response["results"])
        ticker_df = ticker_df.append(stock_tmp)
        start_date = end_date

    # convert epoch to readable date and rename columns
    ticker_df['t'] = ticker_df['t'].apply(lambda t: datetime.datetime.utcfromtimestamp(t*0.001).timestamp()).astype(int)
    ticker_df.rename(columns={'h': 'high', 'l': 'low', 'v': 'volume', 'o': 'open', 'c': 'close'}, inplace=True)

    # since we had to include previous stock dates in order to calculate RSI value for user supplied date
    # skip these first values and only return date for user's date and on
    # rsi_data = ticker_df[ticker_df[ticker_df['t']==date].index.values[0]-1:]
    for index, row in ticker_df.iterrows():
        if date == datetime.datetime.utcfromtimestamp(row['t']).strftime("%Y-%m-%d"):
            return ticker_df[ticker_df[ticker_df['t'] == row['t']].index.values[0] - 1 :]


def fight(ticker, date, rsi_type="simple"):
    stock_df = None
    try:
        stock_df = pd.read_csv("rsi_data_{}_{}_rsi_{}final.pd".format(ticker, date, rsi_type))
    except:
        ticker_df = None
        for stock_time in CHART_PERIODS:
            try:
                ticker_df = pd.read_csv("rsi_data_{}_{}_{}_{}_rsi_{}.pd".format(ticker, date, stock_time[0], stock_time[1], rsi_type))
            except:
                ticker_df = get_ticker_data(ticker, stock_time[0], stock_time[1], date, rsi_type)
                ticker_df['ticker'] = ticker
                # compute rsi
                ticker_df = calculate_rsi(ticker_df, rsi_type, RSI_LENGTH)
                ticker_df.to_csv("rsi_data_{}_{}_{}_{}_rsi_{}.pd".format(ticker, date, stock_time[0], stock_time[1], rsi_type))
                pass
            rsi_df = add_rsi_pnl(ticker_df, "{}_{}".format(stock_time[0], stock_time[1]))
            # Build and join various RSI time interval pnl data to one entire dataframe
            if stock_df is None:
                stock_df = ticker_df
            cols_to_use = rsi_df.columns.difference(stock_df.columns)

            stock_df = pd.merge(stock_df, rsi_df[['t', cols_to_use[0]]], left_on='t', right_on='t', how="outer")

        stock_df = stock_df.sort_values(by=['t'])
        # upon merging with a timeseries superset, our subset timeseries is unlikely to have pnl data for the
        # first few superset ticks, this is a way to set first row to STARTING_CASH which will allow us to
        # fillna with its value for all missing rows including the first few rows
        for stock_time in CHART_PERIODS:
            stock_df.at[0, "cash_pnl_{}_{}".format(stock_time[0], stock_time[1])] = STARTING_CASH
        stock_df = stock_df.fillna(method='ffill')
        stock_df = stock_df[stock_df['close'].notna()]
        stock_df.to_csv("rsi_data_{}_{}_final.pd".format(ticker, date, rsi_type))
    stock_df = stock_df.drop_duplicates(subset=['t'])
    stock_df['t'] = stock_df['t'].apply(lambda x: datetime.datetime.utcfromtimestamp(x))

    fight_chart.Chart(stock_df).draw()

