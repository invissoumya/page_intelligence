import json
import argparse
import re
from bs4 import BeautifulSoup

KEYWORD_MAP = {
    'hero': r'hero',
    'content': r'content',
    'video': r'video',
    'testimonial': r'(testimonial|review|quote)',
    'cta': r'cta|call[-_]to[-_]action',
    'footer': r'footer',
}


def find_by_keyword(soup, keyword_regex):
    """Return all tags that have a class or id matching the regex."""
    pattern = re.compile(keyword_regex, re.I)
    results = []
    for attr in ('class', 'id'):
        # find_all returns a list; for class look for any matching in list
        if attr == 'class':
            for tag in soup.find_all(True, {attr: True}):
                classes = tag.get('class') or []
                for c in classes:
                    if pattern.search(c):
                        results.append(tag)
                        break
        else:
            results.extend(soup.find_all(True, {attr: pattern}))
    return results


def classify_html(html: str) -> dict:
    """Analyze HTML and return a mapping of section names to list of HTML snippets."""
    soup = BeautifulSoup(html, 'html.parser')
    sections = {}

    # optional fallback selectors
    if html.strip() == '':
        return sections

    # hero
    sections['hero'] = [str(tag) for tag in find_by_keyword(soup, KEYWORD_MAP['hero'])]

    # content: anything labelled content or main/article
    content_tags = find_by_keyword(soup, KEYWORD_MAP['content'])
    if not content_tags:
        content_tags = soup.find_all(['main', 'article', 'section'])
    sections['content'] = [str(tag) for tag in content_tags]

    # video: <video>, iframes with video src, or keyword
    videos = soup.find_all('video')
    for iframe in soup.find_all('iframe'):
        src = iframe.get('src', '')
        if 'youtube' in src or 'vimeo' in src or 'video' in src:
            videos.append(iframe)
    # also by keyword classes
    videos += find_by_keyword(soup, KEYWORD_MAP['video'])
    # deduplicate
    seen = set()
    unique_videos = []
    for tag in videos:
        key = str(tag)
        if key not in seen:
            seen.add(key)
            unique_videos.append(tag)
    sections['video'] = [str(tag) for tag in unique_videos]

    # testimonial
    sections['testimonial'] = [str(tag) for tag in find_by_keyword(soup, KEYWORD_MAP['testimonial'])]

    # cta: look for buttons or keyword
    cta_tags = find_by_keyword(soup, KEYWORD_MAP['cta'])
    cta_tags += soup.find_all('button')
    sections['cta'] = [str(tag) for tag in dict.fromkeys(str(t) for t in cta_tags)]

    # footer
    footers = soup.find_all('footer')
    footers += find_by_keyword(soup, KEYWORD_MAP['footer'])
    sections['footer'] = [str(tag) for tag in dict.fromkeys(str(t) for t in footers)]

    return sections


def main():
    parser = argparse.ArgumentParser(description='Extract logical sections from crawled pages')
    parser.add_argument('input', help='Path to JSON file produced by crawler')
    parser.add_argument('-o', '--output', help='Optional output JSON file; defaults to stdout')
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = {}
    for page in data:
        url = page.get('page_url')
        html = page.get('page_html', '')
        sections = classify_html(html)
        results[url] = sections

    out_json = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as out_f:
            out_f.write(out_json)
    else:
        print(out_json)


if __name__ == '__main__':
    main()
