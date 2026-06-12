# AI Defect Detection System

## Overview

AI Defect Detection System is a Computer Vision and Deep Learning based application designed to automatically identify manufacturing defects from product images.

The system classifies images into multiple categories including:

* Crack
* Dent
* Scratch
* Discoloration
* Good (No Defect)

The project includes model training, defect prediction, and an interactive Streamlit dashboard for visualization and monitoring.

---

## Features

✅ Multi-Class Defect Detection

✅ Deep Learning Based Image Classification

✅ Interactive Streamlit Dashboard

✅ Real-Time Image Prediction

✅ Model Training Pipeline

✅ Performance Visualization

✅ Configurable Alert System

✅ Structured Dataset Management

---

## Defect Categories

| Class         | Description              |
| ------------- | ------------------------ |
| Good          | Defect-Free Product      |
| Crack         | Surface Cracks           |
| Dent          | Physical Deformation     |
| Scratch       | Surface Scratches        |
| Discoloration | Color or Texture Defects |

---

## Project Structure

```text
AI-Defect-Detection/
│
├── app.py
├── train.py
├── detect.py
├── config.py
├── alert_config.json
│
├── dashboard/
│   ├── __init__.py
│   └── app.py
│
├── data/
│   ├── train/
│   └── test/
│
├── binary_training_history.png
│
└── README.md
```

---

## Technology Stack

### Programming Language

* Python

### Machine Learning / AI

* TensorFlow / Keras
* NumPy
* OpenCV

### Visualization

* Matplotlib
* Plotly

### Dashboard

* Streamlit

### Data Processing

* Pandas

---

## Installation

### Clone Repository

```bash
git clone https://github.com/Pradyumansharma444/AI-Defect-Detection.git
cd AI-Defect-Detection
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Environment

Windows

```bash
venv\Scripts\activate
```

Linux / Mac

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Train Model

```bash
python train.py
```

---

## Run Defect Detection

```bash
python detect.py
```

---

## Launch Dashboard

```bash
streamlit run app.py
```

or

```bash
streamlit run dashboard/app.py
```

---

## Workflow

1. Collect product images.
2. Organize images into defect categories.
3. Train the deep learning model.
4. Evaluate model performance.
5. Upload new product images.
6. Predict defect type.
7. Visualize results through dashboard.

---

## Dataset

The dataset contains thousands of labeled images divided into:

* Training Set
* Testing Set

Classes:

* Good
* Crack
* Dent
* Scratch
* Discoloration

---

## Future Improvements

* Object Detection Support
* Defect Localization using Bounding Boxes
* Model Explainability
* Cloud Deployment
* Real-Time Camera Inspection
* Industrial IoT Integration

---

## Author

Pradyuman Sharma

Software Developer | AI & Machine Learning Enthusiast

GitHub:
https://github.com/Pradyumansharma444

---

## License

This project is intended for educational, research, and industrial learning purposes.
