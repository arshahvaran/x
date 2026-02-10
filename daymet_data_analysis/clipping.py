# D:
# cd "D:\Publications\Bhaleka_1\data\daymet_srad\"
# python process_2.py

import arcpy
import os

# Input and output directories
input_directory = r"E:\\temp"
output_directory = r"D:\\Publications\\Bhaleka_1\\data\\daymet_srad\\processed_nwt_clipped"
output_directory2 = r"D:\\Publications\\Bhaleka_1\\data\\daymet_srad\\processed_ns_clipped"
in_template_dataset = r"D:\\Publications\\Bhaleka_1\\data\\daymet_srad\\nwt_shapefile\\nwt_shapefile.shp"
in_template_dataset2 = r"D:\\Publications\\Bhaleka_1\\data\\daymet_srad\\ns_shapefile\\ns_shapefile.shp"
rectangle = ""
clipping_geometry = "ClippingGeometry"
maintain_clipping_extent = "NO_MAINTAIN_EXTENT"
nodata_value_to_set = -9999
output_projection = arcpy.SpatialReference(4326)

# Create output directories if they don't exist
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

if not os.path.exists(output_directory2):
    os.makedirs(output_directory2)

# Function to clip, project, and remove original file
def clip_project_and_remove(filename):
    in_raster = os.path.join(input_directory, filename)
    temp_clipped_raster = os.path.join(output_directory, "temp_clipped_" + filename)
    temp_nodata_raster = os.path.join(output_directory, "temp_nodata_" + filename)
    final_raster = os.path.join(output_directory, filename)
    
    try:
        # Perform the clipping
        arcpy.management.Clip(
            in_raster=in_raster,
            rectangle=rectangle,
            out_raster=temp_clipped_raster,
            in_template_dataset=in_template_dataset,
            nodata_value="",
            clipping_geometry=clipping_geometry,
            maintain_clipping_extent=maintain_clipping_extent
        )
        
        # Set NoData value for the output raster using Con
        with arcpy.EnvManager(extent=rectangle):
            con_raster = arcpy.sa.Con(arcpy.Raster(temp_clipped_raster) == nodata_value_to_set, arcpy.sa.SetNull(temp_clipped_raster, temp_clipped_raster, "VALUE = -9999"), arcpy.Raster(temp_clipped_raster))
            con_raster.save(temp_nodata_raster)
        
        # Project the raster to the new projection
        arcpy.management.ProjectRaster(
            in_raster=temp_nodata_raster,
            out_raster=final_raster,
            out_coor_system=output_projection,
            resampling_type="NEAREST",
            in_coor_system=arcpy.Describe(temp_nodata_raster).spatialReference
        )
        
        # Remove the temporary and original files after processing
        arcpy.management.Delete(temp_clipped_raster)
        arcpy.management.Delete(temp_nodata_raster)
        print(f"Clipped, projected, set NoData value, and saved to {final_raster}.")
    except Exception as e:
        print(f"Error processing {filename}: {e}")

def clip_project_and_remove2(filename):
    in_raster = os.path.join(input_directory, filename)
    temp_clipped_raster = os.path.join(output_directory2, "temp_clipped_" + filename)
    temp_nodata_raster = os.path.join(output_directory2, "temp_nodata_" + filename)
    final_raster = os.path.join(output_directory2, filename)
    
    try:
        # Perform the clipping
        arcpy.management.Clip(
            in_raster=in_raster,
            rectangle=rectangle,
            out_raster=temp_clipped_raster,
            in_template_dataset=in_template_dataset2,
            nodata_value="",
            clipping_geometry=clipping_geometry,
            maintain_clipping_extent=maintain_clipping_extent
        )
        
        # Set NoData value for the output raster using Con
        with arcpy.EnvManager(extent=rectangle):
            con_raster = arcpy.sa.Con(arcpy.Raster(temp_clipped_raster) == nodata_value_to_set, arcpy.sa.SetNull(temp_clipped_raster, temp_clipped_raster, "VALUE = -9999"), arcpy.Raster(temp_clipped_raster))
            con_raster.save(temp_nodata_raster)
        
        # Project the raster to the new projection
        arcpy.management.ProjectRaster(
            in_raster=temp_nodata_raster,
            out_raster=final_raster,
            out_coor_system=output_projection,
            resampling_type="NEAREST",
            in_coor_system=arcpy.Describe(temp_nodata_raster).spatialReference
        )
        
        # Remove the temporary files after processing
        arcpy.management.Delete(temp_clipped_raster)
        arcpy.management.Delete(temp_nodata_raster)
        print(f"Clipped, projected, set NoData value, and saved to {final_raster}.")
    except Exception as e:
        print(f"Error processing {filename}: {e}")

print("Starting monitoring of the temp folder...")

# Infinite loop to monitor the directory
while True:
    try:
        for filename in os.listdir(input_directory):
            if filename.endswith(".tif"):
                clip_project_and_remove(filename)
                clip_project_and_remove2(filename)
                os.remove(os.path.join(input_directory, filename))  # Remove the original file after processing
    except Exception as e:
        print(f"Error in monitoring loop: {e}")
