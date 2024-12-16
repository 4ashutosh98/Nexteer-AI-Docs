import os
import fitz  # PyMuPDF for text extraction from PDF
from collections import defaultdict
import tiktoken
from pymongo.mongo_client import MongoClient
from adobe_PDF_extract_API import ExtractTextInfoFromPDF
from reconstruct_text import reconstruct_document_exclude_toc, get_adobe_api_json_outputs_db
from tqdm import tqdm
import re

# MongoDB connection setup
uri = "mongodb+srv://capstone:harshhasdonejackshit@nexteer-capstone.ru1pt.mongodb.net/"
client = MongoClient(uri)
capstone_db = client['capstone_db']
documents_data_db = capstone_db['documents_data']
adobe_api_json_outputs_db = capstone_db['adobe_api_json_outputs']

# Function to extract text from each page of the PDF
def extract_page_texts(file_path):
    doc = fitz.open(file_path)
    page_texts = [page.get_text() for page in doc]
    total_pages = len(page_texts)
    return page_texts, total_pages

# Function to remove page numbers
def remove_page_numbers(text):
    page_patterns = [
        r'\bPage\s*\d+(\s*of\s*\d+)?\b',
        r'\bPg\.\s*\d+(\s*of\s*\d+)?\b',
        r'\bP\.\s*\d+(\s*of\s*\d+)?\b',
        r'\bpage\s*\d+(\s*of\s*\d+)?\b',
    ]
    combined_pattern = re.compile("|".join(page_patterns), re.IGNORECASE)
    return combined_pattern.sub("", text)

# Function to remove headers and footers from the text
def remove_headers_footers(page_texts, headers, footers):
    cleaned_pages = []
    for page_text in tqdm(page_texts, desc="Removing headers, footers, and page numbers"):
        lines = page_text.splitlines()
        cleaned_lines = [line for line in lines if line not in headers and line not in footers]
        cleaned_text = "\n".join(cleaned_lines)
        cleaned_text = remove_page_numbers(cleaned_text)
        cleaned_pages.append(cleaned_text)
    return cleaned_pages

# Function to detect repeated headers and footers
def detect_repeated_headers_footers(page_texts, min_repetition=3, max_repetition=None, num_lines_to_check=7):
    header_candidates = defaultdict(int)
    footer_candidates = defaultdict(int)

    for page_text in tqdm(page_texts, desc="Analyzing pages for headers/footers"):
        lines = page_text.splitlines()
        if len(lines) > num_lines_to_check * 2:
            headers = lines[:num_lines_to_check]
            footers = lines[-num_lines_to_check:]

            for header in headers:
                header_candidates[header] += 1
            for footer in footers:
                footer_candidates[footer] += 1

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
    # Initialize the tokenizer for GPT-4o (assuming it behaves similarly to other OpenAI models)
    encoder = tiktoken.encoding_for_model(model)
    
    # Encode the text and count tokens
    tokens = encoder.encode(text)
    return len(tokens)

# Main function to process a PDF file and upload data to MongoDB
def process_and_upload_pdf(file_path):
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    page_texts, total_pages = extract_page_texts(file_path)
    headers, footers = detect_repeated_headers_footers(page_texts)
    cleaned_pages = remove_headers_footers(page_texts, headers, footers)
    adobe_api_json_output = get_adobe_api_json_outputs_db(file_name, adobe_api_json_outputs_db)

    cleaned_text = reconstruct_document_exclude_toc(adobe_api_json_output)

    token_count = count_tokens(cleaned_text)

    # Create document data
    document_data = {
        "file_name": file_name,
        "cleaned_text": cleaned_text,
        "cleaned_pages": cleaned_pages,
        "headers": list(headers),
        "footers": list(footers),
        "total_pages": total_pages,
        "token_count": token_count  # Example token count
    }

    # Upload to MongoDB
    documents_data_db.update_one(
        {"file_name": file_name},
        {"$set": document_data},
        upsert=True
    )
    print(f"Processed and uploaded {file_name} to documents_data collection.")
