from src.lib.iCAVEDataExtraction import scope_check, cont_check, first_trade
from coinmetrics.api_client import CoinMetricsClient
from pathlib import Path
import pandas as pd
import numpy as np

## Constants
print(Path.cwd())
client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')
assets_df = client.catalog_assets().to_dataframe()
granul = '1d'
val_dates = ['2023-12-31']
market_type = 'spot'
exchanges_df = pd.read_csv(
    Path(__file__).parents[1] / 'static' / 'iCAVE reliable exchanges.csv',
    parse_dates=['from', 'until'], dayfirst=True
)

fiat_currency_list = (
    pd.read_csv(Path(__file__).parents[1] / 'static' / 'fiat_currency.csv')[
        'Alphabetic Code'].str.lower().to_list())
fiat_currency_df = pd.DataFrame(fiat_currency_list,
                                columns=['quote']).drop_duplicates()

crypto_default_coverage = pd.read_csv(
    Path(__file__).parents[1] / 'static' / 'iCAVE default coverage.csv',
    parse_dates=['from', 'until']
)
lookback_period = 10


##  Functions


def scope_check_icave(
        val_date, exchange_input, ccy_df, client, output_path,
        lookback_period=10):
    """
    Returns all crypto-fiat markets among reliable exchanges.

    :param val_date: the valuation date
    :param ccy_df: the static dataframe of all fiat currencies
    :param exchange_input: the input list of reliable exchanges as a dataframe
        with entry and exit dates
    :param client: the instance of CoinMetrics API Python client
    :param lookback_period: the period to check for available trading activities
    :param output_path: folder path to export data
    :return: a Dataframe of all crypto-fiat markets with available minutia
        data in CoinMetrics with optional constraints on exchanges,
        currencies and crypto assets.

    Table columns:
        - market: market name in CoinMetrics format (e.g. coinbase-btc-usd-spot,
        - frequency: frequency of market data (e.g. 1m, 1h, etc.),
        - min_time: timestamp of the first trade,
        - max_time: timestamp of the most recent trade when this function is
          called,
        - exchange: name of exchange,
        - base: name of the crypto,
        - quote: name of the quoting currency,
        - market_type: type of market (spot, future, option),
        - full_name: full name of the crypto
    """
    # intermediate variables
    val_date_dt = pd.to_datetime(val_date)
    output_file_exchanges = output_path / 'iCAVE current reliable exchanges.csv'
    # determine currently reliable exchanges as of val_date
    exchange_output = exchange_input.loc[
        (
                (
                        exchange_input['from'].isnull() | (
                        exchange_input['from'] <= val_date_dt))
                & (
                        exchange_input['until'].isnull() | (
                        exchange_input['until'] >= val_date_dt)))
        , 'exchange']

    print(val_date)

    all_markets = scope_check(
        client_key=client,
        val_date=val_date,
        exchanges=exchange_output.str.lower().to_list(),
        lookback_period=lookback_period)
    fiat_crypto_markets = all_markets.merge(
        ccy_df, how='outer', on='quote', indicator=True
    )
    fiat_crypto_markets = fiat_crypto_markets[
        fiat_crypto_markets['_merge'].isin(['both', 'left_only'])]
    cont_check_df = cont_check(
        val_date=val_date,
        markets=fiat_crypto_markets,
        client=client,
        lookback_period=lookback_period
    )
    # only check first snapshot with volume for fiat markets
    first_trade_df = first_trade(
        val_date=val_date,
        client=client,
        markets=fiat_crypto_markets[fiat_crypto_markets['_merge'] == 'both']
    )
    fiat_crypto_markets = (
        fiat_crypto_markets
        .merge(cont_check_df, on='market')
        .merge(first_trade_df, on='market', how='left'))
    # export static data as of val date
    exchange_output.to_csv(output_file_exchanges, index=False)

    return fiat_crypto_markets


def scope_check_default_icave(val_date, crypto_input, fiat_crypto_markets,
                              output_path):
    """
    Return fiat-crypto markets for top 50 crypto with the largest market cap.

    :param val_date: the valuation date
    :param crypto_input: a Dataframe containing the top 50 largest crypto by
        market cap. Must contain two columns: "base" (currency ticker) and
        "full_name" (full name of the crypto)
    :param fiat_crypto_markets: the full list of fiat-crypto and
        crypto-crypto trading pairs available from reliable exchange
    :return: a Dataframe containing fiat-crypto markets for top 50 crypto with
        the largest market cap.
    :param output_path: folder path to export data

    Table columns:
        - market: market name in CoinMetrics format (e.g. coinbase-btc-usd-spot,
        - frequency: frequency of market data (e.g. 1m, 1h, etc.),
        - min_time: timestamp of the first trade,
        - max_time: timestamp of the most recent trade when this function is
          called,
        - exchange: name of exchange,
        - base: name of the crypto,
        - quote: name of the quoting currency,
        - market_type: type of market (spot, future, option),
        - full_name: full name of the crypto
    """
    output_file_topcrypto = output_path / 'iCAVE current default coverage.csv'
    val_date_dt = pd.to_datetime(val_date)
    # determine currently top 50 crypto as of val_date for default coverage
    crypto_default_output = crypto_input.loc[
        (
                (
                        crypto_input['from'].isnull() | (
                        crypto_input['from'] <= val_date_dt))
                & (
                        crypto_input['until'].isnull() | (
                        crypto_input['until'] >= val_date_dt)))
        , ['base', 'full_name']
    ]
    fiat_markets = (
        fiat_crypto_markets[fiat_crypto_markets['_merge'] == 'both']
        .drop('_merge', axis=1))
    fiat_markets_default = fiat_markets.merge(
        crypto_default_output, how='left', on=['base', 'full_name'],
        indicator=True
    )
    # export current top 50 crypto to csv
    crypto_default_output.to_csv(output_file_topcrypto, index=False)

    return fiat_markets_default


def export_scope_icave(
        val_date, fiat_crypto_markets, fiat_markets_default, output_path):
    """
    Export all market coverage files to csv and xlsx files.
    :param val_date: the valuation date
    :param fiat_crypto_markets: a Dataframe contains the full set of all
        markets among reliable exchange as of the valuation date
    :param fiat_markets_default: a Dataframe contains fiat-crypto markets
        among reliable exchanges for top 50 largest crytos by market cap as
        of the valuation date
    :param output_path: the folder path to export data
    :return: None
    """
    output_file_fiat = output_path / 'iCAVE fiat markets.csv'
    output_file_crypto = output_path / 'iCAVE crypto markets.csv'
    output_file_default = output_path / 'iCAVE default markets.csv'
    output_file_overview = (
            output_path / f'iCAVE coverage_{val_date.replace("-", "")}.xlsx')

    # fiat-crypto markets scoping
    fiat_markets = (
        fiat_crypto_markets[fiat_crypto_markets['_merge'] == 'both']
        .drop(columns=['_merge'])
    )
    # crypto-crypto markets scoping
    crypto_markets = (
        fiat_crypto_markets[fiat_crypto_markets['_merge'] == 'left_only']
        .drop(columns=['_merge'])
    )
    # default iCAVE coverage scoping
    fiat_markets_default[['min_time', 'max_time']] = (
        fiat_markets_default[['min_time', 'max_time']].apply(
            lambda x: x.dt.tz_localize(None))
    )
    print(f'market availability check done for {val_date}')
    print(f'number of fiat markets: {fiat_markets.shape[0]}')
    print(
        f'default coverage of fiat markets: '
        f'{fiat_markets_default.loc[fiat_markets_default["_merge"] == "both"].shape[0]}')
    crypto_markets[['min_time', 'max_time']] = (
        crypto_markets[['min_time', 'max_time']].apply(
            lambda x: x.dt.tz_localize(None))
    )
    print(f'number of crypto markets: {crypto_markets.shape[0]}')
    crypto_market_coverage = crypto_markets.drop_duplicates(
        subset='full_name')
    # export data to csv and xlsx format
    fiat_markets.to_csv(output_file_fiat, index=False)
    crypto_markets.to_csv(output_file_crypto, index=False)
    (
        fiat_markets_default
        .loc[fiat_markets_default['_merge'] == 'both']
        .drop('_merge', axis=1)
        .to_csv(output_file_default, index=False)
    )
    with pd.ExcelWriter(output_file_overview, mode='w',
                        engine="xlsxwriter") as writer:
        fiat_market_coverage = fiat_markets_default.drop_duplicates(
            subset='full_name')
        fiat_market_coverage['status'] = np.where(
            fiat_market_coverage['_merge'] == 'both',
            'Yes',
            'No, but can be manually extracted from data vendor')
        (
            fiat_market_coverage
            .sort_values(
                ['status', 'base'],
                ascending=[False, True])
            .drop(
                [col for col in fiat_market_coverage.columns if
                 col not in ['base', 'full_name', 'status']],
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
                [col for col in crypto_market_coverage.columns if
                 col not in ['base', 'full_name']],
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
    return None


## Execution
for val_date in val_dates:
    output_path = Path(__file__).parents[
                      2] / 'output' / 'MarketDataOfficial' / val_date
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
    output_file_fiat = output_path / 'iCAVE fiat markets.csv'
    if output_file_fiat.exists():
        print(f'iCAVE coverage as of {val_date} is already determined!')
        while True:
            ow_bool = input(
                'Do you want to overwrite the coverage output (y/n)?')
            if ow_bool == 'y':
                ow_bool = True
                break
            elif ow_bool == 'n':
                ow_bool = False
                break
            else:
                print('invalid value, please try again!')
    else:
        ow_bool = True
    if ow_bool:
        markets = scope_check_icave(
            val_date=val_date,
            exchange_input=exchanges_df,
            ccy_df=fiat_currency_df,
            client=client,
            output_path=output_path,
            lookback_period=10)
        default_markets = scope_check_default_icave(
            val_date=val_date,
            crypto_input=crypto_default_coverage,
            output_path=output_path,
            fiat_crypto_markets=markets)
        export_scope_icave(
            val_date=val_date,
            fiat_crypto_markets=markets,
            fiat_markets_default=default_markets,
            output_path=output_path
        )
        # volume statistics
        # output_path = Path(__file__).parents[
        #                   2] / 'output' / 'MarketDataOfficial' / val_date
        # output_file_stats = (
        #         output_path /
        #         f'VolumeStats_{lookback_period}d_{val_date.replace("-", "")}'
        #         f'_{pd.Timestamp.today().strftime("%Y%m%d")}.csv'
        # )
