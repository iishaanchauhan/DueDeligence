## Imports
from coinmetrics.api_client import CoinMetricsClient
from pathlib import Path
import pandas as pd
import numpy as np


## Functions
def scope_check(
        client_key, val_date='2022-09-30', exchanges=None, quote_ccys=None,
        lookback_period=10, granul='1m'):
    """
    Find all markets with available minutia data in CoinMetrics with optional
    constraint on exchanges and
    quote currencies to include.

    :param client_key: an instance of CoinMetrics API client class.
    :param val_date: valuation date
    :param exchanges: list of (reliable) exchanges to constraint the scope
    :param quote_ccys: list of (fiat) currencies to include as eligible quote
        currency
    :param lookback_period: how many days into the past should the daily volume
        be extracted
    :param granul: the candle frequency. Possible values are: '1m', '1h', '1d'.
        Default to be '1m'
    :return: a table of all markets with available minutia data in CoinMetrics
        with optional constraint on exchanges and
        quote currencies to include. Table columns:
        market: market name in CoinMetrics format (e.g. coinbase-btc-usd-spot,
        frequency: frequency of market data (e.g. 1m, 1h, etc.),
        min_time: timestamp of the first trade,
        max_time: timestamp of the most recent trade when this function is called,
        exchange: name of exchange,
        base: name of the crypto,
        quote: name of the quoting currency,
        market_type: type of market (spot, future, option),
        full_name: full name of the crypto,
    """
    all_assets = client_key.catalog_market_candles_v2(
        quote=None, market_type="spot").to_dataframe()
    all_assets['min_time'] = pd.to_datetime(all_assets['min_time'])
    all_assets['max_time'] = pd.to_datetime(all_assets['max_time'])
    all_assets = all_assets[
        (all_assets.frequency == granul)
        & (all_assets.min_time <=
           pd.to_datetime(val_date).tz_localize('UTC')
           - pd.Timedelta(f'{lookback_period} days'))]
    all_assets[['exchange', 'base', 'quote',
                'market_type']] = all_assets.market.str.split('-', expand=True)
    asset_names = client_key.reference_data_assets().to_dataframe()
    all_assets = (
        all_assets.merge(asset_names[['full_name', 'asset']], left_on='base',
                         right_on='asset', how='left'))
    all_assets.drop('asset', axis=1, inplace=True)

    if exchanges is not None:
        print('exchange not None')
        # if there is constraint on exchange
        exchanges_df = pd.DataFrame(exchanges,
                                    columns=['exchange']).drop_duplicates()
        all_assets = pd.merge(all_assets, exchanges_df, on='exchange',
                              how='inner')

    if quote_ccys is not None:
        print('quuote_ccys not None')
        # if there is constraint on base currency
        quote_ccys_df = pd.DataFrame(quote_ccys,
                                     columns=['quote']).drop_duplicates()
        all_assets = pd.merge(all_assets, quote_ccys_df, on='quote',
                              how='inner')
    return all_assets


## Constants
client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')
assets_df = client.reference_data_assets().to_dataframe()[
    ['asset', 'full_name']]
exchanges_df = client.reference_data_exchanges().to_dataframe()
exchanges_df = exchanges_df[
    ~exchanges_df['exchange'].isin(['bitmex'])]

exchanges = exchanges_df['exchange'].to_list()
granul = '1h'
val_date = '2025-06-30'
quote_ccys = ['usd', 'jpy', 'eur', 'usdt']
market_type = 'spot'

## Execution

#  intermediate variables
markets_all = scope_check(client_key=client, exchanges=exchanges,
                          val_date=val_date,
                          quote_ccys=quote_ccys, granul='1h')
markets = pd.merge(left=markets_all, right=assets_df['asset'], left_on='base',
                   right_on='asset', how='inner')

output_path = Path(__file__).parents[2] / 'output' / 'ExchangeDD' / val_date
output_file = (output_path
               / f'CoinMetricsData_{val_date.replace("-", "")}'
                 f'_{pd.Timestamp.today().strftime("%Y%m%d")}.csv')

# data extraction
if not output_path.exists():
    output_path.mkdir(parents=True, exist_ok=True)
    print('folder path created new')
else:
    print('folder path already exists')
print(f'market availability done, {markets.shape[0]} markets to extract')

df_list = []
for chunk in np.array_split(markets.index, markets.shape[0] // 20 + 1):
    try:
        df_foo = client.get_market_candles(
            markets=markets.loc[chunk, 'market'].to_list(),
            start_time=pd.to_datetime(val_date).isoformat(
                timespec='seconds'),
            end_time=(
                    pd.to_datetime(val_date)
                    + pd.Timedelta('1 day')).isoformat(timespec='seconds'),
            frequency=granul).to_dataframe()
        df_list.append(df_foo)
        print('Market data of {0} on {1} was downloaded'
              .format(markets.loc[chunk, 'market'].to_list(), val_date))
    except (KeyError, ValueError) as e:
        print('Market data of {0} on {1} was NOT downloaded'
              .format(markets.loc[chunk, 'market'].to_list(), val_date))
        print('Reason: ' + e)

df = pd.concat(df_list)
df = df.merge(markets[['market', 'full_name']], on='market')

df.to_csv(
    output_file, index=False)
print(f'csv output saved as {output_file}')
