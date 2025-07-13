from flask import Flask, request, jsonify
import nodriver as uc
import asyncio
import threading
import logging
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variable to store the driver instance
driver = None

# Function to start the driver (only once)
async def start_driver():
    global driver
    try:
        if driver is None:
            logger.info("Starting driver...")
            # Add no_sandbox=True and additional configuration
            driver = await uc.start(
                headless=False,
                no_sandbox=True,
                browser_args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu'
                ]
            )
            logger.info("Driver started successfully")
    except Exception as e:
        logger.error(f"Error starting driver: {str(e)}")
        raise

# Async scraper function with retry logic
async def scraper(url, max_retries=3):
    global driver
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Ensure that the driver is started
            await start_driver()

            # Visit the target website
            logger.info(f"Accessing URL: {url}")
            page = await driver.get(url)
            
            # Fix cookies format
            cookies = [{'name': 'sussytoons-terms-accepted', 'value': 'true'}]
            await driver.cookies.set_all(cookies)
            
            # Wait for JavaScript to load
            logger.info("Waiting for page load...")
            await asyncio.sleep(5)

            # wait cloudflare anti-bot
            await asyncio.sleep(10)

            # Get the full-page HTML    
            html_content = await page.get_content()
            logger.info("Successfully retrieved page content")

            return html_content
        except Exception as e:
            retry_count += 1
            logger.error(f"Error in scraper (attempt {retry_count}/{max_retries}): {str(e)}")
            if retry_count < max_retries:
                logger.info("Retrying in 2 seconds...")
                await asyncio.sleep(2)
                # Reset driver on retry
                driver = None
            else:
                raise

# Helper function to run async functions in a thread
def run_async(func, *args):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(func(*args))
    except Exception as e:
        logger.error(f"Error in run_async: {str(e)}")
        raise

@app.route('/scrape', methods=['GET'])
def scrape():
    url = request.args.get('url')  # Get URL from query parameters
    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        # Run async scraper function in a thread
        html_content = run_async(scraper, url)
        return jsonify({"url": url, "html": html_content})
    except Exception as e:
        logger.error(f"Error in scrape endpoint: {str(e)}")
        return jsonify({"error": str(e), "details": "An error occurred while scraping the URL"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3333)
