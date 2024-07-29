import argparse
from PIL import Image

# Create an ArgumentParser object
parser = argparse.ArgumentParser(description='Image processing tool.')

# Add command-line arguments
parser.add_argument(
    '--input_image',
    type=str,
    required=True,
    help='Path to the input image file.'
)

parser.add_argument(
    '--output_image',
    type=str,
    default='output_image.jpg',
    help='Path to the output image file (default: output_image.jpg).'
)

parser.add_argument(
    '--format',
    type=str,
    default='JPEG',
    help='Format to save the image in (default: JPEG).'
)

parser.add_argument(
    '--quality',
    type=int,
    default=85,
    help='Quality of the saved image (default: 85).'
)

# Parse command-line arguments
args = parser.parse_args()

# Process the image
image = Image.open(args.input_image)
image.save(args.output_image, format=args.format, quality=args.quality)

print(f'Processed image saved as {args.output_image}.')
