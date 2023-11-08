from src.lib.iCAVEDataExtraction import get_markets_data
from coinmetrics.api_client import CoinMetricsClient
from pathlib import Path
import pandas as pd

print(Path.cwd())

client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')
std_coverage = pd.read_csv(
    Path(__file__).parents[1] / 'static' / 'iCAVE default coverage.csv')
granul = '1m'
val_dates = ['2023-06-30']
market_type = 'spot'

for val_date in val_dates:
    output_path = Path(__file__).parents[
                      2] / 'output' / 'MarketDataOfficial' / val_date
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
        print(
            f'please execute ScopeCheck.py to determine scope for market data'
            f'extraction as of {val_date}')
    else:
        final_coverage = pd.read_csv(output_path / 'iCAVE default markets.csv')
        output_file = (
                output_path
                / f'CoinMetricsData_{val_date.replace("-", "")}'
                  f'_{pd.Timestamp.today().strftime("%Y%m%d")}'
                  f'.csv')
        print(f'market availability done for {val_date}')
        print(
            f'number of markets in default coverage: {final_coverage.shape[0]}')

        df = get_markets_data(final_coverage, val_date=val_date,
                              client_key=client, granul=granul,
                              lookback_price=0, lookback_volume=10,
                              vol_hist=True)
        df.to_csv(output_file, index=False)
