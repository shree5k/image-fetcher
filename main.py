import os
import requests
from selenium import webdriver
from bs4 import BeautifulSoup
import time
from io import BytesIO
from PIL import Image
import filetype
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration constants
HOTSTAR_URL = "https://www.jiohotstar.com"
MAX_SCROLLS = 3
SCROLL_DELAY = 2
WINDOW_SIZE = (5000, 2000)
MAX_DOWNLOAD_RETRIES = 3


def setup_webdriver() -> webdriver.Chrome:
    """Set up and configure the Selenium WebDriver."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    driver.set_window_size(*WINDOW_SIZE)
    return driver


def scroll_until_all_sections_found(driver: webdriver.Chrome, max_scrolls: int = MAX_SCROLLS) -> List[str]:
    section_titles = []
    
    for _ in range(max_scrolls):
        try:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            tray_containers = soup.find_all("div", {"data-testid": "tray-container-base-wrapper"})
            
            for tray_container in tray_containers:
                header_container = tray_container.find("div", {"data-testid": "action"})
                if header_container:
                    h2_tag = header_container.find("h2")
                    if h2_tag:
                        title = h2_tag.text.strip()
                        if title and title not in section_titles:
                            section_titles.append(title)
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_DELAY)
            
        except Exception as e:
            logger.error(f"Error while scrolling: {e}")
            break
    
    return section_titles


def download_image(image_url: str, folder_path: str, retries: int = MAX_DOWNLOAD_RETRIES) -> bool:
    try:
        for attempt in range(retries):
            try:
                response = requests.get(image_url, stream=True)
                response.raise_for_status()
                
                image_data = BytesIO(response.content)
                kind = filetype.guess(image_data.getvalue())
                
                if kind is None:
                    logger.warning(f"Cannot guess file type for {image_url}")
                    return False
                    
                image_format = kind.extension
                img = Image.open(image_data)
                
                filename = os.path.join(folder_path, 
                                    os.path.basename(image_url).split('.')[0] + '.' + image_format)
                img.save(filename)
                logger.info(f"Successfully downloaded: {filename}")
                return True
                
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Failed to download {image_url} after {retries} attempts: {e}")
                    return False
                time.sleep(1)  # Wait before retrying
                
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for {image_url}: {e}")
        return False


def create_output_directory(section_title: str) -> str:
    folder_name = section_title.replace(" ", "_").lower() + "_images"
    os.makedirs(folder_name, exist_ok=True)
    return folder_name


def main():
    try:
        # Initialize WebDriver
        driver = setup_webdriver()
        driver.get(HOTSTAR_URL)
        time.sleep(5)  # Wait for page load
        
        # Get all sections
        section_titles = scroll_until_all_sections_found(driver)
        
        if not section_titles:
            logger.error("No sections found on the page.")
            return
            
        print("\nAvailable Sections:")
        for i, title in enumerate(section_titles):
            print(f"{i + 1}. {title}")
        
        # Get user selection
        while True:
            try:
                choice = int(input("\nEnter the number of the section to download images from: "))
                if 1 <= choice <= len(section_titles):
                    break
                print("Invalid choice. Please enter a number from the list.")
            except ValueError:
                print("Invalid input. Please enter a number.")
        
        selected_section_title = section_titles[choice - 1]
        logger.info(f"Selected section: {selected_section_title}")
        
        # Create output directory
        image_folder = create_output_directory(selected_section_title)
        logger.info(f"Output directory: {image_folder}")
        
        # Parse and download images
        soup = BeautifulSoup(driver.page_source, "html.parser")
        tray_containers = soup.find_all("div", {"data-testid": "tray-container-base-wrapper"})
        
        for tray_container in tray_containers:
            header_container = tray_container.find("div", {"data-testid": "action"})
            if header_container:
                h2_tag = header_container.find("h2")
                if h2_tag and h2_tag.text.strip().lower() == selected_section_title.lower():
                    image_divs = tray_container.find_all("div", {"data-testid": "hs-image"})
                    
                    total_images = len(image_divs)
                    logger.info(f"Found {total_images} images to download")
                    
                    for i, img_div in enumerate(image_divs, 1):
                        img = img_div.find("img")
                        if img:
                            img_url = img.get("src")
                            if img_url:
                                success = download_image(img_url, image_folder)
                                if success:
                                    logger.info(f"Completed {i}/{total_images}")
                            else:
                                logger.warning("Image source not found")
                        else:
                            logger.warning("Image tag not found")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        if 'driver' in locals():
            driver.quit()


if __name__ == "__main__":
    main()