import os
import glob
import csv
import cv2
from ultralytics import YOLO
import supervision as sv
from collections import Counter

# 类别
classes_of_interest = ['bench', 'large bike rack', 'shelter', 'sign', 'small bike rack']

# 加载 YOLOv8 模型和权重
model = YOLO('../runs/detect/train11/weights/best.pt')


def process_folder(folder):
    image_files = glob.glob(f'{folder}/*.jpg')

    # 从文件夹名称提取 stop_id
    folder_name = [part for part in folder.split('/') if part][-1]
    stop_id = folder_name.split('_')[0]

    if not image_files:

        return [stop_id] + [None for _ in range(len(classes_of_interest) + 3)]  

    total_counts = Counter()
    total_images = len(image_files)

    first_image = image_files[0]
    _, latlon, _ = os.path.basename(first_image).split('_')[0:3]
    lat, lon = latlon.split(',')

    for image_path in glob.glob(f'{folder}/*.jpg'):
        # image = cv2.imread(image_path)
        results = model.predict(image_path, save=True, imgsz=320, conf=0.5)
        # results = model(image)
        detections = sv.Detections.from_ultralytics(results[0])

        
        detected_classes = set(detections.class_id)
        for class_name in classes_of_interest:
            if classes_of_interest.index(class_name) in detected_classes:
                total_counts[class_name] += 1

    with open(os.path.join(folder, 'detection_summary.txt'), 'w') as file:
        for class_name, count in total_counts.items():
            file.write(f'{class_name}: {count}/{total_images}\n')  # 输出比例

    return [stop_id, lat, lon] + [total_counts[class_name] for class_name in classes_of_interest] + [total_images]

def main():

    # 遍历所有城市级别的文件夹
    for parent_folder in glob.glob('./*_stops_imgs/'):
        city_name = [part for part in parent_folder.split('/') if part][-1]
        city_name = city_name.split("_stops_imgs")[0]
        csv_filename = os.path.join(parent_folder, f'{city_name}_stops_analysis.csv')
        # 遍历大文件夹内的所有子文件夹

        with open(csv_filename, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(['stop_id', 'lat', 'lon'] + classes_of_interest + ['total'])

            for sub_folder in glob.glob(f'{parent_folder}/*/'):
                row = process_folder(sub_folder)
                csvwriter.writerow(row)

if __name__ == '__main__':
    main()
