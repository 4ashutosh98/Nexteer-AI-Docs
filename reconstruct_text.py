from adobe_PDF_extract_API import ExtractTextInfoFromPDF
import os
from pymongo.mongo_client import MongoClient
from key_params import uri

# Create a new client and connect to the server
client = MongoClient(uri)

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)


capstone_db = client['capstone_db']

adobe_api_json_outputs_db = capstone_db['adobe_api_json_outputs']

adobe_api_json_outputs_db.count_documents({})

documents_data_db = capstone_db['documents_data']

documents_data_db.count_documents({})

# Function to find all PDF files in a directory (including nested directories)
def find_all_pdfs(root_folder):
    """
    Recursively search for PDF files in a directory and its subdirectories.
    
    Args:
        root_folder (str): Root directory path to start the search
    
    Returns:
        list: List of absolute paths to all PDF files found
    
    Behavior:
        1. Walks through directory tree recursively
        2. Identifies files with .pdf extension
        3. Collects absolute paths of PDF files
        4. Prints progress information:
           - Current folder being checked
           - Each PDF file found with path
    
    Note:
        - Case-insensitive PDF extension matching
        - Maintains original directory structure
        - Provides search progress feedback
    """
    pdf_files = {}  # Dictionary to store the file name and path
    for foldername, subfolders, filenames in os.walk(root_folder):
        #print(f"Checking folder: {foldername}")  # Debug: See which folder is being checked
        for filename in filenames:
            if filename.lower().endswith('.pdf'):  # Check if the file is a PDF
                full_path = os.path.join(foldername, filename)
                #print(f"Found PDF: {filename} in {full_path}")  # Debug: Report found PDFs
                pdf_files[filename] = full_path  # Store the file name and its full path
    return pdf_files

def reconstruct_document_exclude_toc(data):
    elements = data.get("elements", [])
    reconstructed_text = []

    # Filter out elements where 'Path' contains "TOC"
    for element in elements:
        path = element.get("Path", "")
        text = element.get("Text", "")

        if "TOC" not in path and text.strip():  # Exclude TOC elements and empty text
            reconstructed_text.append(text)

    # Combine all the text into a single string
    combined_text = "\n".join(reconstructed_text)

    return combined_text

def get_adobe_api_json_outputs_db(file_name, db_collection):
    file_json = db_collection.find_one({'file_name': file_name})
    return file_json

def update_documents_data_db(file_name, text, db_collection):
    file_name = os.path.splitext(file_name)[0]
    data = get_adobe_api_json_outputs_db(file_name, adobe_api_json_outputs_db)
    if data:
        cleaned_text = reconstruct_document_exclude_toc(text)
        result = db_collection.update_one(
            {"file_name": file_name},
            {"$set": {"cleaned_text": cleaned_text}}
        )
        #print(f"{pdf_file} updated in the database")
        # Check the result
        if result.matched_count > 0:
            if result.modified_count > 0:
                print("Document updated successfully!")
            else:
                print("Document found, but no changes were made.")
        else:
            print("No document found with the specified file_name.")
    else:
        print(f"{file_name} not found in the database")
        
