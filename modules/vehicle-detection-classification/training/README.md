# Specialised traffic YOLOv8 fine-tuning

This training job recognises these **single, mutually exclusive** classes:

| ID | Label | Include |
|---:|---|---|
| 0 | `two_wheeler` | motorcycles, mopeds, bicycles, e-bikes |
| 1 | `three_wheeler` | auto-rickshaws, tuk-tuks, cargo trikes |
| 2-4 | `ambulance`, `fire_truck`, `police_vehicle` | emergency vehicles |
| 5-7 | `taxi`, `delivery_van`, `semi_trailer` | commercial/fleet vehicles |
| 8-10 | `tractor`, `excavator`, `forklift` | heavy machinery |
| 11-12 | `electric_scooter`, `hoverboard` | micro-mobility |

Use the most specific applicable class. For example, a police motorcycle is `police_vehicle`, not `two_wheeler`; an emergency van is `ambulance`, not `delivery_van`. Do not annotate unrelated objects as any of these classes.

## Dataset layout

```
datasets/traffic_specialized/
  images/
    train/  val/  test/       # test is optional
  labels/
    train/  val/  test/       # matching .txt labels; a missing file means no target
```

Each YOLO label file has one normalized box per row:

```
class_id x_center y_center width height
```

## Dataset sources and limits

VisDrone provides annotations for `motor`, `tricycle`, and `awning-tricycle`, so it can contribute rows for IDs 0 and 1 after conversion. Its published detection labels do not cover ambulances, fire trucks, police vehicles, delivery vans, machinery, or micro-mobility. Add licensed, manually reviewed images for those labels; they must be annotated with the exact same taxonomy. Keep a validation set from locations/cameras different from the training set.

## Train

From the repository root:

```powershell
python training/train.py --epochs 100 --imgsz 960 --device 0
```

Use `--device cpu` if no NVIDIA GPU is available, though training will be much slower. The best weights are written to `runs/traffic_specialized/yolov8n/weights/best.pt`.

To use the model in the video app after training, point its YOLO load call at that `best.pt` and remove the current COCO `classes=[2, 3, 5, 7]` filter, because the custom model uses the IDs above.
