import numpy as np
import cv2
from pathlib import Path
import random

class SyntheticDefectGenerator:
    """Generate synthetic defective samples for training"""
    
    def __init__(self, image_size=(224, 224)):
        self.image_size = image_size
        
    def generate_good_product(self):
        """Generate a good product image"""
        img = np.ones((*self.image_size, 3), dtype=np.uint8) * 200
        noise = np.random.normal(0, 10, img.shape).astype(np.uint8)
        img = cv2.add(img, noise)
        center = (self.image_size[0]//2, self.image_size[1]//2)
        radius = min(self.image_size) // 3
        cv2.circle(img, center, radius, (180, 180, 180), -1)
        return img
    
    def add_scratch_defect(self, image):
        """Add scratch defect to product"""
        img = image.copy()
        start_point = (random.randint(50, 150), random.randint(50, 150))
        end_point = (start_point[0] + random.randint(-50, 50), 
                     start_point[1] + random.randint(-50, 50))
        # Ensure coordinates are within image boundaries
        end_point = (max(10, min(self.image_size[0]-10, end_point[0])),
                     max(10, min(self.image_size[1]-10, end_point[1])))
        color = (random.randint(0, 50), random.randint(0, 50), random.randint(0, 50))
        thickness = random.randint(1, 3)
        cv2.line(img, start_point, end_point, color, thickness)
        return img
    
    def add_dent_defect(self, image):
        """Add dent defect to product"""
        img = image.copy()
        center = (random.randint(70, 150), random.randint(70, 150))
        radius = random.randint(5, 15)
        cv2.circle(img, center, radius, (50, 50, 50), -1)
        return img
    
    def add_discoloration_defect(self, image):
        """Add discoloration defect"""
        img = image.copy()
        x, y = random.randint(60, 160), random.randint(60, 160)
        w, h = random.randint(10, 30), random.randint(10, 30)
        discolored_color = (
            random.randint(100, 255),
            random.randint(100, 255),
            random.randint(100, 255)
        )
        cv2.rectangle(img, (x, y), (x+w, y+h), discolored_color, -1)
        return img

    def add_crack_defect(self, image):
        """Add jagged crack defect to product"""
        img = image.copy()
        start_x = random.randint(50, 150)
        start_y = random.randint(50, 150)
        points = [(start_x, start_y)]
        
        # Draw a jagged line
        length = random.randint(3, 6)
        curr_x, curr_y = start_x, start_y
        for _ in range(length):
            next_x = curr_x + random.randint(-20, 20)
            next_y = curr_y + random.randint(-20, 20)
            next_x = max(10, min(self.image_size[0] - 10, next_x))
            next_y = max(10, min(self.image_size[1] - 10, next_y))
            points.append((next_x, next_y))
            curr_x, curr_y = next_x, next_y
            
        color = (random.randint(0, 30), random.randint(0, 30), random.randint(0, 30))
        thickness = random.randint(1, 2)
        
        for i in range(len(points) - 1):
            cv2.line(img, points[i], points[i+1], color, thickness)
            
        return img
    
    def generate_dataset(self, num_samples=1000, output_dir='data'):
        """Generate synthetic dataset"""
        output_dir = Path(output_dir)
        
        classes = ['good', 'scratch', 'dent', 'discoloration', 'crack']
        for split in ['train', 'val', 'test']:
            for cls in classes:
                (output_dir / split / cls).mkdir(parents=True, exist_ok=True)
        
        defect_mapping = {
            'scratch': self.add_scratch_defect,
            'dent': self.add_dent_defect,
            'discoloration': self.add_discoloration_defect,
            'crack': self.add_crack_defect
        }
        
        for split, n in [('train', int(num_samples*0.7)), 
                         ('val', int(num_samples*0.15)), 
                         ('test', int(num_samples*0.15))]:
            
            # Generate good samples
            for i in range(n):
                good_img = self.generate_good_product()
                cv2.imwrite(
                    str(output_dir / split / 'good' / f'good_{i:04d}.jpg'),
                    good_img
                )
                
            # Generate defective samples split across folders
            defect_types = list(defect_mapping.keys())
            for i in range(n):
                defect_type = defect_types[i % len(defect_types)]
                defect_func = defect_mapping[defect_type]
                
                good_base = self.generate_good_product()
                defective_img = defect_func(good_base)
                
                cv2.imwrite(
                    str(output_dir / split / defect_type / f'{defect_type}_{i:04d}.jpg'),
                    defective_img
                )
        
        print(f"Generated {num_samples} samples in {output_dir}")

if __name__ == "__main__":
    generator = SyntheticDefectGenerator()
    generator.generate_dataset(num_samples=1000)
