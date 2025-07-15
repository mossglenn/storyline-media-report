import zipfile
import tempfile
import shutil
import os
import hashlib
import xml.etree.ElementTree as ET
from PIL import Image
from fpdf import FPDF
from pathlib import Path
from datetime import datetime

# --- CONFIG ---
THUMBNAIL_WIDTH = 150
PDF_OUTPUT = "storyline_media_report.pdf"
GRID_COLS = 3
GRID_CELL_WIDTH = 60  # Adjusted width to fit 3 columns comfortably
GRID_CELL_HEIGHT = 80  # Approximate total height per cell (image + text)
GRID_MARGIN = 10

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
    thumb_path = img_path.with_name("thumb_" + img_path.stem + ".jpg")
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(thumb_path)
    return thumb_path

def parse_media_info(story_xml_path, media_dir):
    tree = ET.parse(story_xml_path)
    root = tree.getroot()
    media_elements = root.findall(".//mediaLst/mediaLst/media")

    # Build MD5-to-file map
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
            thumb_path = create_thumbnail(img_path, THUMBNAIL_WIDTH)
            entries.append((thumb_path, alt, note))
    return entries

def generate_pdf(entries, output_path, source_file):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    # Title section
    pdf.set_font("Arial", "B", size=14)
    pdf.cell(0, 10, "Storyline Media Report", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Source File: {Path(source_file).name}", ln=True, align="C")
    pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", size=10)

    cell_width = GRID_CELL_WIDTH
    cell_height = GRID_CELL_HEIGHT
    margin = GRID_MARGIN
    cols = GRID_COLS
    x_start = margin
    y_start = pdf.get_y()
    current_x = x_start
    current_y = y_start
    col_index = 0
    row_height = 0

    for i, (img_path, alt_text, note) in enumerate(entries):
        if col_index >= cols:
            col_index = 0
            current_x = x_start
            current_y += row_height + margin
            row_height = 0
            if current_y + cell_height > 297 - margin:
                pdf.add_page()
                current_y = margin

        try:
            img = Image.open(img_path)
            aspect_ratio = img.size[1] / img.size[0]
            display_width = 40  # in mm
            display_height = display_width * aspect_ratio
            pdf.image(str(img_path), x=current_x, y=current_y, w=display_width)
        except Exception as e:
            pdf.set_xy(current_x, current_y)
            pdf.multi_cell(cell_width, 5, "[Image error]")
            display_height = 5

        text_y = current_y + display_height + 1
        pdf.set_xy(current_x, text_y)

        text_block_height = 0
        if alt_text:
            pdf.set_font("Arial", size=8, style="B")
            pdf.multi_cell(cell_width, 4, f"Alt: {alt_text}")
            text_block_height += 4 * (alt_text.count('\n') + 1)

        if note:
            pdf.set_font("Arial", size=8)
            pdf.multi_cell(cell_width, 4, f"Note: {note}")
            text_block_height += 4 * (note.count('\n') + 1)

        content_height = display_height + 1 + text_block_height + 1  # padding
        pdf.set_draw_color(200, 200, 200)
        pdf.rect(current_x, current_y, cell_width, content_height)

        row_height = max(row_height, content_height)

        current_x += cell_width + margin
        col_index += 1

    pdf.output(output_path)
    print(f"✅ PDF saved to: {output_path}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate Storyline Media PDF Report")
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

    print(f"🖼️ Found {len(entries)} matched media items. Generating PDF...")
    generate_pdf(entries, PDF_OUTPUT, args.story_file)

    shutil.rmtree(tmp_dir)
    print("🧹 Cleaned up temporary files.")

if __name__ == "__main__":
    main()
