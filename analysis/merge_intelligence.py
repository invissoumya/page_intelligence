import os
import json
import argparse
import csv
import re
from typing import Optional

import pandas as pd


PRIORITY_ORDER = ['hero', 'offer', 'testimonial', 'content', 'video', 'cta', 'faq']


def extract_category(resp) -> Optional[str]:
    """Try to pull a 'category' value out of Claude response dict."""
    if not isinstance(resp, dict):
        return None
    # search string values for a JSON blob with category
    for v in resp.values():
        if isinstance(v, str):
            # try to load JSON from inside
            try:
                j = json.loads(v)
                if isinstance(j, dict) and 'category' in j:
                    return j['category']
            except Exception:
                pass
    # also look at known keys
    for key in ('completion', 'output', 'text', 'response'):
        if key in resp:
            val = resp[key]
            if isinstance(val, str):
                try:
                    j = json.loads(val)
                    if isinstance(j, dict) and 'category' in j:
                        return j['category']
                except Exception:
                    # maybe plain text like 'category: hero'
                    m = re.search(r"category\s*[:=]\s*(\w+)", val, re.I)
                    if m:
                        return m.group(1).lower()
    return None


def load_metrics(path: str) -> pd.DataFrame:
    # use pandas to read ignoring comment lines
    df = pd.read_csv(path, comment='#')
    # normalise column names
    df = df.rename(columns={
        'Page path and screen class': 'page_url',
        'Views': 'traffic',
        'Bounce rate': 'bounce_rate'
    })
    return df


def main():
    parser = argparse.ArgumentParser(description='Merge crawl, classification and metrics into a CSV intelligence report')
    parser.add_argument('pages', help='Path to site_pages.json (unused here but kept for interface)')
    parser.add_argument('classification', help='Path to classification JSON produced earlier')
    parser.add_argument('metrics', help='Path to CSV with page metrics')
    parser.add_argument('-o', '--output', default='analysis/site_intelligence.csv', help='Output CSV file')
    args = parser.parse_args()

    with open(args.classification, 'r', encoding='utf-8') as f:
        classification = json.load(f)

    metrics_df = load_metrics(args.metrics)
    # ensure page_url column is str and fill NaN with empty
    metrics_df['page_url'] = metrics_df['page_url'].astype(str).fillna('')

    rows = []
    for _, mrow in metrics_df.iterrows():
        url = str(mrow.get('page_url') or '')
        traffic = mrow.get('traffic')
        bounce = mrow.get('bounce_rate')

        # find matching classification entry
        class_info = classification.get(url)
        if class_info is None and url:
            # try to match by suffix
            for k in classification.keys():
                if isinstance(k, str) and (k.endswith(url) or url in k):
                    class_info = classification[k]
                    break

        section_types = []
        cta_presence = False
        detected_categories = []
        if class_info:
            for section, info in class_info.items():
                summary = info.get('summary', '').strip()
                if summary:
                    section_types.append(section)
                    if section == 'cta':
                        cta_presence = True
                cat = extract_category(info.get('claude_response', {}))
                if cat:
                    detected_categories.append(cat.lower())
        # decide page_type by priority from detected_categories
        page_type = None
        for p in PRIORITY_ORDER:
            if p in detected_categories:
                page_type = p
                break
        if page_type is None and detected_categories:
            page_type = detected_categories[0]
        # fallback to maybe first section type
        if page_type is None and section_types:
            page_type = section_types[0]

        rows.append({
            'page_url': url,
            'page_type': page_type or '',
            'traffic': traffic,
            'bounce_rate': bounce,
            'section_types': ';'.join(section_types),
            'cta_presence': cta_presence,
        })

    # ensure output directory exists
    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with open(args.output, 'w', newline='', encoding='utf-8') as out_f:
        writer = csv.DictWriter(out_f, fieldnames=['page_url', 'page_type', 'traffic', 'bounce_rate', 'section_types', 'cta_presence'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Merged intelligence written to {args.output}")


if __name__ == '__main__':
    main()
