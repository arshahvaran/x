# conda activate tempenv2
# D:
# cd "D:\Publications\Bhaleka_1\data\daymet_srad\"
# python process_1.py

import os
import numpy as np
import rasterio
from rasterio.transform import from_origin, Affine
from rasterio.crs import CRS
from netCDF4 import Dataset
from datetime import datetime, timedelta

# Directories
input_dir = "D:\\Publications\\Bhaleka_1\\data\\daymet_srad\\raw"
output_dir = "E:\\temp"

# Function to process each netCDF file
def process_nc_file(nc_file):
    with Dataset(nc_file, 'r') as src:
        x = src.variables['x'][:]
        y = src.variables['y'][:]
        time = src.variables['time'][:]
        srad = src.variables['srad']
        lcc = src.variables['lambert_conformal_conic']
        
        # Define the projection
        crs = CRS.from_proj4(
            f"+proj=lcc +lat_1={lcc.standard_parallel[0]} +lat_2={lcc.standard_parallel[1]} "
            f"+lat_0={lcc.latitude_of_projection_origin} +lon_0={lcc.longitude_of_central_meridian} "
            f"+x_0={lcc.false_easting} +y_0={lcc.false_northing} +datum=WGS84 +units=m +no_defs"
        )

        # Define the transform
        x_res = (x.max() - x.min()) / (len(x) - 1)
        y_res = (y.max() - y.min()) / (len(y) - 1)
        transform = Affine.translation(x.min() - x_res / 2, y.max() + y_res / 2) * Affine.scale(x_res, -y_res)

        for i, day in enumerate(time):
            date = datetime(1950, 1, 1) + timedelta(days=int(day))
            date_str = date.strftime('%Y-%m-%d')
            output_filename = os.path.join(output_dir, f'daymet_srad_{date_str}.tif')

            # Prepare the srad data for this day
            srad_day = srad[i, :, :]

            try:
                # Remove the file if it exists
                if os.path.exists(output_filename):
                    os.remove(output_filename)

                # Create a new rasterio dataset
                with rasterio.open(
                    output_filename,
                    'w',
                    driver='GTiff',
                    height=srad_day.shape[0],
                    width=srad_day.shape[1],
                    count=1,
                    dtype=srad_day.dtype,
                    crs=crs.to_wkt(),
                    transform=transform,
                ) as dst:
                    dst.write(srad_day, 1)

            except Exception as e:
                print(f"Error processing {output_filename}: {e}")
                continue

# Process all nc files in the input directory
nc_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith('.nc')]
for nc_file in nc_files:
    process_nc_file(nc_file)
