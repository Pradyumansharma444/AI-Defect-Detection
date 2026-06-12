"""
Complete AI-Based Defect Detection System
Integrates all advanced features
"""

import argparse
import sys
import json
from pathlib import Path
import tensorflow as tf
import numpy as np


sys.path.append(str(Path(__file__).parent))

from models.multi_class_defect_detector import MultiClassDefectDetector
from models.yolo_defect_detector import YOLODefectDetector
from models.anomaly_detector import AnomalyDetector
from services.video_processor import VideoStreamProcessor
from services.edge_deployment import EdgeDefectDetector
from services.database import DefectDatabase
from services.alert_system import AlertSystem
from config import Config

class DefectDetectionSystem:
    """Main system integrating all defect detection features"""
    
    def __init__(self, config_path=None):
        self.config = Config()
        self.multi_class_detector = None
        self.yolo_detector = None
        self.anomaly_detector = None
        self.video_processor = None
        self.edge_detector = None
        self.database = DefectDatabase()
        self.alert_system = AlertSystem()
        self.alert_system.register_callback(self._handle_alert)
        
    def initialize_models(self, model_type='all'):
        print("Initializing models...")
        
        # Initialize multi-class detector
        if model_type in ['all', 'multi_class']:
            self.multi_class_detector = MultiClassDefectDetector(
                defect_classes=['scratch', 'dent', 'crack', 'discoloration']
            )
            model_path = self.config.MODEL_DIR / 'multi_class_defect_detector.h5'
            if model_path.exists():
                try:
                    self.multi_class_detector.model = tf.keras.models.load_model(model_path)
                    print("✓ Multi-class detector model loaded from disk")
                except Exception as e:
                    print(f"Error loading multi-class model: {e}. Building fallback.")
                    self.multi_class_detector.build_model()
            else:
                self.multi_class_detector.build_model()
                print("✓ Multi-class detector initialized (untrained)")
                
        # Initialize YOLO detector (with CV fallback)
        if model_type in ['all', 'yolo']:
            self.yolo_detector = YOLODefectDetector()
            print("✓ YOLO detector initialized")
            
        # Initialize anomaly detector
        if model_type in ['all', 'anomaly']:
            self.anomaly_detector = AnomalyDetector()
            model_path = self.config.MODEL_DIR / 'anomaly_detector.h5'
            threshold_path = self.config.MODEL_DIR / 'anomaly_threshold.json'
            
            if model_path.exists():
                try:
                    self.anomaly_detector.autoencoder = tf.keras.models.load_model(model_path)
                    if threshold_path.exists():
                        with open(threshold_path, 'r') as f:
                            self.anomaly_detector.threshold = json.load(f).get('threshold', 0.02)
                    else:
                        self.anomaly_detector.threshold = 0.02
                    print("✓ Anomaly detector model loaded from disk")
                except Exception as e:
                    print(f"Error loading anomaly model: {e}. Building fallback.")
                    self.anomaly_detector.build_autoencoder()
            else:
                self.anomaly_detector.build_autoencoder()
                print("✓ Anomaly detector initialized (untrained)")
                
        # Initialize edge detector
        if model_type in ['all', 'edge']:
            self.edge_detector = EdgeDefectDetector()
            print("✓ Edge detector initialized")
    
    def detect_image(self, image_path, use_model='all'):
        results = {}
        
        if use_model in ['all', 'multi_class'] and self.multi_class_detector:
            multi_result = self.multi_class_detector.predict_with_details(image_path)
            results['classification'] = multi_result
            
        if use_model in ['all', 'yolo'] and self.yolo_detector:
            yolo_result = self.yolo_detector.detect(image_path)
            results['detection'] = yolo_result
            
        if use_model in ['all', 'anomaly'] and self.anomaly_detector:
            anomaly_result = self.anomaly_detector.detect_anomaly(image_path)
            results['anomaly'] = anomaly_result
            
        is_defective = False
        if 'classification' in results:
            is_defective = is_defective or results['classification']['is_defective']
        if 'detection' in results:
            is_defective = is_defective or results['detection']['has_defects']
        if 'anomaly' in results:
            is_defective = is_defective or results['anomaly']['is_anomaly']
            
        results['overall'] = {
            'is_defective': is_defective,
            'defect_type': results.get('classification', {}).get('predicted_class', 'Unknown'),
            'severity': results.get('detection', {}).get('severity', {}).get('level', 'Unknown')
        }
        
        db_record = {
            'image_path': str(image_path),
            'model_type': use_model,
            'is_defective': is_defective,
            'defect_type': results['overall']['defect_type'],
            'confidence': results.get('classification', {}).get('confidence', 0.0),
            'severity': results['overall']['severity']
        }
        detection_id = self.database.insert_detection(db_record)
        
        if is_defective and results['overall']['severity'] in ['Critical', 'Major']:
            self.alert_system.send_alert(results['overall'], 'defect_detected')
            
        return results
    
    def start_video_processing(self, camera_id=0):
        self.video_processor = VideoStreamProcessor(
            defect_detector=self.yolo_detector,
            anomaly_detector=self.anomaly_detector
        )
        def on_defect_detected(detection_event):
            db_record = {
                'image_path': f"video_frame_{detection_event['timestamp']}",
                'model_type': 'yolo',
                'is_defective': True,
                'defect_type': detection_event['defects'][0]['class'] if detection_event['defects'] else 'Unknown',
                'confidence': detection_event['defects'][0]['confidence'] if detection_event['defects'] else 0.0,
                'severity': detection_event['severity']['level'] if 'level' in detection_event['severity'] else 'Unknown'
            }
            self.database.insert_detection(db_record)
            if db_record['severity'] in ['Critical', 'Major']:
                self.alert_system.send_alert(detection_event, 'video_defect')
                
        self.video_processor.on_defect_detected = on_defect_detected
        self.video_processor.start_camera(camera_id)
        self.video_processor.start_processing()
        print(f"Video processing started on camera {camera_id}")
        print("Press 'q' to quit")
    
    def deploy_to_edge(self, model_path, output_path):
        edge_detector = EdgeDefectDetector()
        edge_detector.convert_to_tflite(model_path, output_path, quantize=True)
        edge_detector.load_model(output_path)
        import numpy as np
        test_image = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        benchmark = edge_detector.benchmark(test_image)
        print(f"Edge deployment benchmark: {benchmark['fps']:.2f} FPS")
        return edge_detector
    
    def _handle_alert(self, alert_message):
        print(f"ALERT: {alert_message['subject']}")
        print(f"Message: {alert_message['body'][:200]}...")
    
    def start_dashboard(self):
        import subprocess
        import sys
        # Run streamlit command using the virtual environment's interpreter directly
        subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'dashboard/app.py'])


def main():
    parser = argparse.ArgumentParser(description='AI-Based Defect Detection System')
    parser.add_argument('--mode', choices=['image', 'video', 'dashboard', 'train', 'deploy'],
                       default='dashboard', help='Operation mode')
    parser.add_argument('--image', type=str, help='Path to image for detection')
    parser.add_argument('--camera', type=int, default=0, help='Camera ID for video processing')
    parser.add_argument('--model', type=str, help='Path to model file')
    parser.add_argument('--output', type=str, default='edge_model.tflite', help='Output path for edge model')
    parser.add_argument('--target', choices=['binary', 'multi_class', 'anomaly', 'all'],
                       default='binary', help='Target model to train')
    args = parser.parse_args()
    
    system = DefectDetectionSystem()
    
    if args.mode == 'image':
        if not args.image:
            print("Error: --image argument required for image mode")
            return
        system.initialize_models()
        results = system.detect_image(args.image)
        print(f"Detection Results:")
        print(f"  Defective: {results['overall']['is_defective']}")
        print(f"  Type: {results['overall']['defect_type']}")
        print(f"  Severity: {results['overall']['severity']}")
        
    elif args.mode == 'video':
        system.initialize_models('yolo')
        system.start_video_processing(args.camera)
        
    elif args.mode == 'dashboard':
        system.start_dashboard()
        
    elif args.mode == 'train':
        from train import DefectDetector
        target = args.target
        detector = DefectDetector()
        
        if target in ['binary', 'all']:
            print("--- Training Binary Defect Detector ---")
            detector.build_model(transfer_learning=True)
            train_gen, val_gen, steps, val_steps = detector.prepare_data('binary')
            detector.train(train_gen, val_gen, steps, val_steps, epochs=3)
            detector.save_model()
            detector.plot_training_history('binary_training_history.png')
            
        if target in ['multi_class', 'all']:
            print("--- Training Multi-Class Defect Detector ---")
            multi_detector = MultiClassDefectDetector()
            detector.model = multi_detector.build_model()
            train_gen, val_gen, steps, val_steps = detector.prepare_data('multi_class')
            detector.train(train_gen, val_gen, steps, val_steps, epochs=3)
            multi_detector.save_model(str(detector.config.MODEL_DIR / 'multi_class_defect_detector.h5'))
            detector.plot_training_history('multi_class_training_history.png')
            
        if target in ['anomaly', 'all']:
            print("--- Training Anomaly Autoencoder ---")
            anomaly_detector = AnomalyDetector()
            anomaly_detector.build_autoencoder()
            
            detector.model = anomaly_detector.autoencoder
            train_gen, val_gen, steps, val_steps = detector.prepare_data('anomaly')
            detector.train(train_gen, val_gen, steps, val_steps, epochs=3)
            
            # Save threshold
            val_datagen = tf.keras.preprocessing.image.ImageDataGenerator(rescale=1./255)
            val_gen_raw = val_datagen.flow_from_directory(
                detector.config.DATA_DIR / 'val',
                target_size=(128, 128),
                batch_size=32,
                class_mode='binary',
                classes=['good']
            )
            good_images = []
            for _ in range(min(5, len(val_gen_raw))):
                imgs, _ = next(val_gen_raw)
                good_images.append(imgs)
            if good_images:
                good_images = np.concatenate(good_images, axis=0)
                reconstructions = anomaly_detector.autoencoder.predict(good_images, verbose=0)
                mse = np.mean(np.square(good_images - reconstructions), axis=(1, 2, 3))
                anomaly_detector.threshold = float(np.mean(mse) + 3 * np.std(mse))
            else:
                anomaly_detector.threshold = 0.02
                
            print(f"Anomaly threshold set to: {anomaly_detector.threshold:.6f}")
            anomaly_detector.autoencoder.save(detector.config.MODEL_DIR / 'anomaly_detector.h5')
            threshold_path = detector.config.MODEL_DIR / 'anomaly_threshold.json'
            with open(threshold_path, 'w') as f:
                json.dump({'threshold': anomaly_detector.threshold}, f)
            print(f"Anomaly detector saved successfully")
            
    elif args.mode == 'deploy':
        if not args.model:
            print("Error: --model argument required for deploy mode")
            return
        edge_detector = system.deploy_to_edge(args.model, args.output)
        print(f"Model deployed to {args.output}")

if __name__ == "__main__":
    main()
