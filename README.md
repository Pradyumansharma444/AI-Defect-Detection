# AI-Based Defect Detection System

## Features

- ✅ Multi-class Defect Classification
- ✅ Object Detection with YOLO
- ✅ Anomaly Detection with Autoencoders
- ✅ Real-time Video Processing
- ✅ Edge Deployment (TensorFlow Lite)
- ✅ Database Integration
- ✅ Alert System (Email/SMS/Slack)
- ✅ Real-time Dashboard

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Generate Synthetic Dataset

```bash
python utils/data_generator.py
```

### Train the Model

```bash
python train.py
```

### Detect Defects in an Image

```bash
python main.py --mode image --image path/to/image.jpg
```

### Start Real-time Video Processing

```bash
python main.py --mode video --camera 0
```

### Launch Dashboard

```bash
python main.py --mode dashboard
```

### Deploy to Edge

```bash
python main.py --mode deploy --model models/defect_detector.h5
```

## Project Structure

```
defect_detection_system/
├── models/
│   ├── __init__.py
│   ├── multi_class_defect_detector.py
│   ├── yolo_defect_detector.py
│   └── anomaly_detector.py
├── services/
│   ├── __init__.py
│   ├── video_processor.py
│   ├── edge_deployment.py
│   ├── database.py
│   └── alert_system.py
├── dashboard/
│   ├── __init__.py
│   └── app.py
├── utils/
│   ├── __init__.py
│   └── data_generator.py
├── data/
│   ├── train/
│   │   ├── good/
│   │   └── defective/
│   ├── val/
│   │   ├── good/
│   │   └── defective/
│   └── test/
│       ├── good/
│       └── defective/
├── config.py
├── train.py
├── detect.py
├── app.py
├── main.py
├── setup.py
├── requirements.txt
└── README.md
```

## Configuration

Edit `config.py` to adjust model parameters.
Edit `alert_config.json` to configure email, SMS, and Slack alerts.
