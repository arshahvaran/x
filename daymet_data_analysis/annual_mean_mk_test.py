# conda activate tempenv2
# cd "D:\Publications\Bhaleka_1\data\daymet_srad\"
# python process_5.py

import os
import numpy as np
import rasterio
from pymannkendall import original_test
from tqdm import tqdm  # Progress bar library

# Input and output directories
#input_dir = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_nwt_clipped_annual_mean"
#input_dir = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_ns_clipped_annual_mean"
input_dir = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_nwt_clipped_cw_ceres_annual_mean"

#output_dir = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_nwt_clipped_annual_mean_mk_test"
#output_dir = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_ns_clipped_annual_mean_mk_test"
output_dir = r"D:\Publications\Bhaleka_1\data\daymet_srad\processed_nwt_clipped_cw_ceres_annual_mean_mk_test"

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Function to filter files by year range
def filter_files_by_year(tif_files, start_year, end_year):
    return [f for f in tif_files if start_year <= int(f.split('_')[2].split('.')[0]) <= end_year]

# Define the year range for the analysis
#start_year = 1980
#end_year = 2023

#start_year = 1980
#end_year = 2000

#start_year = 2001
#end_year = 2023

start_year = 2006
end_year = 2023

# Get list of all .tif files in the input directory and filter by year range
tif_files = [f for f in os.listdir(input_dir) if f.endswith('.tif')]
filtered_files = filter_files_by_year(tif_files, start_year, end_year)
years = sorted([int(f.split('_')[2].split('.')[0]) for f in filtered_files])

# Read the data into a 3D numpy array
data_stack = []
for year in tqdm(years, desc="Reading data"):
    file_path = os.path.join(input_dir, f"daymet_srad_{year}.tif")
    with rasterio.open(file_path) as src:
        data = src.read(1)
        data[data == src.nodata] = np.nan
        data_stack.append(data)

data_stack = np.stack(data_stack, axis=-1)

# Initialize arrays for the results
sen_slope = np.full(data_stack.shape[:-1], np.nan)
p_value = np.full(data_stack.shape[:-1], np.nan)
kendall_tau = np.full(data_stack.shape[:-1], np.nan)

# Perform Mann-Kendall test on each pixel
total_pixels = data_stack.shape[0] * data_stack.shape[1]
with tqdm(total=total_pixels, desc="Performing Mann-Kendall test") as pbar:
    for i in range(data_stack.shape[0]):
        for j in range(data_stack.shape[1]):
            pixel_values = data_stack[i, j, :]
            if np.isnan(pixel_values).all():
                pbar.update(1)
                continue
            result = original_test(pixel_values[~np.isnan(pixel_values)])
            sen_slope[i, j] = result.slope
            p_value[i, j] = result.p
            kendall_tau[i, j] = result.Tau
            pbar.update(1)

# Function to save a raster
def save_raster(data, template_file, output_file, nodata_value=3.4e+38):
    with rasterio.open(template_file) as src:
        meta = src.meta
        meta.update(dtype=rasterio.float32, count=1, compress='lzw', nodata=nodata_value)
        with rasterio.open(output_file, 'w', **meta) as dst:
            dst.write(data.astype(rasterio.float32), 1)

# Save the results
template_file = os.path.join(input_dir, filtered_files[0])
save_raster(sen_slope, template_file, os.path.join(output_dir, f'sen_slope_{start_year}-{end_year}.tif'))
save_raster(p_value, template_file, os.path.join(output_dir, f'p_value_{start_year}-{end_year}.tif'))
save_raster(kendall_tau, template_file, os.path.join(output_dir, f'kendall_tau_{start_year}-{end_year}.tif'))

print("Trend analysis completed and rasters saved.")
