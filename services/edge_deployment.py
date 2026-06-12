import tensorflow as tf
import numpy as np
from pathlib import Path
import json
import time

class EdgeDefectDetector:
    """Deploy defect detection models to edge devices using TensorFlow Lite"""
    
    def __init__(self, model_path=None):
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.class_names = None
        
        if model_path:
            self.load_model(model_path)
    
    def convert_to_tflite(self, keras_model_path, output_path, quantize=True):
        model = tf.keras.models.load_model(keras_model_path)
        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        
        if quantize:
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            def representative_dataset():
                for _ in range(100):
                    data = np.random.randn(1, 224, 224, 3).astype(np.float32)
                    yield [data]
            converter.representative_dataset = representative_dataset
            converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            converter.inference_input_type = tf.uint8
            converter.inference_output_type = tf.uint8
        
        tflite_model = converter.convert()
        with open(output_path, 'wb') as f:
            f.write(tflite_model)
        
        model_size = len(tflite_model) / (1024 * 1024)
        metadata = {
            'original_model': str(keras_model_path),
            'quantized': quantize,
            'size_mb': round(model_size, 2),
            'conversion_date': str(time.strftime('%Y-%m-%d %H:%M:%S'))
        }
        
        with open(Path(output_path).with_suffix('.json'), 'w') as f:
            json.dump(metadata, f)
        
        print(f"Model converted successfully!")
        print(f"Size: {model_size:.2f} MB")
        print(f"Saved to: {output_path}")
        
        return output_path
    
    def load_model(self, model_path):
        self.interpreter = tf.lite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        class_path = Path(model_path).with_suffix('.json')
        if class_path.exists():
            with open(class_path, 'r') as f:
                self.class_names = json.load(f)
        
        print(f"Model loaded: {model_path}")
        print(f"Input shape: {self.input_details[0]['shape']}")
        print(f"Output shape: {self.output_details[0]['shape']}")
    
    def preprocess_image(self, image, input_shape):
        _, height, width, channels = input_shape
        
        if isinstance(image, str):
            image = tf.keras.preprocessing.image.load_img(image, target_size=(height, width))
            image = tf.keras.preprocessing.image.img_to_array(image)
        
        if image.shape[:2] != (height, width):
            image = tf.image.resize(image, (height, width))
        
        image = np.expand_dims(image, axis=0).astype(np.float32)
        
        if self.input_details[0]['dtype'] == np.uint8:
            image = (image * 255).astype(np.uint8)
        else:
            image = image / 255.0
        
        return image
    
    def predict(self, image):
        if self.interpreter is None:
            raise Exception("Model not loaded. Call load_model() first.")
        
        input_shape = self.input_details[0]['shape']
        processed_image = self.preprocess_image(image, input_shape)
        self.interpreter.set_tensor(self.input_details[0]['index'], processed_image)
        start_time = time.time()
        self.interpreter.invoke()
        inference_time = time.time() - start_time
        output = self.interpreter.get_tensor(self.output_details[0]['index'])
        prediction = output[0]
        
        if len(prediction.shape) == 1:
            predicted_class = np.argmax(prediction)
            confidence = float(prediction[predicted_class])
            return {
                'class_id': int(predicted_class),
                'class_name': self.class_names.get(str(predicted_class), f'Class_{predicted_class}') if self.class_names else f'Class_{predicted_class}',
                'confidence': confidence,
                'all_probabilities': prediction.tolist(),
                'inference_time_ms': inference_time * 1000
            }
        else:
            return {
                'output': prediction.tolist(),
                'inference_time_ms': inference_time * 1000
            }
    
    def benchmark(self, image, num_runs=100):
        times = []
        for _ in range(10):
            self.predict(image)
        for _ in range(num_runs):
            start = time.time()
            self.predict(image)
            times.append(time.time() - start)
        return {
            'avg_time_ms': np.mean(times) * 1000,
            'std_time_ms': np.std(times) * 1000,
            'min_time_ms': np.min(times) * 1000,
            'max_time_ms': np.max(times) * 1000,
            'fps': 1.0 / np.mean(times)
        }
