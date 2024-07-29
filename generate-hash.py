import argparse
import hashlib

def calculate_hash(text, algorithm):
    """Calculate the specified hash of the given text."""
    try:
        # Create a hash object using the specified algorithm
        hash_obj = hashlib.new(algorithm)
    except ValueError as e:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}") from e
    
    # Update the hash object with the byte-encoded text
    hash_obj.update(text.encode('utf-8'))
    # Return the hexadecimal digest of the hash
    return hash_obj.hexdigest()

def main():
    # Create argument parser
    parser = argparse.ArgumentParser(description='Calculate the hash value of the given text.')
    
    # Add command-line arguments
    parser.add_argument('text', type=str, help='Text to hash')
    parser.add_argument('algorithm', type=str, choices=hashlib.algorithms_available,
                        help='Hash algorithm to use. Available choices: ' + ', '.join(hashlib.algorithms_available))
    
    # Parse command-line arguments
    args = parser.parse_args()
    
    # Get the text and algorithm from arguments
    text = args.text
    algorithm = args.algorithm
    
    # Calculate the hash and print the result
    hash_value = calculate_hash(text, algorithm)
    print(f'The {algorithm} hash of the text is: {hash_value}')

if __name__ == '__main__':
    main()
