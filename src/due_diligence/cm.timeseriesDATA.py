from pathlib import Path

# Print current working directory to know where files will be saved
print(Path.cwd())

from coinmetrics.api_client import CoinMetricsClient
import pandas as pd
import numpy as np

# CoinMetrics API client
client = CoinMetricsClient('zzHnUvjMgthSKDZuZOUb')

# Number of markets requested per API call to avoid overloading API
market_batch_size = 50

# Historical period for which market data is required
start_time = '2023-01-01T00:00:00Z'
end_time = '2025-12-31T23:59:59Z'

# List of crypto assets for which pricing data is required
crypto_quotes = [
    'cetus', 'hsk', 'taiko', 'cati', 'meme', 'fuel',
    'sonic', 'solv', 'j', 'anime', 'safe', 'zeta',
    'shell', 'roam', 'w', 'kernel', 'wct', 'acs',
    'init', 'haedal', 'newt', 'xdc', 'tanssi',
    'huma', 'tnsr', 'tree', 'towns', 'uxlink',
    'in', 'prove', 'asp', 'sapien', 'forest',
    'u', 'wlfi', 'xpl', 'flk', 'parti', 'zbt',
    'eat', 'pyth', 'zrc', 'irys', 'mat', 'adi',
    'zkp', 'zk', 'linea', 'era', 'ip', 'me', 'ape'
]

# Reliable exchanges approved for price sourcing
exchanges = [
    'binance',
    'bitstamp',
    'bullish',
    'bybit',
    'coinbase',
    'crypto.com',
    'deribit',
    'gemini',
    'huobi',
    'itbit',
    'kraken',
    'okex'
]

print("Downloading CoinMetrics catalog...")

# Download the full CoinMetrics market catalog
catalog = client.catalog_market_candles_v2().to_dataframe()

# Create lowercase version of market name for easier filtering
catalog["market_lower"] = (
    catalog["market"]
    .astype(str)
    .str.lower()
)

# Keep spot markets only
catalog = catalog[
    catalog["market_lower"].str.endswith("-spot")
]

catalog = catalog[
    catalog["market_lower"].str.endswith("-usdt-spot")
]

# Keep only exchanges in the approved exchange list
catalog = catalog[
    catalog["market_lower"].str.startswith(
        tuple([x.lower() for x in exchanges])
    )
]

# Build regex pattern from crypto asset list
asset_pattern = "|".join(
    [f"-{x.lower()}-" for x in crypto_quotes]
)

# Keep only requested crypto assets
catalog = catalog[
    catalog["market_lower"].str.contains(
        asset_pattern,
        regex=True
    )
]

# Remove duplicate market entries
spot_markets = catalog.drop_duplicates(
    subset=["market"]
)

print(
    f"spot market scoping done, "
    f"{spot_markets.shape[0]} markets to extract data"
)

# Store downloaded candle data
spot_closing_prices = []

# Download market data in batches to reduce API load
for batch in np.array_split(
        spot_markets,
        spot_markets.shape[0] // market_batch_size + 1):

    print(
        f"Extracting batch containing "
        f"{len(batch)} markets"
    )

    # Download hourly candle data for markets in current batch
    batch_spot_closing_prices = (
        client.get_market_candles(
            markets=batch.market.tolist(),
            frequency="1h",
            start_time=start_time,
            end_time=end_time
        ).to_dataframe()
    )

    # Store batch results
    spot_closing_prices.append(
        batch_spot_closing_prices
    )

# Combine all batches into a single dataframe
spot_closing_prices = pd.concat(
    spot_closing_prices,
    ignore_index=True
)

# Save extracted data to CSV
spot_closing_prices.to_csv(
    "illiquid_spot_price_close.csv",
    index=False
)

print(
    f"Downloaded "
    f"{spot_closing_prices.shape[0]} rows"
)

print("get spot prices done")