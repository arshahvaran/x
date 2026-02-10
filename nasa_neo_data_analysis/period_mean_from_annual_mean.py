# conda activate tempenv2
# D:
# cd "D:\Publications\Bhaleka_1\data\ceres_solar_insolation\"
# python process_6.py

import os
import rasterio
import numpy as np
from glob import glob
from tqdm import tqdm

# Define input and output directories
#input_directory = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\processed_nwt_clipped"
input_directory = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\processed_ns_clipped"

#output_directory = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\processed_nwt_clipped_averages"
output_directory = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\processed_ns_clipped_averages"

# Create the output directory if it does not exist
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# Define the start and end year
start_year = 2006
end_year = 2023

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

# Filter raster files by the specified year range
filtered_raster_files = []
for file_path in raster_files:
    year = int(os.path.basename(file_path).split('_')[3].split('-')[0])
    if start_year <= year <= end_year:
        filtered_raster_files.append(file_path)

# Initialize sum and count arrays
data_sum = None
data_count = None

# Process each file in the filtered list
for file_path in tqdm(filtered_raster_files, desc="Processing files"):
    data, meta = read_raster(file_path)

    if data_sum is None:
        data_sum = np.zeros_like(data, dtype=np.float64)
        data_count = np.zeros_like(data, dtype=np.int32)

    valid_mask = data != meta.get('nodata', -9999)
    data_sum[valid_mask] += data[valid_mask]
    data_count[valid_mask] += 1

# Calculate the mean
with np.errstate(divide='ignore', invalid='ignore'):
    period_mean_data = np.true_divide(data_sum, data_count)
    period_mean_data[data_count == 0] = meta.get('nodata', -9999)

# Update meta for the output raster
meta.update({
    "driver": "GTiff",
    "height": period_mean_data.shape[0],
    "width": period_mean_data.shape[1],
    "transform": meta['transform'],
    "dtype": 'float32',
    "compress": 'lzw'
})

# Save the period mean raster
output_file_path = os.path.join(output_directory, f"ceres_solar_insolation_{start_year}-{end_year}.tif")
write_raster(period_mean_data.astype(np.float32), meta, output_file_path)

print(f"Saved period mean raster for {start_year}-{end_year} to {output_file_path}")
