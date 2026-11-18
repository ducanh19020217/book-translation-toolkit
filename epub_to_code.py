#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPUB to Code (Stealth Reader Generator)
Chuyển đổi file EPUB thành mã nguồn (Python, TypeScript, React, Java, Markdown)
Được định dạng ngụy trang như code thật, có mục lục nhảy nhanh và không bị tràn ngang.
"""

import os
import sys
import re
import json
import zipfile
import textwrap
import argparse
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    from html.parser import HTMLParser
    HAS_BS4 = False


def extract_epub_chapters(epub_path):
    """Trích xuất danh sách các chương từ file EPUB theo đúng thứ tự spine"""
    with zipfile.ZipFile(epub_path, 'r') as z:
        # Tìm content.opf
        opf_path = None
        for name in z.namelist():
            if name.endswith('.opf'):
                opf_path = name
                break
        
        if not opf_path:
            raise ValueError("Không tìm thấy file OPF trong EPUB!")
        
        opf_xml = z.read(opf_path)
        root = ET.fromstring(opf_xml)
        ns = {'opf': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}
        
        # Lấy metadata
        title_elem = root.find('.//dc:title', ns)
        book_title = title_elem.text if title_elem is not None and title_elem.text else "EBOOK_STREAM"
        book_title = unicodedata.normalize('NFC', book_title)

        author_elem = root.find('.//dc:creator', ns)
        book_author = author_elem.text if author_elem is not None and author_elem.text else "Unknown"
        book_author = unicodedata.normalize('NFC', book_author)
        
        manifest = {item.get('id'): item.get('href') for item in root.findall('.//opf:item', ns)}
        spine = [itemref.get('idref') for itemref in root.findall('.//opf:itemref', ns)]
        
        # Thư mục chứa opf (để resolve relative path)
        opf_dir = os.path.dirname(opf_path)
        
        chapters = []
        for ref in spine:
            href = manifest.get(ref)
            if not href or href == 'titlepage.xhtml' or 'TableOfContents' in href or 'cover' in href.lower():
                continue
            
            full_href = os.path.normpath(os.path.join(opf_dir, href)) if opf_dir else href
            
            # Đọc nội dung HTML
            try:
                raw_bytes = z.read(full_href)
            except KeyError:
                matching = [n for n in z.namelist() if n.endswith(href.split('/')[-1])]
                if matching:
                    raw_bytes = z.read(matching[0])
                else:
                    continue
            
            html_text = raw_bytes.decode('utf-8', errors='ignore')
            
            # Parse HTML thành paragraphs
            title, paragraphs = parse_html_content(html_text, fallback_title=ref)
            if paragraphs:
                chapters.append({
                    'id': ref,
                    'title': title,
                    'paragraphs': paragraphs
                })
        
        return book_title, book_author, chapters


def parse_html_content(html_text, fallback_title="CHƯƠNG"):
    """Phân tích HTML lấy tiêu đề và danh sách đoạn văn"""
    title = fallback_title
    paragraphs = []
    
    if HAS_BS4:
        soup = BeautifulSoup(html_text, 'html.parser')
        body = soup.find('body')
        if not body:
            return title, paragraphs
        
        # Tìm tiêu đề
        for h in body.find_all(['h1', 'h2', 'h3', 'h4']):
            h_text = unicodedata.normalize('NFC', h.get_text().strip())
            if h_text and len(h_text) < 100:
                title = h_text
                break
        
        # Tìm đoạn văn
        for elem in body.find_all(['p', 'blockquote', 'li']):
            p_text = unicodedata.normalize('NFC', elem.get_text().strip())
            if p_text:
                paragraphs.append(p_text)
    else:
        # Fallback regex nếu chưa cài bs4
        clean = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html_text, flags=re.DOTALL)
        h_match = re.search(r'<h[1-4][^>]*>(.*?)</h[1-4]>', clean, flags=re.DOTALL | re.IGNORECASE)
        if h_match:
            title = re.sub(r'<[^>]+>', '', h_match.group(1)).strip()
            title = unicodedata.normalize('NFC', title)
        
        p_matches = re.findall(r'<p[^>]*>(.*?)</p>', clean, flags=re.DOTALL | re.IGNORECASE)
        for p in p_matches:
            text = re.sub(r'<[^>]+>', '', p).strip()
            text = unicodedata.normalize('NFC', text)
            if text:
                paragraphs.append(text)
    
    return title, paragraphs


def sanitize_ident(name, default="Chapter"):
    """Tạo tên class/hàm hợp lệ từ tiêu đề tiếng Việt"""
    s = name.replace('đ', 'd').replace('Đ', 'D')
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-zA-Z0-9]+', '_', s).strip('_')
    if not s or s[0].isdigit():
        s = f"{default}_{s}"
    return s[:40]


# ==============================================================================
# GENERATOR FOR PYTHON (.py)
# ==============================================================================
def generate_python(book_title, book_author, chapters, out_path):
    abs_path = os.path.abspath(out_path)
    
    def build_chapter(idx, ch):
        title = ch['title']
        cname = sanitize_ident(title, f"Chapter_{idx:02d}") + "_Worker"
        fname = "stream_" + sanitize_ident(title, f"chapter_{idx:02d}").lower()
        
        lines = [
            '# ' + '='*78,
            f'# {title}',
            '# ' + '='*78,
            f'class {cname}:',
            '    """',
            f'    [{title}]',
            '    Service Pipeline Worker | State: ACTIVE',
            '    """',
            '',
            f'    async def {fname}(self):'
        ]
        
        step = 1
        for p in ch['paragraphs']:
            if p.startswith('-'):
                lines.append(f'        # Event [{step:03d}] Dialogue Trigger')
            
            if len(p) <= 75:
                lines.append(f'        yield {json.dumps(p, ensure_ascii=False)}')
            else:
                wrapped = textwrap.wrap(p, width=72)
                lines.append('        yield (')
                for w in wrapped[:-1]:
                    lines.append(f'            {json.dumps(w + " ", ensure_ascii=False)}')
                lines.append(f'            {json.dumps(wrapped[-1], ensure_ascii=False)}')
                lines.append('        )')
            lines.append('')
            step += 1
            
        lines.append(f'        # [↑ Về mục lục]: file://{abs_path}#L25')
        lines.append('')
        lines.append('')
        return cname, lines

    bodies = [build_chapter(i+1, ch) for i, ch in enumerate(chapters)]

    def make_file(line_nums):
        header = [
            '# -*- coding: utf-8 -*-',
            '"""',
            'Module: core.runtime.data_stream_pipeline',
            'Project: High-Throughput Asynchronous Worker Engine',
            f'Dataset: {book_title} (Author: {book_author})',
            'Version: 3.12.4-lts | Production Environment',
            '',
            'Phím tắt hữu ích trong VSCode:',
            '  - Alt + Z: Bật/Tắt tự động xuống dòng (Word Wrap)',
            '  - Ctrl + Shift + O: Tìm nhanh và nhảy đến bất kỳ Chương nào',
            '  - Giữ Ctrl + Click chuột vào link bên dưới để nhảy thẳng đến chương',
            '"""',
            '',
            'import asyncio',
            'import logging',
            'from dataclasses import dataclass',
            '',
            '# ' + '='*78,
            '# 📑 MỤC LỤC NHANH (GIỮ PHÍM CTRL + CLICK VÀO ĐƯỜNG LINK ĐỂ NHẢY ĐẾN CHƯƠNG)',
            '# ' + '='*78,
            '#'
        ]
        for i, (ch, (cname, _)) in enumerate(zip(chapters, bodies)):
            ln = line_nums[i] if line_nums else 0
            header.append(f'# [{i+1:02d}] {ch["title"]:<30} -> file://{abs_path}#L{ln}')
        
        header.append('#')
        header.append('# ' + '='*78)
        header.append('')
        header.append('')
        
        curr = len(header) + 1
        starts = []
        out = list(header)
        for _, clines in bodies:
            starts.append(curr + 3)
            out.extend(clines)
            curr += len(clines)
        return starts, out

    s1, _ = make_file(None)
    s2, final_lines = make_file(s1)
    s3, final_lines = make_file(s2)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_lines))


# ==============================================================================
# GENERATOR FOR TYPESCRIPT / JAVASCRIPT (.ts / .js)
# ==============================================================================
def generate_typescript(book_title, book_author, chapters, out_path, is_ts=True):
    abs_path = os.path.abspath(out_path)
    ext = "ts" if is_ts else "js"
    
    def build_chapter(idx, ch):
        title = ch['title']
        cname = sanitize_ident(title, f"Chapter_{idx:02d}") + "Worker"
        fname = "stream" + sanitize_ident(title, f"Chapter{idx:02d}")
        
        type_ret = ": AsyncGenerator<string, void, unknown>" if is_ts else ""
        lines = [
            '// ' + '='*78,
            f'// {title}',
            '// ' + '='*78,
            f'export class {cname} {{',
            '  /**',
            f'   * [{title}]',
            '   * Enterprise Event Stream Handler',
            '   */',
            f'  public static async *{fname}(){type_ret} {{'
        ]
        
        step = 1
        for p in ch['paragraphs']:
            if p.startswith('-'):
                lines.append(f'    // Event [{step:03d}] Dialogue Trigger')
            
            if len(p) <= 75:
                lines.append(f'    yield {json.dumps(p, ensure_ascii=False)};')
            else:
                wrapped = textwrap.wrap(p, width=70)
                lines.append('    yield [')
                for w in wrapped:
                    lines.append(f'      {json.dumps(w, ensure_ascii=False)},')
                lines.append('    ].join(" ");')
            lines.append('')
            step += 1
            
        lines.append('  }')
        lines.append('}')
        lines.append(f'// [↑ Về mục lục]: file://{abs_path}#L20')
        lines.append('')
        lines.append('')
        return cname, lines

    bodies = [build_chapter(i+1, ch) for i, ch in enumerate(chapters)]

    def make_file(line_nums):
        header = [
            '/**',
            ' * @fileoverview Stream Data Processing Pipeline',
            f' * @dataset {book_title} by {book_author}',
            ' * @version 2.8.0-prod',
            ' *',
            ' * Phím tắt hữu ích trong VSCode:',
            ' *   - Alt + Z: Bật/Tắt tự động xuống dòng (Word Wrap)',
            ' *   - Ctrl + Shift + O: Tìm nhanh và nhảy đến bất kỳ Chương nào',
            ' *   - Giữ Ctrl + Click chuột vào link bên dưới để nhảy thẳng đến chương',
            ' */',
            '',
            '// ' + '='*78,
            '// 📑 MỤC LỤC NHANH (GIỮ PHÍM CTRL + CLICK VÀO ĐƯỜNG LINK ĐỂ NHẢY ĐẾN CHƯƠNG)',
            '// ' + '='*78,
            '//'
        ]
        for i, (ch, (cname, _)) in enumerate(zip(chapters, bodies)):
            ln = line_nums[i] if line_nums else 0
            header.append(f'// [{i+1:02d}] {ch["title"]:<30} -> file://{abs_path}#L{ln}')
        
        header.append('//')
        header.append('// ' + '='*78)
        header.append('')
        header.append('')
        
        curr = len(header) + 1
        starts = []
        out = list(header)
        for _, clines in bodies:
            starts.append(curr + 3)
            out.extend(clines)
            curr += len(clines)
        return starts, out

    s1, _ = make_file(None)
    s2, final_lines = make_file(s1)
    s3, final_lines = make_file(s2)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_lines))


# ==============================================================================
# GENERATOR FOR REACT (.tsx / .jsx)
# ==============================================================================
def generate_react(book_title, book_author, chapters, out_path, is_ts=True):
    abs_path = os.path.abspath(out_path)
    
    def build_chapter(idx, ch):
        title = ch['title']
        cname = sanitize_ident(title, f"Chapter_{idx:02d}") + "Viewer"
        
        fc_type = ": React.FC" if is_ts else ""
        lines = [
            '// ' + '='*78,
            f'// {title}',
            '// ' + '='*78,
            f'export const {cname}{fc_type} = () => {{',
            '  // Telemetry stream dataset fixture',
            '  const telemetryLogs = useMemo(() => [',
        ]
        
        for p in ch['paragraphs']:
            if len(p) <= 75:
                lines.append(f'    {json.dumps(p, ensure_ascii=False)},')
            else:
                wrapped = textwrap.wrap(p, width=70)
                lines.append('    [')
                for w in wrapped:
                    lines.append(f'      {json.dumps(w, ensure_ascii=False)},')
                lines.append('    ].join(" "),')
                
        lines.append('  ], []);')
        lines.append('')
        lines.append('  return (')
        lines.append('    <div className="telemetry-log-container hidden-display">')
        lines.append('      <span className="log-count">{telemetryLogs.length} records</span>')
        lines.append('    </div>')
        lines.append('  );')
        lines.append('};')
        lines.append(f'// [↑ Về mục lục]: file://{abs_path}#L20')
        lines.append('')
        lines.append('')
        return cname, lines

    bodies = [build_chapter(i+1, ch) for i, ch in enumerate(chapters)]

    def make_file(line_nums):
        header = [
            '/**',
            ' * @fileoverview React Telemetry Stream Component Views',
            f' * @module {book_title} (Mock Dataset)',
            ' *',
            ' * Phím tắt: Alt + Z (Wrap), Ctrl + Shift + O (Jump to Chapter)',
            ' */',
            '',
            'import React, { useMemo } from "react";',
            '',
            '// ' + '='*78,
            '// 📑 MỤC LỤC NHANH (GIỮ PHÍM CTRL + CLICK VÀO LINK ĐỂ NHẢY)',
            '// ' + '='*78,
            '//'
        ]
        for i, (ch, (cname, _)) in enumerate(zip(chapters, bodies)):
            ln = line_nums[i] if line_nums else 0
            header.append(f'// [{i+1:02d}] {ch["title"]:<30} -> file://{abs_path}#L{ln}')
        
        header.append('//')
        header.append('// ' + '='*78)
        header.append('')
        header.append('')
        
        curr = len(header) + 1
        starts = []
        out = list(header)
        for _, clines in bodies:
            starts.append(curr + 3)
            out.extend(clines)
            curr += len(clines)
        return starts, out

    s1, _ = make_file(None)
    s2, final_lines = make_file(s1)
    s3, final_lines = make_file(s2)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_lines))


# ==============================================================================
# GENERATOR FOR JAVA (.java)
# ==============================================================================
def generate_java(book_title, book_author, chapters, out_path):
    abs_path = os.path.abspath(out_path)
    class_main = Path(out_path).stem
    
    def build_chapter(idx, ch):
        title = ch['title']
        fname = "stream" + sanitize_ident(title, f"Chapter{idx:02d}")
        
        lines = [
            '    // ' + '='*74,
            f'    // {title}',
            '    // ' + '='*74,
            '    /**',
            f'     * [{title}]',
            '     * Stream generator for event logs',
            '     */',
            f'    public static Stream<String> {fname}() {{',
            '        return Stream.of('
        ]
        
        for p in ch['paragraphs']:
            if len(p) <= 70:
                lines.append(f'            {json.dumps(p, ensure_ascii=False)},')
            else:
                wrapped = textwrap.wrap(p, width=68)
                lines.append('            String.join(" ",')
                for w in wrapped:
                    lines.append(f'                {json.dumps(w, ensure_ascii=False)},')
                lines.append('            ),')
                
        lines.append('            "[END_OF_CHAPTER]"')
        lines.append('        );')
        lines.append('    }')
        lines.append(f'    // [↑ Về mục lục]: file://{abs_path}#L22')
        lines.append('')
        return fname, lines

    bodies = [build_chapter(i+1, ch) for i, ch in enumerate(chapters)]

    def make_file(line_nums):
        header = [
            'package com.enterprise.data.pipeline;',
            '',
            '/**',
            ' * Enterprise Event Stream Pipeline Service',
            f' * Dataset: {book_title} - {book_author}',
            ' *',
            ' * Phím tắt VSCode: Alt + Z (Wrap), Ctrl + Shift + O (Jump)',
            ' */',
            '',
            'import java.util.stream.Stream;',
            '',
            '// ' + '='*78,
            '// 📑 MỤC LỤC NHANH (GIỮ CTRL + CLICK VÀO LINK ĐỂ NHẢY ĐẾN CHƯƠNG)',
            '// ' + '='*78,
            '//'
        ]
        for i, (ch, (fname, _)) in enumerate(zip(chapters, bodies)):
            ln = line_nums[i] if line_nums else 0
            header.append(f'// [{i+1:02d}] {ch["title"]:<30} -> file://{abs_path}#L{ln}')
        
        header.append('//')
        header.append('// ' + '='*78)
        header.append('')
        header.append(f'public final class {class_main} {{')
        header.append('')
        
        curr = len(header) + 1
        starts = []
        out = list(header)
        for _, clines in bodies:
            starts.append(curr + 7)
            out.extend(clines)
            curr += len(clines)
        
        out.append('}')
        return starts, out

    s1, _ = make_file(None)
    s2, final_lines = make_file(s1)
    s3, final_lines = make_file(s2)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_lines))


# ==============================================================================
# GENERATOR FOR MARKDOWN (.md)
# ==============================================================================
def generate_markdown(book_title, book_author, chapters, out_path):
    lines = [
        f'# {book_title.upper()}\n',
        f'**Tác giả:** {book_author}\n',
        '---\n',
        '<a id="muc-luc" name="muc-luc"></a>\n',
        '## Mục lục\n'
    ]
    
    for i, ch in enumerate(chapters):
        slug = f'chapter-{i+1}'
        lines.append(f'* [{ch["title"]}](#{slug})')
    
    lines.append('\n---\n')
    
    for i, ch in enumerate(chapters):
        slug = f'chapter-{i+1}'
        lines.append(f'<a id="{slug}" name="{slug}"></a>\n')
        lines.append(f'## {ch["title"]}\n')
        
        for p in ch['paragraphs']:
            lines.append(f'{p}\n')
            
        lines.append('\n[↑ Về mục lục](#muc-luc)\n')
        lines.append('\n---\n')
        
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# ==============================================================================
# MAIN ENTRYPOINT & INTERACTIVE MENU
# ==============================================================================
def find_available_epubs():
    """Tự động quét các file .epub gần đây"""
    candidates = []
    search_dirs = [
        Path.cwd(),
        Path.home() / 'Downloads',
        Path.home() / 'Desktop',
        Path.home() / 'Desktop' / 'book'
    ]
    for d in search_dirs:
        if d.exists():
            for f in d.glob('*.epub'):
                if f not in candidates:
                    candidates.append(f)
    return candidates


def main():
    parser = argparse.ArgumentParser(description="Chuyển đổi file EPUB thành file Code ngụy trang để đọc trong VSCode")
    parser.add_argument('epub', nargs='?', help="Đường dẫn đến file .epub")
    parser.add_argument('-l', '--lang', choices=['python', 'ts', 'js', 'react', 'java', 'md'],
                        help="Ngôn ngữ đích: python, ts, js, react, java, md")
    parser.add_argument('-o', '--output', help="Đường dẫn file đầu ra")

    args = parser.parse_args()

    # 1. Chọn file EPUB
    epub_file = args.epub
    if not epub_file:
        print("\n🔍 Đang quét file EPUB trên máy...")
        found = find_available_epubs()
        if found:
            print("\nTìm thấy các file EPUB sau:")
            for i, p in enumerate(found[:6]):
                print(f"  [{i+1}] {p.name} ({p.parent})")
            print("  [0] Nhập đường dẫn khác")
            
            choice = input("\n👉 Chọn số (mặc định 1): ").strip()
            if choice == '0':
                epub_file = input("Nhập đường dẫn file .epub: ").strip()
            elif choice.isdigit() and 1 <= int(choice) <= len(found):
                epub_file = str(found[int(choice)-1])
            else:
                epub_file = str(found[0])
        else:
            epub_file = input("Nhập đường dẫn file .epub: ").strip()

    if not epub_file or not os.path.exists(epub_file):
        print(f"❌ Lỗi: Không tìm thấy file: {epub_file}")
        sys.exit(1)

    # 2. Chọn ngôn ngữ
    lang = args.lang
    if not lang:
        print("\n🛠️  Chọn kiểu ngôn ngữ ngụy trang:")
        print("  [1] Python       (.py)   - Async pipeline, yield stream (Khuyên dùng)")
        print("  [2] TypeScript   (.ts)   - AsyncGenerator class, enterprise types")
        print("  [3] JavaScript   (.js)   - AsyncGenerator class thuần")
        print("  [4] React TSX    (.tsx)  - Mock telemetry state fixture")
        print("  [5] Java         (.java) - Stream.of() service pipeline")
        print("  [6] Markdown     (.md)   - Tài liệu kỹ thuật, clickable TOC")
        
        ch_lang = input("\n👉 Nhập lựa chọn [1-6] (mặc định 1): ").strip()
        lang_map = {
            '1': 'python',
            '2': 'ts',
            '3': 'js',
            '4': 'react',
            '5': 'java',
            '6': 'md'
        }
        lang = lang_map.get(ch_lang, 'python')

    # Trích xuất EPUB
    print(f"\n📖 Đang đọc nội dung EPUB: {epub_file}...")
    book_title, book_author, chapters = extract_epub_chapters(epub_file)
    print(f"✅ Sách: {book_title} | Tác giả: {book_author} | Số chương: {len(chapters)}")

    # 3. Đặt tên file đầu ra
    base_name = sanitize_ident(book_title, "ebook_stream").lower()
    ext_map = {
        'python': '.py',
        'ts': '.ts',
        'js': '.js',
        'react': '.tsx',
        'java': '.java',
        'md': '.md'
    }
    ext = ext_map[lang]
    
    if args.output:
        out_path = args.output
    else:
        out_path = os.path.join(os.getcwd(), f"{base_name}{ext}")

    print(f"⚙️  Đang chuyển đổi sang định dạng [{lang.upper()}]...")
    
    if lang == 'python':
        generate_python(book_title, book_author, chapters, out_path)
    elif lang == 'ts':
        generate_typescript(book_title, book_author, chapters, out_path, is_ts=True)
    elif lang == 'js':
        generate_typescript(book_title, book_author, chapters, out_path, is_ts=False)
    elif lang == 'react':
        generate_react(book_title, book_author, chapters, out_path, is_ts=True)
    elif lang == 'java':
        generate_java(book_title, book_author, chapters, out_path)
    elif lang == 'md':
        generate_markdown(book_title, book_author, chapters, out_path)

    print(f"\n🎉 HOÀN TẤT! File ngụy trang đã sẵn sàng tại:")
    print(f"👉 {out_path}\n")
    print("Mẹo đọc trong VSCode:")
    print("  - Giữ Ctrl + Click vào mục lục ở đầu file để nhảy ngay đến chương")
    print("  - Nhấn Ctrl + Shift + O để tìm nhanh chương")
    print("  - Nhấn Alt + Z nếu muốn bật/tắt wrap dòng mềm")


if __name__ == '__main__':
    main()
