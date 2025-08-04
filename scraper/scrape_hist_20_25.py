"""
Modern Earthquake Data Scraper for PHIVOLCS (2022+)

This module scrapes earthquake data from the modern PHIVOLCS website format (2022 onwards).
The modern format has proper HTML comment blocks for all data fields, making extraction more reliable.
"""

import re
import urllib3
import requests
from bs4 import BeautifulSoup, Tag, Comment
import logging
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class ModernEarthquakeScraper:
    """Scraper for modern PHIVOLCS earthquake pages (2022+)."""

    def __init__(
        self,
        base_url: str = "https://earthquake.phivolcs.dost.gov.ph/",
        request_delay: float = 0.5,
    ):
        self.base_url = base_url
        self.request_delay = request_delay
        self.logger = self._setup_logger()

        # Disable SSL warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _setup_logger(self):
        """Configure logging for the scraper"""
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        logger = logging.getLogger("earthquake_scraper_20_25")
        logger.setLevel(logging.DEBUG)

        # File Handler
        if not logger.handlers:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = logs_dir / f"earthquake_scraper_20_25_{timestamp}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)

            file_format = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s"
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)

        return logger

    def fetch_page(self, url):
        """Fetch and parse a web page with retry mechanism."""
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
                    timeout=(15, 60),  # Increased for slow PHIVOLCS server
                )
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                self.logger.info(
                    f"Successfully fetched: {url} (Status: {response.status_code}, Attempt: {attempt + 1})"
                )
                return soup

            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as e:
                delay = base_delay * (2**attempt)  # Exponential backoff
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

    def extract_comment_block(self, soup, comment_text):
        """Extract HTML block after a specific comment."""
        self.logger.debug(f"Searching for comment block: '{comment_text}'")

        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            if comment_text in comment:
                # Get the parent (element that contains (comes before/wraps around))
                parent = comment.parent
                self.logger.debug(f"Found comment block: '{comment_text}'")
                return parent

        self.logger.warning(f"Comment block '{comment_text}' not found")
        return None

    # Function for fallback incase there's no comment in the html structure
    def extract_label_block(self, soup, regex_pattern):
        """Extract HTML metadata if no comment block"""
        self.logger.debug(f"Searching for pattern: '{regex_pattern}'")

        for td in soup.find_all("td"):
            # Replace the \xa0 with white space to strip
            table_list = td.get_text(strip=True).replace("\xa0", " ")
            # Check the regex pattern if match in the table list
            if re.search(regex_pattern, table_list):
                self.logger.debug(f"Found match in '{table_list}'")
                next_td = td.find_next_sibling("td")
                self.logger.debug(f"Next table: '{next_td}'")
                # IF true -> Double Table
                if next_td:
                    return next_td.get_text(strip=True)
                    # extracted_data_double_cell = next_td.get_text(strip=True)
                    # return extracted_data_double_cell
                # # Single cell
                # else:
                # extracted_data_single_cell = td.get_text(strip=True)
                # return extracted_data_single_cell
        return None

    def parse_datetime(self, date_str, time_str):
        """Convert date and time strings to datetime object."""
        try:
            datetime_str = f"{date_str.strip()} {time_str.strip()}"

            # Define format patterns to try
            formats = [
                "%d %b %Y %I:%M:%S %p",  # 28 Jul 2022 04:02:42 AM
                "%d %b %Y %I:%M %p",  # 28 Jul 2022 04:02 AM
                "%d %B %Y %I:%M:%S %p",  # 28 July 2022 04:02:42 AM
                "%d %B %Y %I:%M %p",  # 28 July 2022 04:02 AM
                "%d %b %Y %H:%M:%S",  # 28 Jul 2022 16:02:42
                "%d %b %Y %H:%M",  # 28 Jul 2022 16:02
                "%d %B %Y %H:%M:%S",  # 28 July 2022 16:02:42
                "%d %B %Y %H:%M",  # 28 July 2022 16:02
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue

            self.logger.error(f"Failed to parse datetime: '{datetime_str}'")
            return None

        except Exception as e:
            self.logger.error(f"Error parsing datetime '{datetime_str}': {e}")
            return None

    def parse_coordinate(self, coord_str):
        """Convert coordinate string (e.g., '17.52°N') to float."""
        try:
            match = re.search(r"(\d+\.\d+)", coord_str)
            if not match:
                self.logger.warning(f"Invalid coordinate format: {coord_str}")
                return None

            value = float(match.group(1))

            # Adjust for direction (negative for South/West)
            if "S" in coord_str or "W" in coord_str:
                value = -value

            return value
        except ValueError as e:
            self.logger.error(f"Failed to parse coordinate '{coord_str}': {e}")
            return None

    def parse_magnitude(self, magnitude_str):
        """Extract magnitude type and value from string (e.g., 'Ms 5.0')."""
        try:
            match = re.search(r"([A-Za-z]+)\s+(\d+\.\d+)", magnitude_str)
            if match:
                mag_type = match.group(1)
                mag_value = float(match.group(2))
                return mag_type, mag_value
            else:
                self.logger.warning(f"Invalid magnitude format: {magnitude_str}")
                return None, None
        except ValueError as e:
            self.logger.error(f"Failed to parse magnitude '{magnitude_str}': {e}")
            return None, None

    def extract_earthquake_details(self, soup):
        """Extract detailed earthquake information from a modern format page."""
        earthquake_info = {}

        # Extract EQ Number
        try:
            eq_text = None

            # Try the primary method
            eq_block = self.extract_comment_block(soup, "EQInfo-Data")
            if eq_block:
                eq_text = eq_block.get_text(strip=True)
            else:
                # Fall back mechanism
                eq_text = self.extract_label_block(
                    soup, r"EARTHQUAKE\sINFORMATION\sNO\.\s:"
                )

            # Extract the number from the text
            if eq_text:
                match = re.search(r"NO\.\s*:\s*(\d+)", eq_text)
                if match:
                    earthquake_info["eq_no"] = int(match.group(1))
                    self.logger.debug(
                        f"Extracted EQ number: {earthquake_info['eq_no']}"
                    )
                else:
                    earthquake_info["eq_no"] = None
            else:
                earthquake_info["eq_no"] = None
        except (AttributeError, ValueError) as e:
            self.logger.error(f"Error extracting EQ number: {e}")
            earthquake_info["eq_no"] = None

        # Extract Date and Time
        try:
            datetime_text = None

            # Try primary method
            datetime_block = self.extract_comment_block(soup, "DateTime-Data")
            if datetime_block:
                datetime_text = datetime_block.get_text(strip=True)
            else:
                # Fallback mechanism
                datetime_text = self.extract_label_block(soup, r"Date/Time")

            # Single parsing logic
            if datetime_text and "-" in datetime_text:
                date_part, time_part = datetime_text.split("-", 1)
                earthquake_info["date_str"] = date_part.strip()
                earthquake_info["time_str"] = time_part.strip()
                earthquake_info["datetime"] = self.parse_datetime(
                    date_part.strip(), time_part.strip()
                )
                self.logger.debug(f"Extracted datetime: {earthquake_info['datetime']}")
            else:
                earthquake_info["date_str"] = ""
                earthquake_info["time_str"] = ""
                earthquake_info["datetime"] = None
        except Exception as e:
            self.logger.error(f"Error extracting date/time: {e}")
            earthquake_info["date_str"] = ""
            earthquake_info["time_str"] = ""
            earthquake_info["datetime"] = None

        # Extract Location
        try:
            location_text = None

            # Primary Method
            location_block = self.extract_comment_block(soup, "Location-Data")
            if location_block:
                location_text = location_block.get_text(strip=True)
            else:
                location_text = self.extract_label_block(soup, r"Location")

            # Find all latitude/longitude values like "12.34 N"
            if location_text:
                lat_lon = re.findall(r"\d+\.\d+°[A-Z]", location_text)

                if len(lat_lon) >= 2:
                    lat_str, lon_str = lat_lon[0], lat_lon[1]
                    earthquake_info["latitude_str"] = lat_str
                    earthquake_info["longitude_str"] = lon_str
                    earthquake_info["latitude"] = self.parse_coordinate(lat_str)
                    earthquake_info["longitude"] = self.parse_coordinate(lon_str)
                    self.logger.debug(
                        f"Extracted coordinates: {earthquake_info['latitude']}, {earthquake_info['longitude']}"
                    )
                else:
                    earthquake_info["latitude_str"] = ""
                    earthquake_info["longitude_str"] = ""
                    earthquake_info["latitude"] = None
                    earthquake_info["longitude"] = None

                # Extract region
                region_match = re.findall(r"(\d{3}\s+.*)", location_text)
                full_region = region_match[0].strip() if region_match else ""
                earthquake_info["region"] = full_region

                # Extract location/municipality/province from region
                location_info = self.parse_region_location(full_region)
                earthquake_info["location"] = location_info["location"]
                earthquake_info["municipality"] = location_info["municipality"]
                earthquake_info["province"] = location_info["province"]

                self.logger.debug(f"Extracted region: {earthquake_info['region']}")
                self.logger.debug(f"Extracted location: {earthquake_info['location']}")
                self.logger.debug(
                    f"Extracted municipality: {earthquake_info['municipality']}"
                )
                self.logger.debug(f"Extracted province: {earthquake_info['province']}")
            else:
                earthquake_info.update(
                    {
                        "latitude_str": "",
                        "longitude_str": "",
                        "latitude": None,
                        "longitude": None,
                        "region": "",
                        "location": "",
                        "municipality": "",
                        "province": "",
                    }
                )
        except Exception as e:
            self.logger.error(f"Error extracting location: {e}")
            earthquake_info.update(
                {
                    "latitude_str": "",
                    "longitude_str": "",
                    "latitude": None,
                    "longitude": None,
                    "region": "",
                    "location": "",
                    "municipality": "",
                    "province": "",
                }
            )

        # Extract Depth
        try:
            depth_text = None

            # Primary method
            depth_block = self.extract_comment_block(soup, "Depth-Data")
            if depth_block:
                depth_text = depth_block.get_text(strip=True)
            else:
                depth_text = self.extract_label_block(soup, r"^Depth\s+of\s+Focus")

            # Error handling
            if depth_text:
                print(depth_text)
                earthquake_info["depth_str"] = depth_text
                depth_match = re.search(r"(\d+)", depth_text)
                earthquake_info["depth_km"] = (
                    int(depth_match.group(1)) if depth_match else None
                )
                self.logger.debug(f"Extracted depth: {earthquake_info['depth_km']} km")
            else:
                earthquake_info["depth_str"] = ""
                earthquake_info["depth_km"] = None
        except Exception as e:
            self.logger.error(f"Error extracting depth: {e}")
            earthquake_info["depth_str"] = ""
            earthquake_info["depth_km"] = None

        # Extract Origin
        try:
            origin_text = None

            # Primary method
            origin_block = self.extract_comment_block(soup, "Origin-Data")

            if origin_block:
                origin_text = origin_block.get_text(strip=True)
            else:
                origin_text = self.extract_label_block(soup, r"Origin")

            if origin_text:
                earthquake_info["origin"] = origin_text
                self.logger.debug(f"Extracted origin: {earthquake_info['origin']}")
            else:
                earthquake_info["origin"] = ""
        except Exception as e:
            self.logger.error(f"Error extracting origin: {e}")
            earthquake_info["origin"] = ""

        # Extract Magnitude
        try:
            magnitude_text = None

            # Primary method
            magnitude_block = self.extract_comment_block(soup, "Magnitude-Data")
            if magnitude_block:
                magnitude_text = magnitude_block.get_text(strip=True)
            else:
                magnitude_text = self.extract_label_block(soup, r"Magnitude")

            if magnitude_text:
                earthquake_info["magnitude_str"] = magnitude_text
                mag_type, mag_value = self.parse_magnitude(magnitude_text)
                earthquake_info["magnitude_type"] = mag_type
                earthquake_info["magnitude_value"] = mag_value
                self.logger.debug(f"Extracted magnitude: {mag_type} {mag_value}")
            else:
                earthquake_info["magnitude_str"] = ""
                earthquake_info["magnitude_type"] = None
                earthquake_info["magnitude_value"] = None
        except Exception as e:
            self.logger.error(f"Error extracting magnitude: {e}")
            earthquake_info["magnitude_str"] = ""
            earthquake_info["magnitude_type"] = None
            earthquake_info["magnitude_value"] = None

        # Extract Map Image
        try:
            map_block = self.extract_comment_block(soup, "Map-Data")
            if map_block:
                img_tag = map_block.find("img")
                if img_tag and img_tag.get("src"):
                    src = img_tag.get("src").strip()
                    earthquake_info["filename"] = (
                        src[:-4] if src.endswith((".png", ".jpg", ".gif")) else src
                    )
                    self.logger.debug(
                        f"Extracted map filename: {earthquake_info['filename']}"
                    )
                else:
                    earthquake_info["filename"] = ""
            else:
                earthquake_info["filename"] = ""
        except Exception as e:
            self.logger.error(f"Error extracting map filename: {e}")
            earthquake_info["filename"] = ""

        # Extract Intensities
        try:
            intensity_text = None

            # Primary Method
            intensity_block = self.extract_comment_block(soup, "Intensity-Data")

            if intensity_block:
                intensity_html = intensity_block.decode_contents().replace(
                    "<br/>", "\n"
                )
                intensity_text = BeautifulSoup(intensity_html, "html.parser").get_text(
                    separator="\n"
                )
            else:
                intensity_text = self.extract_label_block(
                    soup, r"Reported\s+Intensities"
                )
            if intensity_text:
                # Fix spacing around Intensity but preserve instrumental markers
                intensity_text = re.sub(
                    r"(?<!Instrumental\s)\bIntensity", " Intensity", intensity_text
                )

                reported_intensities = []
                instrumental_intensities = []

                # Split by instrumental intensity marker (handle both singular and plural)
                if "Instrumental Intensities:" in intensity_text:
                    reported_part, instrumental_part = intensity_text.split(
                        "Instrumental Intensities:", 1
                    )
                elif "Instrumental Intensity:" in intensity_text:
                    reported_part, instrumental_part = intensity_text.split(
                        "Instrumental Intensity:", 1
                    )
                else:
                    reported_part = intensity_text
                    instrumental_part = ""

                # Enhanced pattern that stops at certain keywords
                pattern = r"Intensity\s+([IVXLCDM]+)\s*[-:]?\s*(.+?)(?=\n|Intensity|Instrumental|This is|Expecting|$)"

                # Extract reported intensities
                for intensity, location in re.findall(pattern, reported_part):
                    location_clean = location.strip()
                    location_clean = re.sub(
                        r"\s*(Instrumental.*|This is.*|Expecting.*)",
                        "",
                        location_clean,
                        flags=re.IGNORECASE,
                    )

                    if location_clean:
                        # Split locations by common separators and clean each
                        locations_list = []
                        # Split by semicolon first, then by comma
                        for loc_group in location_clean.split(";"):
                            for loc in loc_group.split(","):
                                clean_loc = loc.strip()
                                if clean_loc and clean_loc not in locations_list:
                                    locations_list.append(clean_loc)

                        reported_intensities.append(
                            {"intensity": intensity, "locations": locations_list}
                        )
                        self.logger.debug(
                            f"Added REPORTED intensity {intensity}: {locations_list}"
                        )

                # Extract instrumental intensities
                for intensity, location in re.findall(pattern, instrumental_part):
                    location_clean = location.strip()
                    location_clean = re.sub(
                        r"\s*(This is.*|Expecting.*)",
                        "",
                        location_clean,
                        flags=re.IGNORECASE,
                    )

                    if location_clean:
                        # Split locations by common separators and clean each
                        locations_list = []
                        # Split by semicolon first, then by comma
                        for loc_group in location_clean.split(";"):
                            for loc in loc_group.split(","):
                                clean_loc = loc.strip()
                                if clean_loc and clean_loc not in locations_list:
                                    locations_list.append(clean_loc)

                        instrumental_intensities.append(
                            {"intensity": intensity, "locations": locations_list}
                        )
                        self.logger.debug(
                            f"Added INSTRUMENTAL intensity {intensity}: {locations_list}"
                        )

                earthquake_info["reported_intensities"] = reported_intensities
                earthquake_info["instrumental_intensities"] = instrumental_intensities
                self.logger.debug(
                    f"Extracted {len(reported_intensities)} reported and {len(instrumental_intensities)} instrumental intensities"
                )
            else:
                earthquake_info["reported_intensities"] = []
                earthquake_info["instrumental_intensities"] = []
        except Exception as e:
            self.logger.error(f"Error extracting intensities: {e}")
            earthquake_info["reported_intensities"] = []
            earthquake_info["instrumental_intensities"] = []

        # Extract Issued Date/Time
        try:
            issued_text = None

            # Primary method
            issued_block = self.extract_comment_block(soup, "IssuedDT-Data")

            if issued_block:
                issued_text = issued_block.get_text(strip=True)
            else:
                issued_text = self.extract_label_block(soup, r"Issued\s+On")

            if issued_text and "-" in issued_text:
                issued_date, issued_time = issued_text.split("-", 1)
                earthquake_info["issued_date_str"] = issued_date.strip()
                earthquake_info["issued_time_str"] = issued_time.strip()
                earthquake_info["issued_datetime"] = self.parse_datetime(
                    issued_date.strip(), issued_time.strip()
                )
                self.logger.debug(
                    f"Extracted issued datetime: {earthquake_info['issued_datetime']}"
                )
            else:
                earthquake_info["issued_date_str"] = ""
                earthquake_info["issued_time_str"] = ""
                earthquake_info["issued_datetime"] = None
        except Exception as e:
            self.logger.error(f"Error extracting issued date/time: {e}")
            earthquake_info["issued_date_str"] = ""
            earthquake_info["issued_time_str"] = ""
            earthquake_info["issued_datetime"] = None

        # Extract Authors
        try:
            authors_text = None

            # Primary method
            authors_block = self.extract_comment_block(soup, "PreparedBy-Data")
            if authors_block:
                authors_text = authors_block.get_text(strip=True)
            else:
                authors_text = self.extract_label_block(soup, r"Prepared\s+by")

            if authors_text:
                authors = authors_text.split("/")
                authors_dict = {}
                for i, author in enumerate(authors, start=1):
                    authors_dict[f"auth_{i}"] = author.strip()
                earthquake_info["authors"] = authors_dict
                self.logger.debug(f"Extracted {len(authors)} authors")
            else:
                earthquake_info["authors"] = {}
        except Exception as e:
            self.logger.error(f"Error extracting authors: {e}")
            earthquake_info["authors"] = {}

        # Extract Additional Modern Fields

        # Extract Damage Expectation
        try:
            damage_text = None

            # Primary method
            damage_block = self.extract_comment_block(soup, "Damage-Data")
            if damage_block:
                damage_text = damage_block.get_text(strip=True)
            else:
                damage_text = self.extract_label_block(soup, r"Expecting\s+Damage")

            if damage_text:
                earthquake_info["expecting_damage"] = damage_text.upper()
                self.logger.debug(
                    f"Extracted damage expectation: {earthquake_info['expecting_damage']}"
                )
            else:
                earthquake_info["expecting_damage"] = ""
        except Exception as e:
            self.logger.error(f"Error extracting damage expectation: {e}")
            earthquake_info["expecting_damage"] = ""

        # Extract Aftershock Expectation
        try:
            page_text = None

            aftershock_block = self.extract_comment_block(soup, "Aftershock-Data")
            if aftershock_block:
                page_text = aftershock_block.get_text(strip=True)
            else:
                page_text = self.extract_label_block(soup, r"Expecting\sAftershock")

            if page_text:
                if page_text.upper() in ["YES", "NO"]:
                    earthquake_info["expecting_aftershocks"] = page_text.upper()
                else:
                    aftershock_match = re.search(r"([A-Z]+)", page_text)
                    earthquake_info["expecting_aftershocks"] = (
                        aftershock_match.group(1).upper() if aftershock_match else ""
                    )
            else:
                earthquake_info["expecting_aftershocks"] = ""
        except Exception as e:
            self.logger.error(f"Error extracting aftershock expectation: {e}")
            earthquake_info["expecting_aftershocks"] = ""

        return earthquake_info

    def parse_region_location(self, region_str):
        """Parse region string to extract location, municipality, and province.

        Examples:
        - "015 km N 28° W of San Francisco (Anao-aon) (Surigao Del Norte)"
        - "009 km N 43° W of Pagudpud (Ilocos Norte)"
        """
        location_info = {"location": "", "municipality": "", "province": ""}

        if not region_str:
            return location_info

        try:
            # Pattern to match the region format
            # Group 1: Distance and direction info (e.g., "015 km N 28° W of")
            # Group 2: Main location (e.g., "San Francisco")
            # Group 3: Municipality in first parentheses (e.g., "Anao-aon")
            # Group 4: Province in last parentheses (e.g., "Surigao Del Norte")

            # First, extract all content in parentheses from right to left
            # \( -> Matches a literal opening parenthesis
            # [^)]+ -> Matches one or more characters that are not a closing parenthesis )
            # \) -> Matches a literal closing parenthesis
            parentheses_matches = re.findall(r"\(([^)]+)\)", region_str)

            if parentheses_matches:
                # Last parentheses is always the province
                location_info["province"] = parentheses_matches[-1].strip()

                # If there are 2 parentheses, first one is municipality
                if len(parentheses_matches) >= 2:
                    location_info["municipality"] = parentheses_matches[-2].strip()

            # Extract the main location name (after "of" and before first parenthesis)
            location_match = re.search(r"of\s+([^(]+?)(?:\s*\(|$)", region_str)
            if location_match:
                location_info["location"] = location_match.group(1).strip()

            self.logger.debug(f"Parsed region '{region_str}' -> {location_info}")

        except Exception as e:
            self.logger.error(f"Error parsing region location '{region_str}': {e}")

        return location_info

    def scrape_single_event(self, url):
        """Scrape a single earthquake event from its URL."""
        self.logger.info(f"Scraping single modern event: {url}")

        soup = self.fetch_page(url)
        if not soup:
            return None

        earthquake_data = self.extract_earthquake_details(soup)

        self.logger.info(
            f"Successfully scraped modern earthquake #{earthquake_data.get('eq_no', 'unknown')}"
        )
        return earthquake_data

    def save_to_json(self, data, filename: str = "modern_earthquake_data.json"):
        """Save earthquake data to JSON file."""
        try:

            def json_serial(obj):
                """JSON serializer for datetime objects."""
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            with open(filename, "w", encoding="utf-8") as json_file:
                json.dump(
                    data, json_file, default=json_serial, indent=4, ensure_ascii=False
                )

            self.logger.info(f"Successfully saved {len(data)} records to {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save data to {filename}: {e}")
            return False


def main():
    """Main execution function for testing with the 2022 format."""
    # 2022 URL for testing
    # test_url = "https://earthquake.phivolcs.dost.gov.ph/2022_Earthquake_Information/July/2022_0727_2002_B3F.html"
    test_url = "https://earthquake.phivolcs.dost.gov.ph/2025_Earthquake_Information/July/2025_0719_1625_B3F.html"

    scraper = ModernEarthquakeScraper()

    # Scrape single event
    earthquake_data = scraper.scrape_single_event(test_url)

    if earthquake_data:
        # Save to JSON
        scraper.save_to_json([earthquake_data], "modern_earthquake_2022.json")
        print(f"Successfully scraped modern earthquake data:")
        print(f"- EQ Number: {earthquake_data.get('eq_no')}")
        print(f"- DateTime: {earthquake_data.get('datetime')}")
        print(f"- Location: {earthquake_data.get('region')}")
        print(
            f"- Magnitude: {earthquake_data.get('magnitude_type')} {earthquake_data.get('magnitude_value')}"
        )
        print(f"- Depth: {earthquake_data.get('depth_km')} km")
        print(f"- Origin: {earthquake_data.get('origin')}")
        print(
            f"- Reported Intensities: {len(earthquake_data.get('reported_intensities', []))}"
        )
        print(
            f"- Instrumental Intensities: {len(earthquake_data.get('instrumental_intensities', []))}"
        )
        print(f"- Expecting Damage: {earthquake_data.get('expecting_damage')}")
        print(
            f"- Expecting Aftershocks: {earthquake_data.get('expecting_aftershocks')}"
        )
    else:
        print("Failed to scrape earthquake data")


if __name__ == "__main__":
    main()
