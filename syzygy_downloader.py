import py7zr
import os
import shutil
import requests
from pathlib import Path

# Configuration
BASE_URL = "https://chess.cygnitec.com/tablebases/syzygy/"
BASE_DIR = Path("syzygy")

def download_all_files() -> None:
    # Create download directory
    (BASE_DIR / "wdl").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "dtz").mkdir(parents=True, exist_ok=True)

    files = [
        "wdl/3/3.7z", "wdl/4/4.7z", "wdl/5/5.7z.001", "wdl/5/5.7z.002", "wdl/5/5.7z.003",
        "dtz/3/3.7z", "dtz/4/4.7z", "dtz/5/5.7z.001", "dtz/5/5.7z.002", "dtz/5/5.7z.003", "dtz/5/5.7z.004", "dtz/5/5.7z.005"
    ]

    print(f"Downloading {len(files)} files to: {BASE_DIR}\n")

    for file in files:
        filepath = BASE_DIR / file
        filename = file[:4] + file[6:]

        if filepath.exists():
            print(f"✓ {filename} (already exists)")
            continue

        try:
            response = requests.get(BASE_URL + file, stream=True)
            response.raise_for_status()

            with open("syzygy/" + filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"✓ {filename}")
        except Exception as e:
            print(f"✗ {filename}: {e}")

def extract_all_files() -> None:

    print("\nExtracting files...\n")

    if os.path.exists("syzygy/temp3"):
        print(f"✓ 3.7z (already exists)")
    else:
        with py7zr.SevenZipFile('syzygy/wdl/3.7z', 'r') as archive:
            archive.extractall("syzygy/temp3")
        print(f"✓ wdl/3.7z")
        with py7zr.SevenZipFile('syzygy/dtz/3.7z', 'r') as archive:
            archive.extractall("syzygy/temp3")
        print(f"✓ dtz/3.7z")
    os.remove("syzygy/wdl/3.7z")
    os.remove("syzygy/dtz/3.7z")
    
    if os.path.exists("syzygy/temp4"):
        print(f"✓ 4.7z (already exists)")
    else:
        with py7zr.SevenZipFile('syzygy/wdl/4.7z', 'r') as archive:
            archive.extractall("syzygy/temp4")
        print(f"✓ wdl/4.7z")
        with py7zr.SevenZipFile('syzygy/dtz/4.7z', 'r') as archive:
            archive.extractall("syzygy/temp4")
        print(f"✓ dtz/4.7z")
    os.remove("syzygy/wdl/4.7z")
    os.remove("syzygy/dtz/4.7z")

    output_combined = "syzygy/temp5combined.7z"
    if os.path.exists(output_combined):
        os.remove(output_combined)
    
    files = ["syzygy/wdl/5.7z.001", "syzygy/wdl/5.7z.002", "syzygy/wdl/5.7z.003"]

    # 1. Merge parts into a single physical file
    with open(output_combined, 'wb') as output_file:
        for file in files:
            with open(file, "rb") as part_file:
                output_file.write(part_file.read())
            os.remove(file)
            print(f"✓ {file}")
        print(f"✓ {output_combined.split('/')[-1]}")

    # 2. Extract the new single file
    if os.path.exists("syzygy/temp5"):
        print("✓ wdl/5.7z (already exists)")
        print("✓ dtz/5.7z (already exists)")
        print("\nFiles extracted.")
        return
    else:
        with py7zr.SevenZipFile(output_combined, mode='r') as archive:
            archive.extractall(path='syzygy/temp5')
        print("✓ wdl/5.7z")
    
    os.remove(output_combined)

    files = ["syzygy/dtz/5.7z.001", "syzygy/dtz/5.7z.002", "syzygy/dtz/5.7z.003", "syzygy/dtz/5.7z.004", "syzygy/dtz/5.7z.005"]

    # 1. Merge parts into a single physical file
    with open(output_combined, 'wb') as output_file:
        for file in files:
            with open(file, "rb") as part_file:
                output_file.write(part_file.read())
            os.remove(file)
            print(f"✓ {file}")
        print(f"✓ {output_combined.split('/')[-1]}")

    # 2. Extract the new single file
    with py7zr.SevenZipFile(output_combined, mode='r') as archive:
        archive.extractall(path='syzygy/temp5')
    print("✓ dtz/5.7z")
    os.remove("syzygy/temp5combined.7z")
    
    print("\nFiles extracted.")

def clean_all_files() -> None:
    dirs = os.listdir("syzygy/temp3/3")
    for dir in dirs:
        if dir != "md5sum":
            shutil.copy(f"syzygy/temp3/3/{dir}", "syzygy")
            os.remove(f"syzygy/temp3/3/{dir}")
            print(f"✓ {dir}")

    dirs = os.listdir("syzygy/temp4/4")
    for dir in dirs:
        if dir != "md5sum":
            shutil.copy(f"syzygy/temp4/4/{dir}", "syzygy")
            os.remove(f"syzygy/temp4/4/{dir}")
            print(f"✓ {dir}")

    dirs = os.listdir("syzygy/temp5/5")
    for dir in dirs:
        if dir != "md5sum":
            shutil.copy(f"syzygy/temp5/5/{dir}", "syzygy")
            os.remove(f"syzygy/temp5/5/{dir}")
            print(f"✓ {dir}")
    
    shutil.rmtree("syzygy/temp3")
    shutil.rmtree("syzygy/temp4")
    shutil.rmtree("syzygy/temp5")

    shutil.rmtree("syzygy/dtz")
    shutil.rmtree("syzygy/wdl")

def run_full_suite() -> None:
    if os.path.exists("syzygy"):
        shutil.rmtree("syzygy")
    download_all_files()
    extract_all_files()
    clean_all_files()

if __name__ == "__main__":
    run_full_suite()
