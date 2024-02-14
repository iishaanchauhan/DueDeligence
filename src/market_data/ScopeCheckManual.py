from src.lib.iCAVEDataExtraction import scope_check, cont_check, first_trade
from coinmetrics.api_client import CoinMetricsClient
from pathlib import Path
import pandas as pd

print(Path.cwd())

client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')
granul = '1d'
val_dates = ['2023-12-31']
market_type = 'spot'

assets_df = client.catalog_assets().to_dataframe()

exchanges = pd.read_csv(
    Path(__file__).parents[1] / 'static' / 'iCAVE reliable exchanges.csv',
    parse_dates=['from', 'until'], dayfirst=True)

fiat_currency_list = pd.read_csv(
    Path(__file__).parents[1] / 'static' / 'fiat_currency.csv')[
    'Alphabetic Code'].str.lower().to_list()
fiat_currency_df = pd.DataFrame(fiat_currency_list,
                                columns=['quote']).drop_duplicates()

crypto_currency_df = pd.DataFrame(
    {
        'iris', 'pcx', 'cusd', 'orc', 'mtrg', 'xprt', 'lat', 'cspr', 'steth',
        'xpla', 'ssv'
    },
    columns=['base'])
lookback_period = 10
crypto_only = True
"""
Full coverage for all fiat
"""

for val_date in val_dates:
    print(val_date)
    output_path = Path(__file__).parents[
                      2] / 'output' / 'MarketDataOfficial' / val_date
    output_scope = output_path / 'iCAVE manual extraction markets.csv'
    output_conversion = output_path / 'iCAVE manual extraction conversion.csv'
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
    output_scope.unlink(missing_ok=True)
    output_conversion.unlink(missing_ok=True)
    # determine currently reliable exchanges as of val_date
    val_date_dt = pd.to_datetime(val_date)
    exchange_output = exchanges.loc[
        (
                (exchanges['from'].isnull() | (
                        exchanges['from'] <= val_date_dt))
                & (exchanges['until'].isnull() | (
                exchanges['until'] >= val_date_dt))
        ),
        'exchange']
    # extract all markets
    all_markets = scope_check(client_key=client,
                              val_date=val_date,
                              exchanges=exchange_output.str.lower().to_list(),
                              lookback_period=lookback_period)
    if crypto_only:
        # Left join to take everything which are NOT fiat quotes
        markets = (
            all_markets
            .merge(crypto_currency_df, how='inner', on='base')
            .merge(fiat_currency_df, how='left', on='quote', indicator=True)
        )
        markets = markets[markets['_merge'] == 'left_only']
        quote_crypto_df = (
            markets['quote'].drop_duplicates().to_frame().rename(
                columns={'quote': 'base'})
            .merge(all_markets, how='inner', left_on='base', right_on='base')
            .merge(fiat_currency_df, how='inner', left_on='quote',
                   right_on='quote')
        )
        markets_full = pd.concat([markets, quote_crypto_df])
        quote_crypto_df.to_csv(output_conversion, index=False)
        markets.to_csv(output_scope, index=False)
        print(f'number of crypto-fiat quotes: {quote_crypto_df.shape[0]}')
        print(f'number of crypto-crypto quotes: {markets.shape[0]}')
    else:
        markets = (all_markets
                   .merge(crypto_currency_df, how='inner', on='base')
                   .merge(fiat_currency_df, how='inner', on='quote',
                          indicator=True)
                   .drop_duplicates())
        cont_check_df = cont_check(
            val_date=val_date,
            markets=markets,
            client=client,
            lookback_period=lookback_period
        )
        # only check first snapshot with volume for fiat markets
        first_trade_df = first_trade(
            val_date=val_date,
            client=client,
            markets=markets[markets['_merge'] == 'both']
        )
        markets = (markets
                   .merge(cont_check_df, on='market')
                   .merge(first_trade_df, on='market', how='left'))
        print(f'number of crypto-fiat quotes: {markets.shape[0]}')
        markets.to_csv(output_scope, index=False)
    print(f'scope definition  done for {val_date}')
