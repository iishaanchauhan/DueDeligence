from src.lib.iCAVEDataExtraction import (scope_check_manual,
                                         export_scope_manual,
                                         get_market_data_manual)
from coinmetrics.api_client import CoinMetricsClient
from pathlib import Path
import pandas as pd

print(Path.cwd())

client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')
granul = '1m'

val_dates = ['2025-03-31']
market_type = 'spot'

assets_df = client.reference_data_assets().to_dataframe()

exchanges = pd.read_csv(
    Path(__file__).parents[1] / 'static' /
    'iCAVE reliable exchanges.csv',
    parse_dates=['from', 'until'], dayfirst=True)

fiat_currency_list = pd.read_csv(
    Path(__file__).parents[1] / 'static' /
    'fiat_currency.csv')[
    'Alphabetic Code'].str.lower().to_list()
fiat_currency_df = pd.DataFrame(fiat_currency_list,
                                columns=['quote']).drop_duplicates()

crypto_currency_df = pd.DataFrame(
    {
        'crv','ldo','mkr','pendle','prime','rpl'
    },
    columns=['base'])

lookback_period = 10
crypto_only = True
# set to True if conv market data already extracted and there is no need for
# further data
skip_conv = False
"""
Full coverage for all fiat
"""
for val_date in val_dates:
    output_path = (
            Path(__file__).parents[2] /
            'output' / 'iCAVEMarketData' / val_date)
    markets = scope_check_manual(
        val_date=val_date,
        exchange_df=exchanges,
        fiat_currency_df=fiat_currency_df,
        crypto_currency_df=crypto_currency_df,
        crypto_only=crypto_only,
        client=client,
        lookback_period=lookback_period)
    get_market_data_manual(
        client_key=client,
        output_path=output_path,
        granul=granul,
        crypto_only=crypto_only,
        fiat_crypto_markets=markets,
        val_date=val_date,
        skip_conv=skip_conv
    )
    print(f'Pricing data downloaded to: {output_path}')
