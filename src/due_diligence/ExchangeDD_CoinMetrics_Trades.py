## imports
from coinmetrics.api_client import CoinMetricsClient
from pathlib import Path
import pandas as pd
import numpy as np


## Function


def scope_check_trades(
        client_key, exchanges=None, quote_ccys=None, granul='1m'):
    """
    Find all markets with available minutia data in CoinMetrics with optional constraint on exchanges and
    quote currencies to include.

    :param client_key: an instance of CoinMetrics API client class.
    :param val_date: valuation date
    :param exchanges: list of (reliable) exchanges to constraint the scope
    :param quote_ccys: list of (fiat) currencies to include as eligible quote currency
    :param lookback_period: number of days into the past to check for trading activity
    :param granul: the candle frequency. Possible values are: '1m', '1h', '1d'. Default to be '1m'
    :return: a table of all markets with available minutia data in CoinMetrics with optional constraint on exchanges and
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
    all_assets = client_key.catalog_market_candles_v2(quote=None,
                                                   market_type="spot").to_dataframe()
    all_assets['min_time'] = pd.to_datetime(all_assets['min_time'])
    all_assets['max_time'] = pd.to_datetime(all_assets['max_time'])
    all_assets = all_assets[(all_assets.frequency == granul)]
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
    #
    # except ValueError as e:
    #     print(e)
    return all_assets


## Constants

client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')
assets = ['SOL','ETH','BNB','BTC','USDC'
]
ref_date = '2026-08-19'
quote_ccys = ['usdt']
market_type = 'spot'
assets_df = client.reference_data_assets(assets=assets).to_dataframe()[
    ['asset', 'full_name']]
exchanges_df = client.reference_data_exchanges().to_dataframe()
exchanges_df = exchanges_df[
    exchanges_df['exchange'].isin(['mexc'])]
# exchanges = exchanges_df['exchange'].to_list()
exchanges = ['mexc']
val_time_start = '2026-08-19T06:04:00'
val_time_end = '2026-08-19T06:10:00'
# val_time_start = (pd.Timestamp.now() - pd.Timedelta('3 hour')).isoformat(timespec='seconds')
# val_time_end = (pd.Timestamp.now() - pd.Timedelta('2 hour')).isoformat(timespec='seconds')

## Execution

#  intermediate variables
val_date = val_time_start[:10]
print(val_date)
markets_all = scope_check_trades(
    client_key=client, exchanges=exchanges,
    quote_ccys=quote_ccys, granul='1h')
markets = pd.merge(
    left=markets_all, right=assets_df['asset'], left_on='base',
    right_on='asset', how='inner')

output_path = (
        Path(__file__).parents[
            2] / 'output' / 'ExchangeDD' / ref_date / 'Coin Metrics Trades')

output_data = (
        output_path
        / f'CoinMetricsTrades'
          f'_{exchanges[0] if len(exchanges)==1 else "exchanges"}'
          f'_{val_time_end[:10].replace("-", "").replace(":", "")}'
          f'_{pd.Timestamp.today().strftime("%Y%m%d")}.csv')
output_scope = (
        output_path
        / f'CoinMetricsTrades'
          f'_{exchanges[0] if len(exchanges)==1 else "exchanges"}_markets'
          f'_{val_time_end[:10].replace("-", "").replace(":", "")}'
          f'_{pd.Timestamp.today().strftime("%Y%m%d")}.csv')
# data extraction
if not output_path.exists():
    output_path.mkdir()
    print('folder path created new')
else:
    print('folder path already exists')

print(f'market availability done, there are {markets.shape[0]} markets')
trades_data = []
for chunk in np.array_split(markets.index, markets.shape[0] // 3 + 1):
    try:
        trades_df = client.get_market_trades(
            markets=markets.loc[chunk, 'market'].to_list(),
            end_time=val_time_end,
            start_time=val_time_start,
            start_inclusive=True,
            end_inclusive=True,
            paging_from='end').to_dataframe()
        print(trades_df.loc[trades_df.index[:5], 'time'])
        trades_data.append(trades_df)
        print(
            f'{trades_df.shape[0]} trades for '
            f'{markets.loc[chunk, "market"].to_list()}'
            f'before {val_time_end} done')
    except (KeyError, ValueError) as e:
        print(e)
        print(f'trades data for {markets.loc[chunk, "market"].to_list()}'
              f'before {val_time_end} failed')
trades_data = pd.concat(trades_data)
trades_data = trades_data.merge(markets[['market', 'full_name']], on='market')
markets.to_csv(output_scope, index=False)
trades_data.to_csv(output_data, index=False)
print(f'csv output saved as {output_data}')
print(f'scope saved as {output_scope}')
