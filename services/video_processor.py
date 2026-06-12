import cv2
import numpy as np
import threading
import queue
import time
from datetime import datetime
from collections import deque
import asyncio

class VideoStreamProcessor:
    """Real-time video processing for defect detection"""
    
    def __init__(self, defect_detector, anomaly_detector=None):
        self.defect_detector = defect_detector
        self.anomaly_detector = anomaly_detector
        
        self.camera = None
        self.processing_thread = None
        self.is_running = False
        
        self.raw_queue = queue.Queue(maxsize=10)
        self.processed_queue = queue.Queue(maxsize=10)
        
        self.fps_history = deque(maxlen=100)
        self.detection_history = deque(maxlen=1000)
        self.current_fps = 0
        
        self.on_defect_detected = None
        self.on_frame_processed = None
        
    def start_camera(self, camera_id=0, width=640, height=480):
        self.camera = cv2.VideoCapture(camera_id)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.camera.set(cv2.CAP_PROP_FPS, 30)
        
        if not self.camera.isOpened():
            raise Exception("Could not open camera")
        
        return True
    
    def start_processing(self):
        if self.is_running:
            return
        
        self.is_running = True
        capture_thread = threading.Thread(target=self._capture_frames)
        capture_thread.daemon = True
        capture_thread.start()
        
        self.processing_thread = threading.Thread(target=self._process_frames)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        display_thread = threading.Thread(target=self._display_frames)
        display_thread.daemon = True
        display_thread.start()
    
    def stop_processing(self):
        self.is_running = False
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()
    
    def _capture_frames(self):
        frame_count = 0
        fps_start_time = time.time()
        
        while self.is_running:
            ret, frame = self.camera.read()
            if not ret:
                print("Failed to grab frame")
                break
            
            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - fps_start_time
                self.current_fps = 30 / elapsed
                self.fps_history.append(self.current_fps)
                fps_start_time = time.time()
            
            timestamp = datetime.now()
            if not self.raw_queue.full():
                self.raw_queue.put((frame, timestamp))
            
            time.sleep(0.001)
    
    def _process_frames(self):
        while self.is_running:
            if not self.raw_queue.empty():
                frame, timestamp = self.raw_queue.get()
                
                try:
                    if self.defect_detector:
                        result = self.defect_detector.detect(frame, visualize=True)
                        annotated_frame = result.get('annotated_image', frame)
                        
                        if result.get('has_defects', False):
                            detection_event = {
                                'timestamp': timestamp,
                                'defects': result['defects'],
                                'severity': result.get('severity', {}),
                                'frame': annotated_frame
                            }
                            self.detection_history.append(detection_event)
                            if self.on_defect_detected:
                                self.on_defect_detected(detection_event)
                    else:
                        annotated_frame = frame
                    
                    anomaly_result = None
                    if self.anomaly_detector:
                        anomaly_result = self.anomaly_detector.detect_anomaly(frame)
                        if anomaly_result['is_anomaly']:
                            heatmap = anomaly_result['error_map']
                            heatmap_colored = cv2.applyColorMap(
                                (heatmap * 255).astype(np.uint8), 
                                cv2.COLORMAP_JET
                            )
                            annotated_frame = cv2.addWeighted(
                                annotated_frame, 0.7, 
                                cv2.resize(heatmap_colored, (annotated_frame.shape[1], annotated_frame.shape[0])), 
                                0.3, 0
                            )
                    
                    annotated_frame = self._add_overlay(annotated_frame, result if self.defect_detector else None, anomaly_result)
                    if not self.processed_queue.full():
                        self.processed_queue.put(annotated_frame)
                    
                    if self.on_frame_processed:
                        self.on_frame_processed(annotated_frame, result, anomaly_result)
                except Exception as e:
                    print(f"Error processing frame: {e}")
                    if not self.processed_queue.full():
                        self.processed_queue.put(frame)
    
    def _add_overlay(self, frame, defect_result=None, anomaly_result=None):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 120), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)
        
        cv2.putText(frame, f"FPS: {self.current_fps:.1f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        y_offset = 90
        if defect_result and defect_result.get('has_defects'):
            severity = defect_result.get('severity', {}).get('level', 'Unknown')
            color = (0, 0, 255) if severity == 'Critical' else (0, 255, 255)
            cv2.putText(frame, f"DEFECTS: {defect_result['num_defects']} ({severity})", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        if anomaly_result and anomaly_result['is_anomaly']:
            y_offset += 25
            cv2.putText(frame, f"ANOMALY: Score {anomaly_result['anomaly_score']:.1f}%", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
        
        return frame
    
    def _display_frames(self):
        cv2.namedWindow('Defect Detection Live', cv2.WINDOW_NORMAL)
        
        while self.is_running:
            if not self.processed_queue.empty():
                frame = self.processed_queue.get()
                cv2.imshow('Defect Detection Live', frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_processing()
                    break
    
    def get_statistics(self):
        return {
            'current_fps': self.current_fps,
            'average_fps': np.mean(self.fps_history) if self.fps_history else 0,
            'total_detections': len(self.detection_history),
            'recent_detections': list(self.detection_history)[-10:],
            'defect_rate': len([d for d in self.detection_history if d.get('severity', {}).get('level') in ['Critical', 'Major']]) / max(1, len(self.detection_history))
        }
