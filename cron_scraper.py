from main import DailyUpdateScraper
import logging
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime


# Setup
def setup_environment():
    """Ensure we're in the right directory and environment is loaded"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    load_dotenv()  # Load .env after changing to project directory


def setup_logging():
    """Configure logging for cron execution"""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    logger = logging.getLogger("cron_scraper")
    logger.setLevel(logging.INFO)

    # File handler - single append file for all cron runs
    if not logger.handlers:
        log_file = logs_dir / "cron.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def main():
    """Main execution"""
    # Setup
    setup_environment()
    logger = setup_logging()

    logger.info("=== CRON SCRAPER STARTED ===")

    try:
        logger.info("Initializing DailyUpdateScraper...")
        scraper = DailyUpdateScraper()

        logger.info("Starting daily earthquake data scraping...")
        result = scraper.process_daily_updates()

        # Log results
        if result:
            logger.info(f"Scraping completed successfully. Result: {result}")
        else:
            logger.info("Scraping completed successfully.")
        
        logger.info("=== CRON SCRAPER COMPLETED SUCCESSFULLY ===")
        exit(0)  # Success exit code

    except Exception as e:
        logger.error(f"=== CRON SCRAPER FAILED: {str(e)} ===")
        exit(1)  # Failure exit code


if __name__ == "__main__":
    main()
