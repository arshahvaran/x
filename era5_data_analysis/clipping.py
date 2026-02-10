# D:
# cd "D:\Publications\Bhaleka_1\data\era5_cloud_cover\"
# python process_2.py


import arcpy
from arcpy import env
import os
from tqdm import tqdm

# Set environment settings
env.workspace = r"F:\output"
env.overwriteOutput = True

# Define the input and output directories
input_directory = r"F:\output"
output_directory = r"D:\Publications\Bhaleka_1\data\era5_cloud_cover\processed_nwt_clipped"
shapefile = r"D:\Publications\Bhaleka_1\data\era5_cloud_cover\nwt_shapefile\nwt_shapefile.shp"

# Create output directory if it doesn't exist
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# List all .tif files in the input directory
tif_files = [f for f in os.listdir(input_directory) if f.endswith('.tif')]

# Loop through each .tif file and clip it
for tif_file in tqdm(tif_files, desc="Clipping TIFF files"):
    in_raster = os.path.join(input_directory, tif_file)
    out_raster = os.path.join(output_directory, tif_file)
    
    # Clip the raster
    arcpy.management.Clip(
        in_raster=in_raster,
        rectangle="",
        out_raster=out_raster,
        in_template_dataset=shapefile,
        nodata_value="",
        clipping_geometry="ClippingGeometry",
        maintain_clipping_extent="NO_MAINTAIN_EXTENT"
    )

print("All TIFF files have been clipped successfully.")
