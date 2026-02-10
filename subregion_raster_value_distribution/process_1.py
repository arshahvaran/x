import os
import numpy as np
import geopandas as gpd
import rasterio
import rasterio.mask

# -------------------------------
# Define file paths
# -------------------------------
shapefile_path = r"E:\publications\ashkan_2\revision\figure_provinces\provinces_shapefile\provinces.shp"
updated_shapefile_path = r"E:\publications\ashkan_2\revision\figure_provinces\provinces_shapefile\provinces_updated.shp"
raster_path = r"E:\publications\ashkan_2\revision\figure_provinces\tif_file\BiLSTM_BWO.tif"

# -------------------------------
# Load the provinces shapefile using GeoPandas
# -------------------------------
gdf = gpd.read_file(shapefile_path)

# It is assumed that the shapefile already contains these fields:
#   very_low, very_low_p, low, low_per, moderate, moderate_p, high, high_per, very_high, very_high_
# (If not, you would need to add them before processing.)

# -------------------------------
# Open the raster using Rasterio
# -------------------------------
with rasterio.open(raster_path) as src:
    # Get the nodata value (if any); here it is 0.
    raster_nodata = src.nodata
    if raster_nodata is None:
        raster_nodata = 0

    # -------------------------------
    # Loop through each province (polygon) in the shapefile
    # -------------------------------
    for idx, row in gdf.iterrows():
        # Get the geometry in GeoJSON format (rasterio.mask.mask requires the __geo_interface__)
        geom = [row['geometry'].__geo_interface__]

        try:
            # Mask the raster with the polygon geometry and crop to the extent of the polygon.
            out_image, out_transform = rasterio.mask.mask(src, geom, crop=True)
        except Exception as e:
            print(f"Error processing polygon index {idx}: {e}")
            continue

        # out_image is a 3D array with shape (bands, height, width); here we have one band.
        data = out_image[0]

        # Create a mask for valid data (exclude nodata pixels)
        valid_mask = (data != raster_nodata)
        valid_data = data[valid_mask]
        # Also, remove any potential NaN values.
        valid_data = valid_data[~np.isnan(valid_data)]

        # -------------------------------
        # Count pixels in each wildfire susceptibility class.
        # The classes are defined as:
        #   Very Low:    [0, 0.32)
        #   Low:         [0.32, 0.42)
        #   Moderate:    [0.42, 0.46)
        #   High:        [0.46, 0.52)
        #   Very High:   [0.52, 1.0]   (including 1.0)
        # -------------------------------
        if valid_data.size == 0:
            count_very_low = count_low = count_moderate = count_high = count_very_high = 0
        else:
            count_very_low  = np.count_nonzero((valid_data >= 0)    & (valid_data < 0.32))
            count_low       = np.count_nonzero((valid_data >= 0.32) & (valid_data < 0.42))
            count_moderate  = np.count_nonzero((valid_data >= 0.42) & (valid_data < 0.46))
            count_high      = np.count_nonzero((valid_data >= 0.46) & (valid_data < 0.52))
            count_very_high = np.count_nonzero((valid_data >= 0.52) & (valid_data <= 1.0))

        # Total number of valid pixels in this polygon
        total_pixels = count_very_low + count_low + count_moderate + count_high + count_very_high

        # -------------------------------
        # Compute percentages for each class.
        # If no valid pixels are found, the percentages are set to 0.
        # -------------------------------
        if total_pixels > 0:
            perc_very_low  = (count_very_low  / total_pixels) * 100
            perc_low       = (count_low       / total_pixels) * 100
            perc_moderate  = (count_moderate  / total_pixels) * 100
            perc_high      = (count_high      / total_pixels) * 100
            perc_very_high = (count_very_high / total_pixels) * 100
        else:
            perc_very_low = perc_low = perc_moderate = perc_high = perc_very_high = 0

        # -------------------------------
        # Update the GeoDataFrame fields with the computed counts and percentages.
        # Field mapping (from your attribute table):
        #   very_low    : count for Very Low
        #   very_low_p  : percentage for Very Low
        #   low         : count for Low
        #   low_per     : percentage for Low
        #   moderate    : count for Moderate
        #   moderate_p  : percentage for Moderate
        #   high        : count for High
        #   high_per    : percentage for High
        #   very_high   : count for Very High
        #   very_high_  : percentage for Very High
        # -------------------------------
        gdf.at[idx, "very_low"]   = count_very_low
        gdf.at[idx, "very_low_p"] = perc_very_low
        gdf.at[idx, "low"]        = count_low
        gdf.at[idx, "low_per"]    = perc_low
        gdf.at[idx, "moderate"]   = count_moderate
        gdf.at[idx, "moderate_p"] = perc_moderate
        gdf.at[idx, "high"]       = count_high
        gdf.at[idx, "high_per"]   = perc_high
        gdf.at[idx, "very_high"]  = count_very_high
        gdf.at[idx, "very_high_"] = perc_very_high

        # (Optional) Print results for the polygon
        print(f"Polygon index {idx}: Total valid pixels = {total_pixels}")
        print(f"  Very Low: {count_very_low} pixels ({perc_very_low:.2f}%)")
        print(f"  Low: {count_low} pixels ({perc_low:.2f}%)")
        print(f"  Moderate: {count_moderate} pixels ({perc_moderate:.2f}%)")
        print(f"  High: {count_high} pixels ({perc_high:.2f}%)")
        print(f"  Very High: {count_very_high} pixels ({perc_very_high:.2f}%)\n")

# -------------------------------
# Write the updated GeoDataFrame to a new shapefile
# -------------------------------
gdf.to_file(updated_shapefile_path)
print("Processing complete. Updated shapefile saved as:")
print(updated_shapefile_path)
