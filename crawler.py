import requests
from bs4 import BeautifulSoup

from urllib.parse import urljoin, urlparse
import json
import logging

# suppress insecure HTTPS warnings when verify=False
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')


class SiteCrawler:
    def __init__(self, root_url: str):
        self.root_url = root_url.rstrip('/')
        self.root_domain = urlparse(self.root_url).netloc
        self.visited = set()
        self.results = []

    def is_internal(self, link: str) -> bool:
        parsed = urlparse(link)
        # treat relative URLs as internal
        if not parsed.netloc:
            return True
        return parsed.netloc == self.root_domain

    def normalize(self, link: str) -> str:
        # join with root to handle relative links
        return urljoin(self.root_url, link.split('#')[0].rstrip('/'))

    def crawl_page(self, url: str):
        if url in self.visited:
            return
        self.visited.add(url)

        logging.info(f"Fetching {url}")
        try:
            # disable certificate verification in case of self-signed or missing CA
            resp = requests.get(url, timeout=10, verify=False)
            resp.raise_for_status()
        except requests.RequestException as e:
            logging.warning(f"Failed to fetch {url}: {e}")
            return

        soup = BeautifulSoup(resp.text, 'html.parser')

        title = soup.title.string.strip() if soup.title and soup.title.string else ''
        meta_desc = ''
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag and desc_tag.get('content'):
            meta_desc = desc_tag['content'].strip()
        h1 = ''
        h1_tag = soup.find('h1')
        if h1_tag:
            h1 = h1_tag.get_text(strip=True)

        # retain element structure but remove text content to reduce size
        # parse again to strip text nodes
        # tmp_soup = BeautifulSoup(resp.text, 'html.parser')
        # for text_node in tmp_soup.find_all(text=True):
        #     # skip script/style content if needed; remove all text otherwise
        #     text_node.replace_with('')
        # page_html = str(tmp_soup)
        
        page_html = resp.text

        internal_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            normalized = self.normalize(href)
            if self.is_internal(normalized):
                internal_links.append(normalized)

        # remove duplicates
        internal_links = list(set(internal_links))

        self.results.append({
            'page_url': url,
            'title': title,
            'meta_description': meta_desc,
            'h1': h1,
            'page_html': page_html,
            'internal_links': internal_links,
        })

        # crawl links
        for link in internal_links:
            if link not in self.visited:
                self.crawl_page(link)

    def crawl(self):
        self.crawl_page(self.root_url)

    def save(self, path='site_pages.json', compress: bool = False):
        """Write results to JSON file. If `compress` is True or path ends with .gz,
        the output will be written in gzip format to reduce size.
        """
        if compress or path.endswith('.gz'):
            import gzip
            mode = 'wt'
            opener = gzip.open
            if not path.endswith('.gz'):
                path += '.gz'
        else:
            opener = open
            mode = 'w'
        with opener(path, mode, encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        return path


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Simple internal site crawler')
    parser.add_argument('root', help='Root URL to start crawling from')
    parser.add_argument('--output', '-o', default='site_pages.json', help='Output JSON filename')
    parser.add_argument('--compress', '-z', action='store_true', help='Compress output using gzip')
    args = parser.parse_args()

    crawler = SiteCrawler(args.root)
    crawler.crawl()
    out_path = crawler.save(args.output, compress=args.compress)
    logging.info(f"Crawling completed. Results saved to {out_path}")
