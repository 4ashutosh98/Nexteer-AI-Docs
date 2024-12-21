# Import necessary libraries and modules
import os
import fitz  # PyMuPDF for text extraction from PDF
from collections import defaultdict
import tiktoken
from pymongo.mongo_client import MongoClient
from reconstruct_text import reconstruct_document_exclude_toc, get_adobe_api_json_outputs_db
from tqdm import tqdm
import re
from key_params import uri

# MongoDB connection setup
# Connect to the MongoDB client using the provided URI
client = MongoClient(uri)
# Select the 'capstone_db' database
capstone_db = client['capstone_db']
# Select the 'documents_data' collection
documents_data_db = capstone_db['documents_data']
# Select the 'adobe_api_json_outputs' collection
adobe_api_json_outputs_db = capstone_db['adobe_api_json_outputs']

# Function to extract text from each page of the PDF
def extract_page_texts(file_path):
    """
    Extracts text from each page of a PDF file.

    Args:
        file_path (str): The path to the PDF file.

    Returns:
        tuple: A tuple containing a list of page texts and the total number of pages.
    """
    # Open the PDF file
    doc = fitz.open(file_path)
    # Extract text from each page
    page_texts = [page.get_text() for page in doc]
    # Get the total number of pages
    total_pages = len(page_texts)
    return page_texts, total_pages

# Function to remove page numbers
def remove_page_numbers(text):
    """
    Removes page numbers from the given text using predefined patterns.

    Args:
        text (str): The text from which to remove page numbers.

    Returns:
        str: The text without page numbers.
    """
    # Define patterns to identify page numbers
    page_patterns = [
        r'\bPage\s*\d+(\s*of\s*\d+)?\b',
        r'\bPg\.\s*\d+(\s*of\s*\d+)?\b',
        r'\bP\.\s*\d+(\s*of\s*\d+)?\b',
        r'\bpage\s*\d+(\s*of\s*\d+)?\b',
    ]
    # Compile the patterns into a regex
    combined_pattern = re.compile("|".join(page_patterns), re.IGNORECASE)
    # Remove page numbers from the text
    return combined_pattern.sub("", text)

# Function to remove headers and footers from the text
def remove_headers_footers(page_texts, headers, footers):
    """
    Removes headers and footers from each page of text.

    Args:
        page_texts (list): List of texts from each page of the document.
        headers (set): Set of detected header strings.
        footers (set): Set of detected footer strings.

    Returns:
        list: List of cleaned page texts without headers and footers.
    """
    # Initialize a list to store cleaned pages
    cleaned_pages = []
    # Iterate over each page text
    for page_text in tqdm(page_texts, desc="Removing headers, footers, and page numbers"):
        # Split the page text into lines
        lines = page_text.splitlines()
        # Remove lines that are headers or footers
        cleaned_lines = [line for line in lines if line not in headers and line not in footers]
        # Join the cleaned lines back into a single text
        cleaned_text = "\n".join(cleaned_lines)
        # Remove page numbers from the cleaned text
        cleaned_text = remove_page_numbers(cleaned_text)
        # Add the cleaned text to the list
        cleaned_pages.append(cleaned_text)
    return cleaned_pages

# Function to detect repeated headers and footers
def detect_repeated_headers_footers(page_texts, min_repetition=3, max_repetition=None, num_lines_to_check=7):
    """
    Detects repeated headers and footers in the document pages.

    Args:
        page_texts (list): List of texts from each page of the document.
        min_repetition (int): Minimum number of repetitions for a line to be considered a header/footer.
        max_repetition (int | None): Maximum number of repetitions for a line to be considered a header/footer.
        num_lines_to_check (int): Number of lines to check at the top and bottom of each page.

    Returns:
        tuple: A tuple containing sets of detected headers and footers.
    """
    # Initialize dictionaries to count header and footer candidates
    header_candidates = defaultdict(int)
    footer_candidates = defaultdict(int)

    # Iterate over each page text
    for page_text in tqdm(page_texts, desc="Analyzing pages for headers/footers"):
        # Split the page text into lines
        lines = page_text.splitlines()
        # Check if the page has enough lines to analyze
        if len(lines) > num_lines_to_check * 2:
            # Extract potential headers and footers
            headers = lines[:num_lines_to_check]
            footers = lines[-num_lines_to_check:]

            # Count occurrences of each header and footer
            for header in headers:
                header_candidates[header] += 1
            for footer in footers:
                footer_candidates[footer] += 1

    # Filter headers and footers based on repetition criteria
    headers = {
        header for header, count in header_candidates.items()
        if count >= min_repetition and (max_repetition is None or count <= max_repetition)
    }
    footers = {
        footer for footer, count in footer_candidates.items()
        if count >= min_repetition and (max_repetition is None or count <= max_repetition)
    }

    return headers, footers

# Function to count the number of tokens in a given text
def count_tokens(text, model="gpt-4o"):
    """
    Counts the number of tokens in a given text using the specified model's tokenizer.

    Args:
        text (str): The text to tokenize.
        model (str): The model whose tokenizer to use.

    Returns:
        int: The number of tokens in the text.
    """
    # Initialize the tokenizer for GPT-4o (assuming it behaves similarly to other OpenAI models)
    encoder = tiktoken.encoding_for_model(model)
    
    # Encode the text and count tokens
    tokens = encoder.encode(text)
    return len(tokens)

# Main function to process a PDF file and upload data to MongoDB
def process_and_upload_pdf(file_path):
    """
    Processes a PDF file to extract and clean text, then uploads the data to MongoDB.

    Args:
        file_path (str): The path to the PDF file.
    """
    # Get the file name without extension
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    # Extract text from each page of the PDF
    page_texts, total_pages = extract_page_texts(file_path)
    # Detect repeated headers and footers
    headers, footers = detect_repeated_headers_footers(page_texts)
    # Remove headers and footers from the page texts
    cleaned_pages = remove_headers_footers(page_texts, headers, footers)
    # Get the JSON output from the Adobe API
    adobe_api_json_output = get_adobe_api_json_outputs_db(file_name, adobe_api_json_outputs_db)

    # Reconstruct the document text excluding the table of contents
    cleaned_text = reconstruct_document_exclude_toc(adobe_api_json_output)

    # Count the number of tokens in the cleaned text
    token_count = count_tokens(cleaned_text)

    # Create document data
    document_data = {
        "file_name": file_name,
        "cleaned_text": cleaned_text,
        "cleaned_pages": cleaned_pages,
        "headers": list(headers),
        "footers": list(footers),
        "total_pages": total_pages,
        "token_count": token_count
    }

    # Upload to MongoDB
    documents_data_db.update_one(
        {"file_name": file_name},
        {"$set": document_data},
        upsert=True
    )
    print(f"Processed and uploaded {file_name} to documents_data collection.")
