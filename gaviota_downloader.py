import py7zr
import os
import shutil
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
BASE_URL = "https://chess.cygnitec.com/tablebases/gaviota/"
BASE_DIR = Path("gaviota_5")
MAX_WORKERS = 6  # Number of parallel downloads

def download_all_files() -> None:
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

def extract_all_files() -> None:

    print("\nExtracting files...\n")

    if os.path.exists("gaviota_5/temp3"):
        print(f"✓ 3.7z (already exists)")
    else:
        with py7zr.SevenZipFile('gaviota_5/3/3.7z', 'r') as archive:
            archive.extractall("gaviota_5/temp3")
        print(f"✓ 3.7z")
    os.remove("gaviota_5/3/3.7z")
    
    if os.path.exists("gaviota_5/temp4"):
        print(f"✓ 4.7z (already exists)")
    else:
        with py7zr.SevenZipFile('gaviota_5/4/4.7z', 'r') as archive:
            archive.extractall("gaviota_5/temp4")
        print(f"✓ 4.7z")
    os.remove("gaviota_5/4/4.7z")

    output_combined = 'gaviota_5/temp5combined.7z'
    if os.path.exists("gaviota_5/temp5combined.7z"):
        print(f"✓ {output_combined.split('/')[-1]} (already exists)")
    else:
        base_name = 'gaviota_5/5/5.7z'

        # 1. Merge parts into a single physical file
        with open(output_combined, 'wb') as output_file:
            part_num = 1
            while True:
                part_name = f"{base_name}.{part_num:03d}"
                try:
                    with open(part_name, 'rb') as part_file:
                        output_file.write(part_file.read())
                    os.remove(part_name)
                    print(f"✓ 5.7z.{part_num:03d}")
                    part_num += 1
                except FileNotFoundError:
                    break
        print(f"✓ {output_combined.split('/')[-1]}")

    # 2. Extract the new single file
    if os.path.exists("gaviota_5/temp5"):
        print("✓ 5.7z (already exists)")
    else:
        with py7zr.SevenZipFile(output_combined, mode='r') as archive:
            archive.extractall(path='gaviota_5/temp5')
        print("✓ 5.7z")
    os.remove("gaviota_5/temp5combined.7z")
    
    print("\nFiles extracted.")

def clean_all_files() -> None:
    dirs = os.listdir("gaviota_5/temp3/3")
    for dir in dirs:
        if dir.endswith(".cp4"):
            shutil.copy(f"gaviota_5/temp3/3/{dir}", "gaviota_5/3")
            os.remove(f"gaviota_5/temp3/3/{dir}")
            print(f"✓ {dir}")

    dirs = os.listdir("gaviota_5/temp4/4")
    for dir in dirs:
        if dir.endswith(".cp4"):
            shutil.copy(f"gaviota_5/temp4/4/{dir}", "gaviota_5/4")
            os.remove(f"gaviota_5/temp4/4/{dir}")
            print(f"✓ {dir}")

    dirs = os.listdir("gaviota_5/temp5/5")
    for dir in dirs:
        if dir.endswith(".cp4"):
            shutil.copy(f"gaviota_5/temp5/5/{dir}", "gaviota_5/5")
            os.remove(f"gaviota_5/temp5/5/{dir}")
            print(f"✓ {dir}")
    
    shutil.rmtree("gaviota_5/temp3")
    shutil.rmtree("gaviota_5/temp4")
    shutil.rmtree("gaviota_5/temp5")

def run_full_suite() -> None:
    shutil.rmtree("gaviota_5")
    download_all_files()
    extract_all_files()
    clean_all_files()

if __name__ == "__main__":
    run_full_suite()