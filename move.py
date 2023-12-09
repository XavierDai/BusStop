from email import header
import math
import tempfile
import requests
import shutil
import os
import sys
import pandas as pd
from PIL import Image, ImageDraw, ImageFilter
import io

counter = 0
DOWNLOAD_LIMIT = 100
def calculate_adjacent_coordinates(lat, lon, distance=10):

    olat = lat
    olon = lon
    R = 6378137  # Earth’s radius, sphere
    dLat = distance/R
    dLon = distance/(R * math.cos(math.pi * lat / 180))

    north = lat + dLat * 180/math.pi
    south = lat - dLat * 180/math.pi
    east = lon + dLon * 180/math.pi
    west = lon - dLon * 180/math.pi

    return {"origin": (olat,olon),"north": (north, lon), "south": (south, lon), "east": (lat, east), "west": (lat, west)}

def get_pano_metadata(lat, lon, api_key):

    url = f"https://maps.googleapis.com/maps/api/streetview/metadata?location={lat},{lon}&key={api_key}"
    response = requests.get(url)
    data = response.json()
    # print(data)
    if 'pano_id' in data and 'location' in data:
        return data['pano_id'], (data['location']['lat'], data['location']['lng'])
    else:
        return None, None

def calculate_heading(from_lat, from_lon, to_lat, to_lon):

    from_lat = math.radians(from_lat)
    from_lon = math.radians(from_lon)
    to_lat = math.radians(to_lat)
    to_lon = math.radians(to_lon)

    delta_lon = to_lon - from_lon

    x = math.sin(delta_lon) * math.cos(to_lat)
    y = math.cos(from_lat) * math.sin(to_lat) - (math.sin(from_lat) * math.cos(to_lat) * math.cos(delta_lon))
    heading = math.atan2(x, y)
    heading = math.degrees(heading)
    heading = (heading + 360) % 360

    return heading

def blur_specific_area(image, area):
    """
    在图像的指定区域应用模糊效果。
    area 是一个元组 (x1, y1, x2, y2)，指定了要模糊的区域。
    """
    # 裁剪出需要模糊的区域
    blur_area = image.crop(area)

    # 对这个区域应用模糊效果
    blur_area = blur_area.filter(ImageFilter.GaussianBlur(5))

    # 将模糊后的区域粘贴回原图
    image.paste(blur_area, area)

    return image

def save_street_view_image(pano_id, heading, api_key, directory, filename):
    """
    Save a Google Street View image for a given panoID and heading in the specified directory.
    """
    url = f"https://maps.googleapis.com/maps/api/streetview?size=600x300&fov=70&pano={pano_id}&heading={heading}&key={api_key}"
    response = requests.get(url, stream=True)

    if response.status_code == 200:
        with Image.open(io.BytesIO(response.content)) as image:
            # 模糊左下角区域
            left_bottom_area = (0, image.height - 22, 63, image.height)
            image = blur_specific_area(image, left_bottom_area)

            # 模糊右下角区域
            right_bottom_area = (image.width - 60, image.height - 25, image.width, image.height)
            image = blur_specific_area(image, right_bottom_area)

            # 保存修改后的图像
            image.save(os.path.join(directory, filename))
    else:
        print(f"Error: Failed to retrieve image for pano ID {pano_id}")

def one_row(original_coordinates,stop_name, file_name, stop_code, stop_id):
    api_key = 'AIzaSyBE_V_xPhwrmAvASI20hBPtdbPlW_YovlI'  # Replace with your Google API key
    parent_directory = file_name+"_imgs"  # Directory to save images
    lat, lon = original_coordinates
    if not os.path.exists(parent_directory):
        os.makedirs(parent_directory)
    
    images_directory = os.path.join(parent_directory, f"{stop_id}_{sanitize_filename(stop_name)}")
    # Create the directory if it doesn't exist
    if not os.path.exists(images_directory):
        os.makedirs(images_directory)

    # Calculate adjacent coordinates
    adjacent_coords = calculate_adjacent_coordinates(*original_coordinates)

    # Get panoIDs, their actual coordinates, and calculate headings for each position
    pano_data = {}
    for direction, coords in adjacent_coords.items():
        pano_id, pano_coords = get_pano_metadata(*coords, api_key)
        if pano_id and pano_id not in pano_data:
            heading = calculate_heading(*pano_coords, *original_coordinates)
            pano_data[pano_id] = {"coords": pano_coords, "heading": heading, "move":direction}

   
    # Retrieve and save images for each panoID
    for pano_id, data in pano_data.items():
        # filename = f"{sanitize_filename(stop_name)}_{data['move']}_{pano_id}_heading_{data['heading']}.jpg"
        if stop_code:
            filename = f"{data['move']}_{lat},{lon}_{stop_code}_{stop_id}.jpg"
        else:
            filename = f"{data['move']}_{lat},{lon}_{stop_id}.jpg"
        
        
        save_street_view_image(pano_id, data['heading'], api_key, images_directory, filename)
        
    global counter
    counter += 1
    print(counter)
    # print(stop_id)
    if counter >= DOWNLOAD_LIMIT:
            print("Reached download limit. Exiting...")
            sys.exit()  # 终止程序

def sanitize_filename(name):
    return "".join([c for c in name if c.isalnum() or c in ' -_().'])

def process_bus_stops_txt(file_path):

    file_name = os.path.splitext(os.path.basename(file_path))[0]
    with open(file_path, 'r') as file:

            headers = file.readline().strip().split(',')
            name_idx = headers.index('stop_name')
            lat_idx = headers.index('stop_lat')
            lon_idx = headers.index('stop_lon')
            if 'stop_code' in headers:
                code_idx = headers.index('stop_code')
            else:
                code_idx = None
            id_idx = headers.index('stop_id')

            for line in file:
                fields = line.strip().split(',')
                stop_name = fields[name_idx]
                stop_lat = float(fields[lat_idx])
                stop_lon = float(fields[lon_idx])
                if(code_idx):
                    stop_code = fields[code_idx]
                else:
                    stop_code = None
                stop_id = int(fields[id_idx])
                one_row((stop_lat, stop_lon), stop_name, file_name, stop_code, stop_id)

def process_bus_stops_xlsx(file_path):
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    df = pd.read_excel(file_path)
    for index, row in df.iterrows():
        stop_name = row['STOP_NAME']
        lat, lng = row['LATITUDE'], row['LONGITUDE']
        one_row((lat, lng), stop_name, file_name)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 script.py file.extension")
        return
    
    file_path = sys.argv[1]
    _, file_extension = os.path.splitext(file_path)

    if file_extension.lower() == '.txt':
        process_bus_stops_txt(file_path)
    elif file_extension.lower() == '.xlsx':
        process_bus_stops_xlsx(file_path)
    else:
        print("Unsupported file type.")

if __name__ == "__main__":
    main()
