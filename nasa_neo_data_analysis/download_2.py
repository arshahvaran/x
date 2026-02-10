# conda activate tempenv
# D:
# cd "D:\Publications\Bhaleka_1\data\modis_cloud_fraction\"
# python downloads.py

import requests
import os
from urllib.parse import urlparse

def download_file(url, current_number, total_number, start_number):
    try:
        # Print the current status with percentage completed
        completed = (current_number - start_number + 1) / total_number * 100
        print(f"Downloading file id {current_number}. Process {current_number - start_number + 1}/{total_number} ({completed:.2f}%) completed")

        # Start the session
        with requests.Session() as session:
            # Get the URL head to check the file name in the Content-Disposition
            response = session.head(url, allow_redirects=True)
            if 'Content-Disposition' in response.headers:
                filename = response.headers['Content-Disposition'].split('filename=')[1].strip('"')
                if not (filename.startswith("MYDAL2_D_CLD_FR") or filename.startswith("MODAL2_D_CLD_FR")):
                    return  # Skip download if filename is not correct
            else:
                filename = urlparse(url).path.split('/')[-1]

            # Check if the file already exists
            file_path = os.path.join("D:\\Publications\\Bhaleka_1\\data\\modis_cloud_fraction\\raw", filename)
            if os.path.exists(file_path):
                print(f"File {filename} already exists. Skipping download.")
                return  # Skip download if file already exists

            # Actual download if filename is correct or unknown
            response = session.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Save the file
            with open(file_path, 'wb') as f:
                f.write(response.content)

            # Check filename again if it was not checked before
            if not (filename.startswith("MYDAL2_D_CLD_FR") or filename.startswith("MODAL2_D_CLD_FR")):
                os.remove(file_path)  # Remove the file if it does not start with the correct prefixes

    except requests.RequestException as e:
        print(f"Failed to download {url}. Error: {e}")

# Main loop to download files
start_number = 1622840
end_number = 1884322
base_url = "https://neo.gsfc.nasa.gov/servlet/RenderData?si={}&cs=gs&format=TIFF&width=3600&height=1800"
total_files = end_number - start_number + 1

for number in range(start_number, end_number + 1):
    url = base_url.format(number)
    download_file(url, number, total_files, start_number)
