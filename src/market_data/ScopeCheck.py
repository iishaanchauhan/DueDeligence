from src.lib.iCAVEDataExtraction import scope_check, vol_stats
from coinmetrics.api_client import CoinMetricsClient
from pathlib import Path
import os
import pandas as pd
import numpy as np

## Constants
print(Path.cwd())
client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')
assets_df = client.catalog_assets().to_dataframe()
granul = '1d'
val_dates = ['2022-12-31']
market_type = 'spot'
market_data_list = list()
exchanges_df = pd.read_csv(
    Path(__file__).parents[1] / 'static' / 'iCAVE reliable exchanges.csv',
    parse_dates=['from', 'until'], dayfirst=True
)

fiat_currency_list = (
    pd.read_csv(Path(__file__).parents[1] / 'static' / 'fiat_currency.csv')['Alphabetic Code'].str.lower().to_list())
fiat_currency_df = pd.DataFrame(fiat_currency_list, columns=['quote']).drop_duplicates()

crypto_default_coverage = pd.read_csv(
    Path(__file__).parents[1] / 'static' / 'iCAVE default coverage.csv',
    parse_dates=['from', 'until']
)
lookback_period = 10
vol_stat = False


##  Functions


def scope_check_iCAVE(val_date, exchange_input, ccy_df, crypto_input, client, lookback_period=10):
    """
    Returns all crypto-fiat markets among reliable exchanges either as csv export and/or as dataframe output
    :param val_date: the valuation date
    :param ccy_df: the static dataframe of all fiat currencies
    :param crypto_input: the static dataframe of crypto assets with entry and exit dates
    :param exchange_input: the input list of reliable exchanges as a dataframe with entry and exit dates
    :param client: the instance of CoinMetrics API Python client
    :param lookback_period: the period to check for available trading activities
    :return: a table of all crypto-fiat markets with available minutia data in CoinMetrics with optional constraints
    on exchanges, currencies and crypto assets. Table columns:
        market: market name in CoinMetrics format (e.g. coinbase-btc-usd-spot,
        frequency: frequency of market data (e.g. 1m, 1h, etc.),
        min_time: timestamp of the first trade,
        max_time: timestamp of the most recent trade when this function is called,
        exchange: name of exchange,
        base: name of the crypto,
        quote: name of the quoting currency,
        market_type: type of market (spot, future, option),
        full_name: full name of the crypto
    """
    # intermediate variables
    val_date_dt = pd.to_datetime(val_date)
    output_path = Path(__file__).parents[2] / 'output' / 'MarketDataOfficial' / val_date
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
    output_file_fiat = output_path / 'iCAVE fiat markets.csv'
    output_file_crypto = output_path / 'iCAVE crypto markets.csv'
    output_file_default = output_path / 'iCAVE default markets.csv'
    output_file_overview = output_path / f'iCAVE coverage_{val_date.replace("-", "")}.xlsx'
    output_file_exchanges = output_path / 'iCAVE current reliable exchanges.csv'
    output_file_topcrypto = output_path / 'iCAVE current default coverage.csv'
    # determine currently reliable exchanges as of val_date
    exchange_output = exchange_input.loc[
        (
                (exchange_input['from'].isnull() | (exchange_input['from'] <= val_date_dt))
                & (exchange_input['until'].isnull() | (exchange_input['until'] >= val_date_dt))
        ),
        'exchange']
    exchange_output.to_csv(output_file_exchanges, index=False)
    # determine currently top 50 crypto as of val_date for default coverage
    crypto_default_output = crypto_input.loc[
        (
                (crypto_input['from'].isnull() | (crypto_input['from'] <= val_date_dt))
                & (crypto_input['until'].isnull() | (crypto_input['until'] >= val_date_dt))
        ),
        ['base', 'full_name']
    ]
    crypto_default_output.to_csv(output_file_topcrypto, index=False)
    print(val_date)

    # fiat markets scope definition
    all_markets = scope_check(client_key=client,
                              val_date=val_date,
                              exchanges=exchange_output.str.lower().to_list(),
                              lookback_period=lookback_period)
    if output_file_fiat.exists():
        print('iCAVE coverage already determined')

        return None
    else:
        fiat_crypto_markets = all_markets.merge(
            ccy_df, how='outer', on='quote', indicator=True
        )
        fiat_crypto_markets = fiat_crypto_markets[fiat_crypto_markets['_merge'].isin(['both', 'left_only'])]
        # fiat_markets = all_markets.merge(ccy_df, how='inner', on='quote')
        fiat_markets = (
            fiat_crypto_markets[fiat_crypto_markets['_merge'] == 'both']
            .drop(columns=['_merge'])
        )
        fiat_markets.to_csv(output_file_fiat, index=False)
        fiat_markets_default = fiat_markets.merge(
            crypto_default_output, how='left', on=['base', 'full_name'], indicator=True
        )
        (
            fiat_markets_default
            .loc[fiat_markets_default['_merge'] == 'both']
            .drop('_merge', axis=1)
            .to_csv(output_file_default, index=False)
        )
        fiat_markets_default[['min_time', 'max_time']] = (
            fiat_markets_default[['min_time', 'max_time']].apply(lambda x: x.dt.tz_localize(None))
        )
        fiat_market_coverage = fiat_markets_default.drop_duplicates(subset='full_name')
        fiat_market_coverage['status'] = np.where(
            fiat_market_coverage['_merge'] == 'both',
            'Yes',
            'No, but can be manually extracted from data vendor')
        print(f'market availability check done for {val_date}')
        print(f'total number of fiat markets: {fiat_markets.shape[0]}')
        print(
            f'default coverage of fiat markets: '
            f'{fiat_markets_default.loc[fiat_markets_default["_merge"] == "both"].shape[0]}')

        # crypto markets scope definition
        crypto_markets = (
            fiat_crypto_markets[fiat_crypto_markets['_merge'] == 'left_only']
            .drop(columns=['_merge'])
        )
        crypto_markets.to_csv(output_file_crypto, index=False)
        crypto_markets[['min_time', 'max_time']] = (
            crypto_markets[['min_time', 'max_time']].apply(lambda x: x.dt.tz_localize(None))
        )
        print(f'number of crypto markets: {crypto_markets.shape[0]}')
        crypto_market_coverage = crypto_markets.drop_duplicates(subset='full_name')
        # write coverage overview to excel
        with pd.ExcelWriter(output_file_overview, mode='w', engine="xlsxwriter") as writer:
            (
                fiat_market_coverage
                .sort_values(
                    ['status', 'base'],
                    ascending=[False, True])
                .drop(
                    [col for col in fiat_market_coverage.columns if col not in ['base', 'full_name', 'status']],
                    axis=1)
                .rename(
                    {'base': 'Asset',
                     'full_name': 'Full name',
                     'status': 'Market data available in iCAVE by default'},
                    axis=1)
                .to_excel(
                    excel_writer=writer,
                    sheet_name='iCAVE Coverage',
                    index=False)
            )
            (
                fiat_markets_default
                .loc[fiat_markets_default['_merge'] == 'both']
                .drop('_merge', axis=1)
                .to_excel(excel_writer=writer,
                          sheet_name='iCAVE All Markets',
                          index=False)
            )
            (
                crypto_market_coverage
                .drop(
                    [col for col in crypto_market_coverage.columns if col not in ['base', 'full_name']],
                    axis=1)
                .sort_values(
                    ['base'],
                    ascending=[True])
                .rename(
                    {'base': 'Asset',
                     'full_name': 'Full name'},
                    axis=1)
                .to_excel(
                    excel_writer=writer,
                    sheet_name='Manual Assessment Coverage',
                    index=False)
            )
            (
                crypto_markets
                .to_excel(excel_writer=writer,
                          sheet_name='All crypto markets',
                          index=False)
            )
        return fiat_markets


## Execution

for val_date in val_dates:
    fiat_markets = scope_check_iCAVE(
        val_date=val_date, exchange_input=exchanges_df, crypto_input=crypto_default_coverage,
        ccy_df=fiat_currency_df, client=client, lookback_period=10)

    # volume statistics
    output_path = Path(__file__).parents[2] / 'output' / 'MarketDataOfficial' / val_date
    output_file_stats = (
            output_path /
            f'VolumeStats_{lookback_period}d_{val_date.replace("-", "")}'
            f'_{pd.Timestamp.today().strftime("%Y%m%d")}.csv'
    )
    if vol_stat and not output_file_stats.exists():
        hist_vol = list()
        for chunk in np.array_split(fiat_markets.index, fiat_markets.shape[0] // 20 + 1):
            df = vol_stats(markets=fiat_markets.loc[chunk, 'market'].to_list(),
                           val_date=val_date, client_key=client,
                           lookback_volume=lookback_period)
            hist_vol.append(df)

        hist_vol = pd.concat(hist_vol)
        hist_vol[['exchange', 'base', 'quote', 'spot']] = hist_vol['market'].str.split('-', expand=True)
        hist_vol = hist_vol.merge(fiat_markets[['market', 'full_name']], on='market', how='inner')
        hist_vol.to_csv(
            os.path.join(val_date,
                         f'VolumeStats_{lookback_period}d_{val_date.replace("-", "")}'
                         f'_{pd.Timestamp.today().strftime("%Y%m%d")}.csv'),
            index=False)
        market_data_list.append(hist_vol)
    else:
        print('iCAVE volume statistics already determined or not activated')
