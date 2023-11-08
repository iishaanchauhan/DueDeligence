from src.lib.iCAVEDataExtraction import get_markets_data
from coinmetrics.api_client import CoinMetricsClient
from pathlib import Path
import pandas as pd

print(Path.cwd())

client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')
std_coverage = pd.read_csv(
    Path(__file__).parents[1] / 'static' / 'iCAVE default coverage.csv')
granul = '1m'  # change back to 1m
val_dates = ['2022-12-31']
market_type = 'spot'
crypto_only = False

for val_date in val_dates:

    output_path = Path(__file__).parents[
                      2] / 'output' / 'MarketDataOfficial' / val_date
    input_scope = output_path / 'iCAVE manual extraction markets.csv'
    input_conversion = output_path / 'iCAVE manual extraction conversion.csv'

    if not output_path.exists() or not input_scope.exists():
        output_path.mkdir(parents=True, exist_ok=True)
        print(
            f'please execute ScopeCheckManual.py to determine scope '
            f'for market data extraction as of {val_date}')
    else:
        output_pricing = (
                output_path /
                f'CoinMetricsData_manual'
                f'_{val_date.replace("-", "")}'
                f'_{pd.Timestamp.today().strftime("%Y%m%d")}'
                f'.csv'
        )

    pricing_coverage = pd.read_csv(input_scope)
    print(f'market availability done for {val_date}')
    print(f'number of pricing quotes: {pricing_coverage.shape[0]}')
    df = get_markets_data(pricing_coverage, val_date=val_date,
                          client_key=client, granul=granul,
                          lookback_price=0, lookback_volume=10, vol_hist=True)
    df.to_csv(output_pricing, index=False)
    # only extract data if there is a scope definition for crypto conversion

    if input_conversion.exists():
        output_conversion = (
                output_path /
                f'CoinMetricsData_manualconv_{val_date.replace("-", "")}'
                f'_{pd.Timestamp.today().strftime("%Y%m%d")}'
                f'.csv'
        )
        conversion_coverage = pd.read_csv(input_conversion)
        print(f'number of conversion quotes: {conversion_coverage.shape[0]}')
        df = get_markets_data(conversion_coverage, val_date=val_date,
                              client_key=client, granul=granul,
                              lookback_price=0, lookback_volume=10,
                              vol_hist=True)
        df.to_csv(output_conversion, index=False)
    else:
        print(
            'if the data extraction is intended for manual assessment, '
            'please ensure that the flag crypto_only is True'
            ' when running ScopeCheckManual.py')
