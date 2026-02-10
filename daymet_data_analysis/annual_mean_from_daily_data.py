# conda activate tempenv2
# D:
# cd "D:\Publications\Bhaleka_1\data\daymet_srad\"
# python process_3.py

import os
import rasterio
import numpy as np
from glob import glob
from tqdm import tqdm

# Define input and output directories
#input_directory = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_nwt_clipped"
#input_directory = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_ns_clipped"
input_directory = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_nwt_clipped_cw_ceres"

#output_directory = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_nwt_clipped_annual_mean"
#output_directory = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_ns_clipped_annual_mean"
output_directory = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_nwt_clipped_cw_ceres_annual_mean"

# Create the output directory if it does not exist
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
raster_files = glob(os.path.join(input_directory, "daymet_srad_*.tif"))

# Group raster files by year
rasters_by_year = {}
for file_path in raster_files:
    year = os.path.basename(file_path).split('_')[2].split('-')[0]
    if year not in rasters_by_year:
        rasters_by_year[year] = []
    rasters_by_year[year].append(file_path)

# Process each year
for year, files in tqdm(rasters_by_year.items(), desc="Processing years"):
    # Initialize sum and count arrays
    data_sum = None
    count = 0

    for file_path in tqdm(files, desc=f"Processing files for year {year}", leave=False):
        data, meta = read_raster(file_path)

        if data_sum is None:
            data_sum = np.zeros_like(data, dtype=np.float64)

        valid_mask = data != meta.get('nodata', -9999)
        data_sum[valid_mask] += data[valid_mask]
        count += 1

    # Calculate the mean
    annual_mean_data = data_sum / count
    annual_mean_data[~valid_mask] = meta.get('nodata', -9999)

    # Update meta for the output raster
    meta.update({
        "driver": "GTiff",
        "height": annual_mean_data.shape[0],
        "width": annual_mean_data.shape[1],
        "transform": meta['transform'],
        "dtype": 'float32',
        "compress": 'lzw'
    })

    # Save the annual mean raster
    output_file_path = os.path.join(output_directory, f"daymet_srad_{year}.tif")
    write_raster(annual_mean_data.astype(np.float32), meta, output_file_path)

    print(f"Saved annual mean raster for {year} to {output_file_path}")
