import pandas as pd

def test_parquet_file_quality():
    df = pd.read_parquet("parquet/egat_realtime_power_history.parquet")
    assert len(df) >= 1000, f"Dataset contains {len(df)} records, which is less than required."
    df['scrape_timestamp_utc'] = pd.to_datetime(df['scrape_timestamp_utc'])
    time_range = df['scrape_timestamp_utc'].max() - df['scrape_timestamp_utc'].min()
    assert time_range >= pd.Timedelta(hours=24), f"Dataset time range is {time_range}."
    completeness = df.notna().mean().mean()
    assert completeness >= 0.90, f"Dataset completeness is {completeness:.2%}, less than required."
    assert df.duplicated().sum() == 0, "Found duplicate records."

if __name__ == '__main__':
    test_parquet_file_quality()
    print("All dataset quality tests passed!")