import gradio as gr
from detect import DefectDetectionInference
import cv2
import numpy as np
from PIL import Image
import tempfile
import os

class DefectDetectionApp:
    def __init__(self):
        self.detector = DefectDetectionInference()
        
    def detect_and_visualize(self, image):
        """Process uploaded image and return results"""
        if isinstance(image, np.ndarray):
            img_array = image
        else:
            img_array = np.array(image)
        
        result = self.detector.predict(img_array)
        color = (0, 0, 255) if result['is_defective'] else (0, 255, 0)
        vis_image = img_array.copy()
        border_size = 10
        vis_image = cv2.copyMakeBorder(
            vis_image, border_size, border_size, border_size, border_size,
            cv2.BORDER_CONSTANT, value=color
        )
        text = f"{result['class']} - Confidence: {result['confidence']:.2%}"
        cv2.putText(
            vis_image,
            text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            color,
            2
        )
        return vis_image, result
    
    def create_interface(self):
        """Create Gradio interface"""
        with gr.Blocks(title="AI Defect Detection System") as interface:
            gr.Markdown("# 🔍 AI-Based Defect Detection System")
            gr.Markdown("Upload an image to detect manufacturing defects")
            
            with gr.Row():
                with gr.Column():
                    input_image = gr.Image(label="Upload Image", type="numpy")
                    detect_btn = gr.Button("Detect Defects", variant="primary")
                
                with gr.Column():
                    output_image = gr.Image(label="Detection Result")
                    result_text = gr.JSON(label="Detailed Results")
            
            gr.Examples(
                examples=["examples/good_product.jpg", "examples/defective_product.jpg"],
                inputs=input_image,
                label="Example Images"
            )
            
            detect_btn.click(
                fn=self.detect_and_visualize,
                inputs=[input_image],
                outputs=[output_image, result_text]
            )
        
        return interface

if __name__ == "__main__":
    app = DefectDetectionApp()
    interface = app.create_interface()
    interface.launch(share=False)
