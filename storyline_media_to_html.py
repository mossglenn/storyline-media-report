import zipfile
import tempfile
import shutil
import os
import hashlib
import base64
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from PIL import Image
import argparse

THUMBNAIL_WIDTH = 150
HTML_OUTPUT = "storyline_media_report.html"

def extract_story_archive(story_file):
    tmp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(story_file, 'r') as zip_ref:
        zip_ref.extractall(tmp_dir)
    return tmp_dir

def get_md5(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def create_thumbnail(img_path, max_width):
    img = Image.open(img_path)
    width_percent = (max_width / float(img.size[0]))
    height = int((float(img.size[1]) * float(width_percent)))
    img = img.resize((max_width, height), Image.LANCZOS)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    return img

def image_to_base64(img):
    from io import BytesIO
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def parse_media_info(story_xml_path, media_dir):
    tree = ET.parse(story_xml_path)
    root = tree.getroot()
    media_elements = root.findall(".//mediaLst/mediaLst/media")

    file_md5_map = {}
    for file in os.listdir(media_dir):
        fpath = Path(media_dir) / file
        if fpath.is_file():
            file_md5_map[get_md5(fpath)] = fpath

    entries = []
    for media in media_elements:
        note = media.attrib.get("note", "")
        alt = media.findtext("altText", default="")
        checksum = media.findtext("md5Checksum/stream", default="").lower()
        if checksum in file_md5_map:
            img_path = file_md5_map[checksum]
            thumb = create_thumbnail(img_path, THUMBNAIL_WIDTH)
            b64 = image_to_base64(thumb)
            entries.append((b64, alt, note))
    return entries

def generate_html(entries, output_path, source_file):
    today = datetime.now().strftime("%Y-%m-%d")
    with open(output_path, "w") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Storyline Media Report</title>
<style>
body {{ font-family: sans-serif; padding: 20px; background-color: #fff; }}
h1 {{ text-align: center; }}
.cell {{
  margin-bottom: 20px;
  padding: 10px;
  border: 1px solid #ccc;
  background: #f9f9f9;
  max-width: 300px;
}}
img {{
  width: 100px;
  height: auto;
  display: block;
  margin-bottom: 10px;
}}
.alt {{ font-weight: bold; font-size: 0.9em; }}
.note {{ font-size: 0.85em; color: #333; }}
</style>
</head>
<body>
<h1>Storyline Media Report</h1>
<p style="text-align:center;">Source File: {Path(source_file).name} | Generated: {today}</p>
<div>
""")
        for b64, alt, note in entries:
            f.write(f"""<div class="cell">
<img src="data:image/jpeg;base64,{b64}" alt="{alt}">
<div class="alt">Alt: {alt}</div>
<div class="note">Note: {note}</div>
</div>\n""")
        f.write("</div></body></html>")

def main():
    parser = argparse.ArgumentParser(description="Generate Storyline Media HTML Report")
    parser.add_argument("story_file", help=".story file to process")
    args = parser.parse_args()

    if not os.path.isfile(args.story_file):
        print("❌ File not found:", args.story_file)
        return

    print("📦 Extracting .story archive...")
    tmp_dir = extract_story_archive(args.story_file)
    story_xml = Path(tmp_dir) / "story" / "story.xml"
    media_dir = Path(tmp_dir) / "story" / "media"

    print("🔍 Parsing media info...")
    entries = parse_media_info(story_xml, media_dir)

    print(f"🖼️ Found {len(entries)} matched media items. Generating HTML...")
    generate_html(entries, HTML_OUTPUT, args.story_file)

    shutil.rmtree(tmp_dir)
    print(f"✅ HTML saved to: {HTML_OUTPUT}")

if __name__ == "__main__":
    main()
