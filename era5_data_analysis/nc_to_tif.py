# conda activate tempenv2
# D:
# cd "D:\Publications\Bhaleka_1\data\era5_cloud_cover\"
# python process_1.py

import os
import numpy as np
import rasterio
from rasterio.transform import from_origin
from netCDF4 import Dataset
from tqdm import tqdm

# Define directories
input_dir = "D:\\Publications\\Bhaleka_1\\data\\era5_cloud_cover\\raw"
output_dir = "F:\\output"

# Create the output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Define the dimensions of the data
n_days_in_year = 365
n_hours_in_day = 24

def process_nc_file(nc_file_path, year):
    print(f"Processing file: {nc_file_path}")
    with Dataset(nc_file_path, 'r') as nc_file:
        tcc = nc_file.variables['tcc']
        latitudes = nc_file.variables['latitude'][:]
        longitudes = nc_file.variables['longitude'][:]
        
        # Calculate the daily means
        daily_tcc = np.zeros((n_days_in_year, len(latitudes), len(longitudes)), dtype=np.float32)
        
        for day in tqdm(range(n_days_in_year), desc=f'Processing days for {year}'):
            start_hour = day * n_hours_in_day
            end_hour = start_hour + n_hours_in_day
            
            # Handle edge case for the last day which might not have exactly 24 hours
            if end_hour > tcc.shape[0]:
                end_hour = tcc.shape[0]
            
            daily_data = tcc[start_hour:end_hour, :, :].astype(np.float32)
            daily_tcc[day, :, :] = np.mean(daily_data, axis=0)
        
        # Save daily rasters
        for day in tqdm(range(n_days_in_year), desc=f'Saving rasters for {year}'):
            date_str = f"{year}-{(day // 30 + 1):02d}-{(day % 30 + 1):02d}"
            output_path = os.path.join(output_dir, f"era5_cloud_cover_{date_str}.tif")
            
            with rasterio.open(
                output_path, 'w', driver='GTiff',
                height=len(latitudes), width=len(longitudes),
                count=1, dtype='float32',
                crs='+proj=latlong',
                transform=from_origin(longitudes.min(), latitudes.max(), 0.25, 0.25)
            ) as dst:
                dst.write(daily_tcc[day, :, :], 1)
            print(f"Saved {output_path}")

# Process each file
nc_files = sorted([f for f in os.listdir(input_dir) if f.endswith('.nc')])

for nc_file in tqdm(nc_files, desc='Processing yearly files'):
    year = int(nc_file[:4])
    nc_file_path = os.path.join(input_dir, nc_file)
    process_nc_file(nc_file_path, year)

print("Processing completed.")


