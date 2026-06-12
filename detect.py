import cv2
import numpy as np
import tensorflow as tf
from config import Config
import matplotlib.pyplot as plt
from PIL import Image
from pathlib import Path

class DefectDetectionInference:
    def __init__(self, model_path=None):
        self.config = Config()
        self.model_path = model_path or (self.config.MODEL_DIR / self.config.MODEL_NAME)
        
        if not Path(self.model_path).exists():
            print(f"Warning: Model file not found at {self.model_path}. Building untrained fallback model...")
            from train import DefectDetector
            detector = DefectDetector(self.config)
            self.model = detector.build_model(transfer_learning=True)
        else:
            try:
                self.model = tf.keras.models.load_model(self.model_path)
                print(f"✓ Model loaded successfully from {self.model_path}")
            except Exception as e:
                print(f"Error loading model: {e}. Rebuilding untrained fallback model...")
                from train import DefectDetector
                detector = DefectDetector(self.config)
                self.model = detector.build_model(transfer_learning=True)
        
    def preprocess_image(self, image):
        """Preprocess image for inference"""
        if isinstance(image, str):
            image = cv2.imread(image)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        elif isinstance(image, Image.Image):
            image = np.array(image)
            
        # Ensure image has shape (H, W, 3)
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[-1] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            
        image_resized = cv2.resize(image, self.config.IMG_SIZE)
        image_normalized = image_resized / 255.0
        image_batch = np.expand_dims(image_normalized, axis=0)
        
        return image_batch, image
    
    def predict(self, image):
        """Make prediction on single image"""
        processed_image, original_image = self.preprocess_image(image)
        prediction = self.model.predict(processed_image, verbose=0)[0][0]
        is_defective = prediction > self.config.DEFECT_THRESHOLD
        confidence = prediction if is_defective else 1.0 - prediction
        return {
            'is_defective': bool(is_defective),
            'class': 'Defective' if is_defective else 'Good',
            'confidence': float(confidence),
            'raw_prediction': float(prediction)
        }
    
    def visualize_prediction(self, image, prediction_result):
        """Visualize the prediction on the image"""
        if isinstance(image, str):
            image = cv2.imread(image)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        plt.figure(figsize=(10, 8))
        plt.imshow(image)
        color = 'red' if prediction_result['is_defective'] else 'green'
        text = f"{prediction_result['class']}: {prediction_result['confidence']:.2%}"
        plt.title(text, color=color, fontsize=16, fontweight='bold')
        plt.axis('off')
        plt.show()
        
    def detect_defects_in_batch(self, image_paths):
        """Process multiple images"""
        results = []
        for img_path in image_paths:
            result = self.predict(img_path)
            result['image_path'] = img_path
            results.append(result)
        return results
    
    def generate_heatmap(self, image):
        """Generate Grad-CAM heatmap for model interpretability"""
        try:
            processed_image, original_image = self.preprocess_image(image)
            
            # Find base model if nested (ResNet50 transfer learning model)
            base_model = None
            for layer in self.model.layers:
                if isinstance(layer, tf.keras.Model) or layer.name == 'resnet50':
                    base_model = layer
                    break
                    
            if base_model is not None:
                # Find last conv layer in ResNet50
                conv_layer_name = None
                for layer in reversed(base_model.layers):
                    if 'conv' in layer.name or 'out' in layer.name or 'add' in layer.name:
                        conv_layer_name = layer.name
                        break
                if conv_layer_name is None:
                    return None
                
                conv_layer = base_model.get_layer(conv_layer_name)
                grad_model = tf.keras.models.Model(
                    inputs=self.model.inputs,
                    outputs=[conv_layer.output, self.model.output]
                )
            else:
                # Scratch model
                last_conv_layer = None
                for layer in reversed(self.model.layers):
                    if 'conv' in layer.name:
                        last_conv_layer = layer
                        break
                if last_conv_layer is None:
                    return None
                grad_model = tf.keras.models.Model(
                    inputs=self.model.inputs,
                    outputs=[last_conv_layer.output, self.model.output]
                )
            
            with tf.GradientTape() as tape:
                conv_outputs, predictions = grad_model(processed_image)
                loss = predictions[:, 0]
                
            grads = tape.gradient(loss, conv_outputs)
            pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
            
            conv_outputs = conv_outputs[0]
            heatmap = tf.reduce_sum(tf.multiply(pooled_grads, conv_outputs), axis=-1)
            
            heatmap = np.maximum(heatmap, 0)
            max_val = np.max(heatmap)
            if max_val == 0:
                max_val = 1e-8
            heatmap = heatmap / max_val
            return heatmap
        except Exception as e:
            print(f"Error generating Grad-CAM: {e}")
            return None

    def get_gradcam_image(self, image, heatmap, alpha=0.4):
        """Overlay the heatmap on the original image"""
        try:
            if heatmap is None:
                return image
                
            if isinstance(image, str):
                image = cv2.imread(image)
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            elif isinstance(image, Image.Image):
                image = np.array(image)
                
            # Resize heatmap to match original image size
            heatmap_resized = cv2.resize(heatmap, (image.shape[1], image.shape[0]))
            heatmap_color = np.uint8(255 * heatmap_resized)
            heatmap_color = cv2.applyColorMap(heatmap_color, cv2.COLORMAP_JET)
            heatmap_color = cv2.cvtColor(heatmap_color, cv2.COLOR_BGR2RGB)
            
            superimposed_img = cv2.addWeighted(image, 1.0 - alpha, heatmap_color, alpha, 0)
            return superimposed_img
        except Exception as e:
            print(f"Error overlaying heatmap: {e}")
            return image
