import argparse
import requests

# Create an ArgumentParser object
parser = argparse.ArgumentParser(description='Web scraping tool.')

# Add command-line arguments
parser.add_argument(
    '--url',
    type=str,
    required=True,
    help='The URL to scrape data from.'
)

parser.add_argument(
    '--output_file',
    type=str,
    default='scraped_data.txt',
    help='Path to the output file (default: scraped_data.txt).'
)

parser.add_argument(
    '--log',
    action='store_true',
    help='Enable logging of the scraping process (default: disabled).'
)

# Parse command-line arguments
args = parser.parse_args()

# Perform the web scraping
response = requests.get(args.url)
data = response.text

# Save the scraped data
with open(args.output_file, 'w') as file:
    file.write(data)

if args.log:
    print(f'URL scraped: {args.url}')
    print(f'Data saved to: {args.output_file}')
