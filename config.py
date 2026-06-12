import os
from pathlib import Path

class Config:
    # Paths
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / 'data'
    MODEL_DIR = BASE_DIR / 'models'
    EXPORT_DIR = BASE_DIR / 'exports'
    
    # Training parameters
    IMG_SIZE = (224, 224)
    BATCH_SIZE = 32
    EPOCHS = 50
    LEARNING_RATE = 0.001
    
    # Model parameters
    MODEL_NAME = 'resnet50_defect_detector.h5'
    
    # Detection threshold
    DEFECT_THRESHOLD = 0.5
    
    # Classes
    CLASSES = ['good', 'defective']
    NUM_CLASSES = len(CLASSES)
