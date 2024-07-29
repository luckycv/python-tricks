import argparse

# Create an ArgumentParser object
parser = argparse.ArgumentParser(description='A script that demonstrates command-line arguments with default values.')

# Add command-line arguments
parser.add_argument(
    '--param1',
    type=int,
    default=10,
    help='An integer parameter with a default value of 10.'
)

parser.add_argument(
    '--param2',
    type=str,
    default='default_value',
    help='A string parameter with a default value of "default_value".'
)

parser.add_argument(
    '--param3',
    action='store_true',
    help='A boolean flag parameter (default is False).'
)

# Parse command-line arguments
args = parser.parse_args()

# Use command-line arguments
print(f'param1: {args.param1}')
print(f'param2: {args.param2}')
print(f'param3: {args.param3}')
