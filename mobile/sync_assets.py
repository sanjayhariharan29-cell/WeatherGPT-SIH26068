"""
WeatherGPT Mobile Asset Synchronizer
Synchronizes frontend web assets to android/app/src/main/assets/public
for native Android / Capacitor packaging.
"""

import os
import shutil
import json

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
ANDROID_ASSETS_DIR = os.path.join(REPO_ROOT, "android", "app", "src", "main", "assets")
ANDROID_PUBLIC_DIR = os.path.join(ANDROID_ASSETS_DIR, "public")
CAP_CONFIG_SRC = os.path.join(REPO_ROOT, "capacitor.config.json")
CAP_CONFIG_DEST = os.path.join(ANDROID_ASSETS_DIR, "capacitor.config.json")

def sync_assets():
    print(f"Syncing web assets from {FRONTEND_DIR} to {ANDROID_PUBLIC_DIR}...")
    
    # Ensure destination directories exist
    os.makedirs(ANDROID_PUBLIC_DIR, exist_ok=True)
    
    # Copy frontend directory tree
    for item in os.listdir(FRONTEND_DIR):
        src_path = os.path.join(FRONTEND_DIR, item)
        dest_path = os.path.join(ANDROID_PUBLIC_DIR, item)
        
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            print(f"  [DIR]  {item}/ -> assets/public/{item}/")
        else:
            shutil.copy2(src_path, dest_path)
            print(f"  [FILE] {item} -> assets/public/{item}")
            
    # Copy capacitor.config.json to assets root
    if os.path.exists(CAP_CONFIG_SRC):
        shutil.copy2(CAP_CONFIG_SRC, CAP_CONFIG_DEST)
        print(f"  [CFG]  capacitor.config.json -> assets/capacitor.config.json")
        
    # Write empty capacitor.plugins.json if not present
    plugins_path = os.path.join(ANDROID_ASSETS_DIR, "capacitor.plugins.json")
    if not os.path.exists(plugins_path):
        with open(plugins_path, "w", encoding="utf-8") as f:
            json.dump([], f)
        print("  [PLUG] created assets/capacitor.plugins.json")
        
    print("Capacitor Android asset synchronization completed successfully!")

if __name__ == "__main__":
    sync_assets()
