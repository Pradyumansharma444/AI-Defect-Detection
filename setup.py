from setuptools import setup, find_packages

setup(
    name="defect-detection-system",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        'tensorflow>=2.13.0',
        'torch>=2.0.1',
        'torchvision>=0.15.2',
        'opencv-python>=4.8.1',
        'numpy>=1.24.3',
        'matplotlib>=3.7.2',
        'streamlit>=1.27.0',
        'plotly>=5.17.0',
        'pandas>=2.0.3',
        'twilio>=8.9.0'
    ],
    entry_points={
        'console_scripts': [
            'defect-detect=main:main',
            'defect-dashboard=dashboard.app:main',
        ],
    },
    author="Your Name",
    description="AI-Based Defect Detection System with Advanced Features",
    python_requires='>=3.8',
)
