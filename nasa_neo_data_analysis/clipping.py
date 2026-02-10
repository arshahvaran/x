# conda activate tempenv2
# D:
# cd D:\Publications\Bhaleka_1\data\ceres_solar_insolation\
# python process_1.py

import os
import glob
import rasterio
from rasterio.mask import mask
import geopandas as gpd
import numpy as np

# Define the paths
input_raster_path = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\raw"

#input_shapefile_path = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\nwt_shapefile\nwt_shapefile.shp"
input_shapefile_path = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\ns_shapefile\ns_shapefile.shp"

#output_raster_path = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\processed_nwt_clipped"
output_raster_path = r"D:\Publications\Bhaleka_1\data\ceres_solar_insolation\processed_ns_clipped"

# Read the shapefile
shapefile = gpd.read_file(input_shapefile_path)

# Function to process each raster file
def process_raster(file_path):
    try:
        # Read the raster file
        with rasterio.open(file_path) as src:
            # Clip the raster with the shapefile geometry
            out_image, out_transform = mask(src, shapefile.geometry, crop=True)
            
            # Divide raster values by 255
            out_image = out_image / 255.0
            out_image = out_image * 550.0
            # Update the metadata
            out_meta = src.meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                "dtype": 'float32'
            })
            
            # Extract the date from the input file name
            file_name = os.path.basename(file_path)
            date_str = file_name.split('_')[3]
            
            # Create the output file name
            output_file_name = f"ceres_solar_insolation_{date_str}.TIFF"
            output_file_path = os.path.join(output_raster_path, output_file_name)
            
            # Save the processed raster
            with rasterio.open(output_file_path, "w", **out_meta) as dest:
                dest.write(out_image)
    except rasterio.errors.RasterioIOError as e:
        print(f"Skipping file {file_path} due to error: {e}")

# Ensure the output directory exists
os.makedirs(output_raster_path, exist_ok=True)

# Process all .tiff and .TIFF files in the input directory
for raster_file in glob.glob(os.path.join(input_raster_path, "*.tiff")) + glob.glob(os.path.join(input_raster_path, "*.TIFF")):
    process_raster(raster_file)
