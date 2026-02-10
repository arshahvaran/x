# conda activate tempenv2
# D:
# cd D:\Publications\Bhaleka_1\data\modis_cloud_fraction\
# python process_2.py

import os
import shutil
from collections import defaultdict
import rasterio
import numpy as np
from tqdm import tqdm


def main():
    aqua_dir = r"D:\Publications\Bhaleka_1\data\modis_cloud_fraction\processed_nwt_clipped\aqua"
    terra_dir = r"D:\Publications\Bhaleka_1\data\modis_cloud_fraction\processed_nwt_clipped\terra"
    output_dir = r"D:\Publications\Bhaleka_1\data\modis_cloud_fraction\processed_nwt_clipped\time-series"
    averaged_output_dir = r"D:\Publications\Bhaleka_1\data\modis_cloud_fraction\processed_nwt_clipped\temp"

    date_to_files = defaultdict(list)  # Store files by date for easier averaging

    # Process Aqua files
    for filename in tqdm(os.listdir(aqua_dir), desc="Processing Aqua"):
        if filename.endswith(".TIFF") and filename.startswith("MYDAL2"):
            date = filename.split("_")[4][:10]  # Extract YYYY-MM-DD
            date_to_files[date].append(os.path.join(aqua_dir, filename))
            new_filename = f"modis_cloud_fraction_{date}.TIFF"
            shutil.copy(os.path.join(aqua_dir, filename), os.path.join(output_dir, new_filename))

    # Process Terra files
    for filename in tqdm(os.listdir(terra_dir), desc="Processing Terra"):
        if filename.endswith(".TIFF") and filename.startswith("MODAL2"):
            date = filename.split("_")[4][:10]
            date_to_files[date].append(os.path.join(terra_dir, filename))
            if len(date_to_files[date]) == 1:  # If no Aqua file exists for this date
                new_filename = f"modis_cloud_fraction_{date}.TIFF"
                shutil.copy(os.path.join(terra_dir, filename), os.path.join(output_dir, new_filename))

    # Average duplicate rasters
    for date, files in tqdm(date_to_files.items(), desc="Averaging duplicates"):
        if len(files) == 2:  # Two rasters to average
            new_filename = f"modis_cloud_fraction_{date}.TIFF"
            with rasterio.open(files[0]) as src1, rasterio.open(files[1]) as src2:
                profile = src1.profile
                avg_data = (src1.read(1) + src2.read(1)) / 2  # Average pixel values
                with rasterio.open(os.path.join(averaged_output_dir, new_filename), 'w', **profile) as dst:
                    dst.write(avg_data, 1)


if __name__ == "__main__":
    main()
