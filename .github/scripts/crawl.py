import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor
import logging
import time

# Setup logging
logging.basicConfig(filename='crawling.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

visited_urls = set()
checked_correct_urls = set()
broken_links = []

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://mi.docs.wso2.com/en/latest/',
    'Accept-Language': 'en-US,en;q=0.9'
}

VALID_DOMAINS = [
    "https://mi.docs.wso2.com/en/latest",
    "https://mi.docs.wso2.com/en/4.3.0"
]

def remove_fragment(url):
    parsed_url = urlparse(url)
    url_without_fragment = urlunparse(parsed_url._replace(fragment=''))
    return url_without_fragment

def join_url(base, link):
    parsed_url = urlparse(base)
    if not parsed_url.path.endswith('/') and not parsed_url.path.split('/')[-1].count('.'):
        base = urlunparse(parsed_url._replace(path=parsed_url.path + '/'))
    return urljoin(base, link)

def is_file_path(url):
    parsed_url = urlparse(url)
    return bool(parsed_url.path.split('/')[-1].count('.'))

def is_same_domain(url1, url2):
    return urlparse(url1).netloc == urlparse(url2).netloc

def is_valid_domain(url):
    return any(url.startswith(domain) for domain in VALID_DOMAINS)

def check_url(url, target_redirect, parent_url=None):
    if url in checked_correct_urls:
        return

    logging.info(f"Checking: {url}")

    try:
        link_response = requests.get(url, headers=headers, allow_redirects=True)
        if link_response.status_code in (301, 302) and link_response.headers.get('Location') == target_redirect:
            visited_urls.add(url)
            logging.error(f"{url} redirects to {link_response.headers.get('Location')} and is found on {parent_url}")
            broken_links.append([url, link_response.headers.get('Location'), parent_url, '301/302 redirect to target URL'])
            return False  # Error found
        elif link_response.url == target_redirect:
            visited_urls.add(url)
            logging.error(f"{url} redirects to {link_response.url} and is found on {parent_url}")
            broken_links.append([url, link_response.url, parent_url, 'Redirect to target URL'])
            return False  # Error found
        elif link_response.status_code == 404:
            visited_urls.add(url)
            logging.error(f"{url} returns 404 error and is found on {parent_url}")
            broken_links.append([url, None, parent_url, '404 Not Found'])
            return False  # Error found
    except requests.RequestException as e:
        logging.error(f"Failed to fetch {url} and is found in {parent_url}: {e}")
        broken_links.append([url, None, parent_url, f"Failed to fetch {url}: {e}"])
        return False  # Error found

    checked_correct_urls.add(url)
    return True  # No error found

def find_redirects(url, target_redirect, base_url, max_depth=300, depth=0):
    if depth > max_depth or url in visited_urls:
        return
    
    visited_urls.add(url)
    
    if is_file_path(url):
        logging.info(f"Skipped Crawling: {url} is a file path")
        return

    logging.info(f"Crawling: {url}")
    print(f"Crawling: {url}")

    try:
        response = requests.get(url, headers=headers)
    except requests.RequestException as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return

    # Add a delay to avoid triggering rate limits
    time.sleep(1)

    soup = BeautifulSoup(response.text, 'html.parser')

    nav_elements = soup.find_all('nav', {'aria-label': 'Navigation'})
    exclude_links = []
    for nav in nav_elements:
        ul = nav.find('ul', recursive=False)
        if ul:
            for li in ul.find_all('li', recursive=False):
                if 'md-nav__item--active' not in li.get('class', []):
                    exclude_links.extend(li.find_all('a', href=True))

    for link in soup.find_all('a', href=True):
        if link in exclude_links:
            continue

        full_url = join_url(url, link['href'])
        full_url = remove_fragment(full_url)

        logging.info(f"Found link: {full_url}")

        if is_same_domain(full_url, base_url):
            if not is_valid_domain(full_url):
                logging.info(f"{full_url} is a version mismatch and is found on {url} and href is {link['href']}")
                broken_links.append([full_url, None, url, 'Version mismatch'])
            else:
                if check_url(full_url, target_redirect, parent_url=url):
                    find_redirects(full_url, target_redirect, base_url, max_depth, depth+1)
        else:
            check_url(full_url, target_redirect, parent_url=url)

def crawl_website(base_url, target_redirect):
    find_redirects(base_url, target_redirect, base_url)

if __name__ == "__main__":
    base_url = "https://mi.docs.wso2.com/en/latest/"
    target_redirect = "https://mi.docs.wso2.com/en/latest/page-not-found/"
    
    crawl_website(base_url, target_redirect)
    
    if broken_links:
        print("\nBroken Links Report:")
        for link in broken_links:
            print(f"Source URL: {link[0]}, Redirected URL: {link[1]}, Containing Page: {link[2]}, Description: {link[3]}")
        raise Exception("Broken links were found. See report above.")
    else:
        print("No broken links found.")
    
    logging.info("Crawling completed!!!")
