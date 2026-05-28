import os
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
BASE_URL = "https://chess.cygnitec.com/tablebases/gaviota/"
BASE_DIR = Path("gaviota_5")
MAX_WORKERS = 6  # Number of parallel downloads

# Create download directory
(BASE_DIR / "3").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "4").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "5").mkdir(parents=True, exist_ok=True)

files = [f"5/5.7z.{i:03d}" for i in range(1, 54)]
file_urls = [BASE_URL + filename for filename in files]

print(f"Downloading {len(file_urls)} files to: {BASE_DIR}\n")

# Download function
def download_file(url, folder = 5):
    filename = url.split('/')[-1]
    filepath = BASE_DIR / str(folder) / filename
    
    if filepath.exists():
        print(f"✓ {filename} (already exists)")
        return
    
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
        
        print(f"✓ {filename}")
    except Exception as e:
        print(f"✗ {filename}: {e}")

download_file(BASE_URL + "3/3.7z", 3)
download_file(BASE_URL + "4/4.7z", 4)

# Download files in parallel
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(download_file, url) for url in file_urls]
    for future in as_completed(futures):
        future.result()

print(f"\n✓ Download complete! You now have all 53 parts.")
print(f"\nNext step: Extract with 7-Zip")
print(f"1. Install 7-Zip from https://www.7-zip.org/")
print(f"2. Right-click on 5.7z.001 → 7-Zip → Extract Here")