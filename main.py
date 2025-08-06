import re
import urllib3
from bs4 import BeautifulSoup, Comment, Tag
import logging
from pathlib import Path
from datetime import datetime
import time
import requests

# Import scraper and database
from scraper.scrape_hist_20_25 import ModernEarthquakeScraper
from database.earthquake_database import EarthquakeDatabase


class DailyUpdateScraper:
    def __init__(
        self,
        base_url: str = "https://earthquake.phivolcs.dost.gov.ph/",
        request_delay: float = 1.0,
    ):
        self.base_url = base_url
        self.request_delay = request_delay
        self.logger = self._setup_logger()

        # Initialize sub-scrapers
        self.eq_database = EarthquakeDatabase()
        self.modern_scraper = ModernEarthquakeScraper()

        # Disable SSL warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _setup_logger(self):
        """
        Configure logging for the daily updater with timestamped file output.

        Returns:
            logging.Logger: Configured logger instance for main index operations
        """
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        logger = logging.getLogger("main_index")
        logger.setLevel(logging.DEBUG)

        # File Handler
        if not logger.handlers:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = logs_dir / f"main_index_{timestamp}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)

            file_format = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s"
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)

        return logger

    def fetch_page_with_retry(self, url: str):
        """
        Fetch a web page with exponential backoff retry mechanism.

        Implements robust HTTP client with proper headers and 3-retry strategy
        for handling network failures and PHIVOLCS server reliability issues.

        Args:
            url (str): The URL to fetch

        Returns:
            requests.Response: Successful HTTP response object, or None if all retries failed
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    verify=False,
                    headers=headers,
                    timeout=(15, 60),  # Increased timeouts for slow PHIVOLCS server
                )
                response.raise_for_status()
                self.logger.info(f"Successfully fetched: {url} (attempt {attempt + 1})")
                return response

            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as e:
                delay = base_delay * (2**attempt)
                self.logger.warning(
                    f"Connection failed for {url} (attempt {attempt + 1}/{max_retries}): {e}"
                )

                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"All retry attempts failed for {url}")
                    return None

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Failed to fetch {url}: {e}")
                return None

    def get_comment_node(self, soup, target_comment):
        """
        Find a specific HTML comment node in the parsed HTML.

        Args:
            soup (BeautifulSoup): Parsed HTML document
            target_comment (str): Text to search for within HTML comments

        Returns:
            Comment: HTML comment node containing the target text, or None if not found
        """
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            if target_comment in comment:
                return comment
        return None

    def get_links_with_regex_fallback(self, soup):
        """
        Extract earthquake links using regex pattern matching as fallback method.

        When the primary comment-based extraction fails, this method searches for
        earthquake URLs matching the current year pattern: YYYY_MMDD_HRMM_*.html

        Args:
            soup (BeautifulSoup): Parsed HTML document from main index page

        Returns:
            list: List of earthquake URLs (strings) matching current year pattern
        """
        # Pattern for current year earthquakes
        current_year = datetime.now().year
        pattern = f"{current_year}_\d{{4}}_\d{{4}}.*\.html"

        # BeautifulSoup regex
        a_tags = soup.find_all("a", href=re.compile(pattern))

        links = [a_tag.get("href") for a_tag in a_tags]
        return links

    def get_all_links_after_comment(self, soup, comment_text):
        """
        Extract earthquake links from main index using comment-based navigation (primary method).

        Finds the specified start comment, then traverses DOM elements collecting all
        <a> tag href attributes until reaching the "end of last event" comment.
        This is the primary method for extracting current earthquake event URLs.

        Args:
            soup (BeautifulSoup): Parsed HTML document from main index page
            comment_text (str): Starting comment to search for (e.g., "enter new event below")

        Returns:
            list: List of earthquake URLs (strings) found between start and end comments
        """
        comment_node = self.get_comment_node(soup, comment_text)
        if not comment_node:
            return []

        links = []
        current = comment_node

        while True:
            current = current.next_element
            if current is None:
                break
            if isinstance(current, Tag) and current.name == "a":
                href = current.get("href")
                if href:  # Make sure href exists
                    links.append(href)
            if isinstance(current, Comment) and "end of last event" in current:
                break

        return links

    def scrape_and_update_single_eq(self, url):
        """
        Process a single earthquake: scrape data and update database.

        Takes a relative earthquake URL, converts it to absolute URL, scrapes the
        earthquake data using ModernEarthquakeScraper, then performs database
        upsert operation (INSERT/UPDATE/SKIP) based on existing data.

        Args:
            url (str): Relative earthquake URL (e.g., "2025_Earthquake_Information\\August\\2025_0803_0147_B1.html")

        Returns:
            str: Database operation result message ("Successful inserting new earthquake",
                 "Successful updating earthquake", "Successful skipping earthquake", or error message)
        """
        # Convert to relative URL to full URL
        self.logger.info(f"Processing earthquake: {url}")
        link = url.replace("\\", "/")
        full_url = self.base_url + link

        # Call ModernEarthquakeScraper
        self.logger.info(f"Starting to scrape earthquake data from: {full_url}")
        scrape_eq = self.modern_scraper.scrape_single_event(full_url)
        if not scrape_eq:
            self.logger.error(f"Failed to scrape data from {full_url}")
            return "Failed: No data scraped"

        if not scrape_eq.get("eq_no") or not scrape_eq.get("datetime"):
            self.logger.error("Invalid earthquake data: missing critical fields")
            return "Failed: Invalid data"

        # Call Database to save/update the earthquake
        self.logger.info("Starting to database upsert operation")
        upsert = self.eq_database.process_live_update(scrape_eq)
        
        # Validate database operation result
        if upsert is None:
            return "Failed: Database operation returned None"

        # Return success or fail
        return upsert

    def process_daily_updates(self):
        """
        Main orchestration method - complete daily earthquake update pipeline.

        Executes the full daily update workflow:
        1. Fetch PHIVOLCS main index page with retry mechanism
        2. Extract earthquake links using primary method + fallback
        3. Process each earthquake through scraping and database upsert
        4. Provide progress reporting and final statistics

        Implements production-level error handling, rate limiting, and logging.
        Designed to process all available earthquake events (typically 1000+ per run).

        Returns:
            dict: Summary statistics with keys 'total', 'successful', 'failed', 'elapsed_time'
                  Returns None if critical failure (no main page or no links found)
        """
        start_time = time.time()
        self.logger.info("Starting daily earthquake updates")

        # Fetch main page
        response = self.fetch_page_with_retry(self.base_url)
        if not response:
            self.logger.error("Failed to fetch main page - aborting daily updates")
            return None

        soup = BeautifulSoup(response.content, "html.parser")

        # Extract earthquake links (primary + fallback)
        self.logger.info("Extracting earthquake links from main index")
        links = self.get_all_links_after_comment(soup, "enter new event below")

        if not links:
            self.logger.warning("Primary method failed, trying fallback")
            links = self.get_links_with_regex_fallback(soup)

        if not links:
            self.logger.error("No earthquake links found - aborting")
            return None

        self.logger.info(f"Found {len(links)} earthquake links to process")

        # Process all earthquakes
        successful = 0
        skipped = 0
        failed = 0

        for i, earthquake_url in enumerate(links, 1):
            self.logger.info(
                f"Processing earthquake {i}/{len(links)}: {earthquake_url}"
            )

            try:
                result = self.scrape_and_update_single_eq(earthquake_url)
                if result and "Successful" in result:
                    if "inserting" in result or "updating" in result:
                        successful += 1
                        self.logger.info(f"Earthquake {i} processed: {result}")
                    elif "skipping" in result:
                        skipped += 1
                        self.logger.debug(
                            f"Earthquake {i} skipped (no update needed): {result}"
                        )
                    else:
                        successful += 1
                        self.logger.info(f"Earthquake {i} processed: {result}")
                else:
                    failed += 1
                    self.logger.warning(f"Earthquake {i} failed: {result}")

            except Exception as e:
                failed += 1
                self.logger.error(f"Exception processing earthquake {i}: {e}")

            # Progress reporting every 50 earthquakes
            if i % 50 == 0:
                self.logger.info(
                    f"Progress: {i}/{len(links)} processed ({successful} successful, {skipped} skipped, {failed} failed)"
                )

            # Rate limiting
            time.sleep(self.request_delay)

        # Calculate elapsed time
        end_time = time.time()
        elapsed_time = end_time - start_time
        elapsed_minutes = elapsed_time / 60

        # Final summary
        self.logger.info(
            f"Daily updates completed: {successful} successful, {skipped} skipped, {failed} failed out of {len(links)} total"
        )
        self.logger.info(
            f"Total elapsed time: {elapsed_minutes:.2f} minutes ({elapsed_time:.2f} seconds)"
        )

        return {
            "total": len(links),
            "successful": successful,
            "skipped": skipped,
            "failed": failed,
            "elapsed_time": elapsed_time,
            "elapsed_minutes": elapsed_minutes,
        }


if __name__ == "__main__":
    # Initialize the scraper
    scraper = DailyUpdateScraper()

    # Run the full daily update pipelines
    results = scraper.process_daily_updates()

    # Display results
    if results:
        print("\n=== DAILY UPDATE COMPLETED ===")
        print(f"Total earthquakes processed: {results['total']}")
        print(f"Successful operations: {results['successful']}")
        print(f"Failed operations: {results['failed']}")
        print(f"Elapsed time: {results['elapsed_minutes']:.2f} minutes")
    else:
        print("Daily update failed - check logs for details")
