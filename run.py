import argparse
import sys

# Add src to the Python path to allow for absolute imports
sys.path.insert(0, './src')

def main():
    """
    Unified entry point for the Telegram Summarizer application.
    
    Handles command-line arguments to run different components:
    - scrape: Starts the Telethon scraper to listen for new messages.
    - bot: Starts the Telegram bot for summarizing messages.
    - web: Starts the Flask web dashboard.
    """
    parser = argparse.ArgumentParser(
        description="Unified entry point for the Telegram Summarizer application."
    )
    parser.add_argument(
        "component",
        choices=['scrape', 'bot', 'web'],
        help="The component of the application to run."
    )
    
    args = parser.parse_args()
    
    if args.component == 'scrape':
        print("Starting the message scraper...")
        from scraper.main import run as run_scraper
        run_scraper()
    
    elif args.component == 'bot':
        print("Starting the Telegram summary bot...")
        from bot.main import run as run_bot
        run_bot()
        
    elif args.component == 'web':
        print("Starting the Flask web dashboard...")
        from web.main import run as run_web
        run_web()

if __name__ == '__main__':
    main()
