# conda activate tempenv2
# D:
# cd "D:\Publications\Bhaleka_1\data\ceres_solar_insolation\"
# python process_7.py


import os
import rasterio
import numpy as np
from glob import glob
from tqdm import tqdm

# Define start and end years
start_year = 2006
end_year = 2023

#input_directory = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\processed_nwt_clipped"
input_directory = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\processed_ns_clipped"

#output_directory = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\processed_nwt_clipped_averages"
output_directory = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\processed_ns_clipped_averages"

if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# Function to read raster data
def read_raster(file_path):
    with rasterio.open(file_path) as src:
        return src.read(1), src.meta

# Function to write raster data
def write_raster(data, meta, output_path):
    with rasterio.open(output_path, 'w', **meta) as dst:
        dst.write(data, 1)

# Get list of all raster files in the input directory
raster_files = glob(os.path.join(input_directory, "ceres_solar_insolation_*.TIFF"))

# Define seasons
seasons = {
    'spring': ['03', '04', '05'],
    'summer': ['06', '07', '08'],
    'autumn': ['09', '10', '11'],
    'winter': ['12', '01', '02']
}

# Filter raster files by year range
filtered_raster_files = []
for file_path in raster_files:
    basename = os.path.basename(file_path)
    date_part = basename.split('_')[3]  # Correcting the index to match the date format
    year = int(date_part.split('-')[0])
    if start_year <= year <= end_year:
        filtered_raster_files.append(file_path)

# Group raster files by season
rasters_by_season = {season: [] for season in seasons}
for file_path in tqdm(filtered_raster_files, desc="Grouping files by season"):
    basename = os.path.basename(file_path)
    date_part = basename.split('_')[3]  # Correcting the index to match the date format
    year = date_part.split('-')[0]
    month = date_part.split('-')[1]
    for season, months in seasons.items():
        if month in months:
            rasters_by_season[season].append(file_path)
            break

# Process each season
for season, files in tqdm(rasters_by_season.items(), desc="Processing seasons"):
    if not files:
        continue  # Skip if there are no files for this season

    # Initialize sum and count arrays
    data_sum = None
    data_count = None

    for file_path in tqdm(files, desc=f"Processing files for {season}", leave=False):
        data, meta = read_raster(file_path)

        if data_sum is None:
            data_sum = np.zeros_like(data, dtype=np.float64)
            data_count = np.zeros_like(data, dtype=np.float64)

        valid_mask = data != meta.get('nodata', -9999)
        data_sum[valid_mask] += data[valid_mask]
        data_count[valid_mask] += 1

    # Calculate the mean
    valid_pixels = data_count > 0
    seasonal_mean_data = np.zeros_like(data_sum, dtype=np.float64)
    seasonal_mean_data[valid_pixels] = data_sum[valid_pixels] / data_count[valid_pixels]
    seasonal_mean_data[~valid_pixels] = meta.get('nodata', -9999)

    # Update meta for the output raster
    meta.update({
        "driver": "GTiff",
        "height": seasonal_mean_data.shape[0],
        "width": seasonal_mean_data.shape[1],
        "transform": meta['transform'],
        "dtype": 'float32',
        "compress": 'lzw'
    })

    # Save the seasonal mean raster
    output_file_path = os.path.join(output_directory, f"ceres_solar_insolation_{season}_{start_year}-{end_year}.tif")
    write_raster(seasonal_mean_data.astype(np.float32), meta, output_file_path)

    print(f"Saved seasonal mean raster for {season} {start_year}-{end_year} to {output_file_path}")