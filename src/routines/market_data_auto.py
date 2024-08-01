from src.lib.iCAVEDataExtraction import (scope_check_icave,
                                         export_scope_icave,
                                         get_market_data_auto)
from coinmetrics.api_client import CoinMetricsClient
from pathlib import Path
import pandas as pd

## Constants
print(Path.cwd())
client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')
assets_df = client.catalog_assets().to_dataframe()
granul = '1m'
val_dates = ['2024-06-30']
market_type = 'spot'
exchanges_df = pd.read_csv(
    Path(__file__).parents[1] /
    'static' / 'iCAVE reliable exchanges.csv',
    parse_dates=['from', 'until'], dayfirst=True
)

fiat_currency_list = pd.read_csv(
    Path(__file__).parents[1] /
    'static' / 'fiat_currency.csv')['Alphabetic Code'].str.lower().to_list()
fiat_currency_df = pd.DataFrame(fiat_currency_list,
                                columns=['quote']).drop_duplicates()

crypto_default_coverage = pd.read_csv(
    Path(__file__).parents[1] /
    'static' / 'iCAVE default coverage.csv',
    parse_dates=['from', 'until'],
    dayfirst=True
)
lookback_period = 10
## Execution
for val_date in val_dates:
    output_path = (
            Path(__file__).parents[2] / 'output' /
            'iCAVEMarketData' / val_date)
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
                print('invalid value, please enter only "y" or "n"!')
    else:
        ow_bool = True
    if ow_bool:
        markets, default_markets = scope_check_icave(
            val_date=val_date,
            exchange_df=exchanges_df,
            fiat_currency_df=fiat_currency_df,
            crypto_currency_df=crypto_default_coverage,
            client=client,
            output_path=output_path,
            lookback_period=10)
        export_scope_icave(
            val_date=val_date,
            fiat_crypto_markets=markets,
            fiat_markets_default=default_markets,
            output_path=output_path
        )
        get_market_data_auto(
            val_date=val_date,
            client_key=client,
            output_path=output_path,
            fiat_crypto_markets=default_markets,
            granul=granul
        )
