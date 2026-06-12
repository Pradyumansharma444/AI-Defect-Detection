import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import matplotlib.pyplot as plt
from config import Config
import numpy as np
from pathlib import Path
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns
import json

def binary_generator_wrapper(generator):
    """Wraps a multi-class generator to yield binary labels (0 = good, 1 = defective)"""
    for x, y in generator:
        # y is categorical of shape (batch_size, 5)
        # Class index 0 is 'good', indices 1..4 are defects
        if len(y.shape) > 1 and y.shape[1] > 1:
            binary_y = 1.0 - y[:, 0]  # 0 if index 0 is 1, else 1
        else:
            binary_y = np.where(y == 0, 0.0, 1.0)
        yield x, binary_y

def autoencoder_generator_wrapper(generator):
    """Wraps a generator to yield (image, image) for autoencoder training"""
    for x, _ in generator:
        yield x, x

class DefectDetector:
    def __init__(self, config=None):
        self.config = config or Config()
        self.model = None
        self.history = None
        
    def build_model(self, transfer_learning=True):
        """Build the binary defect detection model"""
        if transfer_learning:
            # Use pre-trained ResNet50
            base_model = tf.keras.applications.ResNet50(
                weights='imagenet',
                include_top=False,
                input_shape=(*self.config.IMG_SIZE, 3)
            )
            base_model.trainable = False
            
            inputs = layers.Input(shape=(*self.config.IMG_SIZE, 3))
            x = tf.keras.applications.resnet50.preprocess_input(inputs)
            x = base_model(x, training=False)
            x = layers.GlobalAveragePooling2D()(x)
            x = layers.Dropout(0.2)(x)
            x = layers.Dense(256, activation='relu')(x)
            x = layers.Dropout(0.2)(x)
            outputs = layers.Dense(1, activation='sigmoid')(x)
            
            self.model = keras.Model(inputs, outputs, name='binary_defect_detector')
        else:
            # Build CNN from scratch
            self.model = keras.Sequential([
                layers.Conv2D(32, (3, 3), activation='relu', input_shape=(*self.config.IMG_SIZE, 3)),
                layers.MaxPooling2D(2, 2),
                layers.Conv2D(64, (3, 3), activation='relu'),
                layers.MaxPooling2D(2, 2),
                layers.Conv2D(64, (3, 3), activation='relu'),
                layers.MaxPooling2D(2, 2),
                layers.Conv2D(128, (3, 3), activation='relu'),
                layers.MaxPooling2D(2, 2),
                layers.Flatten(),
                layers.Dense(512, activation='relu'),
                layers.Dropout(0.5),
                layers.Dense(1, activation='sigmoid')
            ], name='binary_defect_detector_scratch')
        
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.config.LEARNING_RATE),
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.Precision(name='precision'), tf.keras.metrics.Recall(name='recall')]
        )
        return self.model
    
    def prepare_data(self, target_type='binary'):
        """Prepare data generators with augmentation based on target model type"""
        train_datagen = ImageDataGenerator(
            rescale=1./255,
            rotation_range=20,
            width_shift_range=0.2,
            height_shift_range=0.2,
            shear_range=0.2,
            zoom_range=0.2,
            horizontal_flip=True,
            fill_mode='nearest'
        )
        
        val_test_datagen = ImageDataGenerator(rescale=1./255)
        classes = ['good', 'scratch', 'dent', 'discoloration', 'crack']
        
        if target_type == 'anomaly':
            # Autoencoder only trains on GOOD images and requires shape (128, 128)
            train_generator = train_datagen.flow_from_directory(
                self.config.DATA_DIR / 'train',
                target_size=(128, 128),
                batch_size=self.config.BATCH_SIZE,
                class_mode='binary',
                classes=['good']
            )
            val_generator = val_test_datagen.flow_from_directory(
                self.config.DATA_DIR / 'val',
                target_size=(128, 128),
                batch_size=self.config.BATCH_SIZE,
                class_mode='binary',
                classes=['good']
            )
            return autoencoder_generator_wrapper(train_generator), autoencoder_generator_wrapper(val_generator), len(train_generator), len(val_generator)
            
        # For both binary and multi-class classification, load all classes
        train_generator = train_datagen.flow_from_directory(
            self.config.DATA_DIR / 'train',
            target_size=self.config.IMG_SIZE,
            batch_size=self.config.BATCH_SIZE,
            class_mode='categorical',
            classes=classes
        )
        
        val_generator = val_test_datagen.flow_from_directory(
            self.config.DATA_DIR / 'val',
            target_size=self.config.IMG_SIZE,
            batch_size=self.config.BATCH_SIZE,
            class_mode='categorical',
            classes=classes
        )
        
        if target_type == 'binary':
            return binary_generator_wrapper(train_generator), binary_generator_wrapper(val_generator), len(train_generator), len(val_generator)
        else:
            return train_generator, val_generator, len(train_generator), len(val_generator)
            
    def train(self, train_gen, val_gen, steps_per_epoch, validation_steps, epochs=None):
        """Train the loaded model"""
        epochs = epochs or self.config.EPOCHS
        
        callbacks = [
            keras.callbacks.EarlyStopping(monitor='val_loss', patience=6, restore_best_weights=True),
            keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, min_lr=1e-6)
        ]
        
        self.history = self.model.fit(
            train_gen,
            steps_per_epoch=steps_per_epoch,
            epochs=epochs,
            validation_data=val_gen,
            validation_steps=validation_steps,
            callbacks=callbacks
        )
        return self.history
        
    def plot_training_history(self, filename='training_history.png'):
        """Plot and save training metrics"""
        if self.history is None:
            print("No training history to plot.")
            return
            
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        axes[0].plot(self.history.history['loss'], label='Train')
        if 'val_loss' in self.history.history:
            axes[0].plot(self.history.history['val_loss'], label='Validation')
        axes[0].set_title('Loss History')
        axes[0].set_xlabel('Epoch')
        axes[0].set_ylabel('Loss')
        axes[0].legend()
        
        metric_name = 'accuracy' if 'accuracy' in self.history.history else 'mae'
        axes[1].plot(self.history.history[metric_name], label='Train')
        if f'val_{metric_name}' in self.history.history:
            axes[1].plot(self.history.history[f'val_{metric_name}'], label='Validation')
        axes[1].set_title(f'{metric_name.capitalize()} History')
        axes[1].set_xlabel('Epoch')
        axes[1].set_ylabel(metric_name.capitalize())
        axes[1].legend()
        
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
        print(f"Training history saved as {filename}")

    def save_model(self, model_path=None):
        path = model_path or (self.config.MODEL_DIR / self.config.MODEL_NAME)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.model.save(path)
        print(f"Model saved to {path}")

if __name__ == "__main__":
    detector = DefectDetector()
    detector.build_model(transfer_learning=True)
    print(detector.model.summary())
    train_gen, val_gen, steps, val_steps = detector.prepare_data('binary')
    history = detector.train(train_gen, val_gen, steps, val_steps, epochs=5)
    detector.plot_training_history()
    detector.save_model()
