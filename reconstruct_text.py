# Import necessary libraries and modules
from adobe_PDF_extract_API import ExtractTextInfoFromPDF
import os
from pymongo.mongo_client import MongoClient
#from key_params import uri
from dotenv import load_dotenv


load_dotenv()
# Load environment variables from .env file
uri = os.getenv('uri')

# Create a new client and connect to the server
client = MongoClient(uri)

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

# Access the capstone database
capstone_db = client['capstone_db']

# Access the adobe_api_json_outputs collection
adobe_api_json_outputs_db = capstone_db['adobe_api_json_outputs']

# Count documents in the adobe_api_json_outputs collection
adobe_api_json_outputs_db.count_documents({})

# Access the documents_data collection
documents_data_db = capstone_db['documents_data']

# Count documents in the documents_data collection
documents_data_db.count_documents({})

# Function to find all PDF files in a directory (including nested directories)
def find_all_pdfs(root_folder):
    """
    Recursively search for PDF files in a directory and its subdirectories.
    
    Args:
        root_folder (str): Root directory path to start the search
    
    Returns:
        dict: Dictionary of file names and their absolute paths
    
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
    # Initialize an empty dictionary to store PDF files
    pdf_files = {}  
    # Iterate over each folder and subfolder in the directory tree
    for foldername, subfolders, filenames in os.walk(root_folder):
        # Iterate over each file in the directory
        for filename in filenames:
            # Check if the file is a PDF
            if filename.lower().endswith('.pdf'):
                # Construct the full path to the file
                full_path = os.path.join(foldername, filename)
                # Store the file name and its full path
                pdf_files[filename] = full_path
    # Return the dictionary of PDF files
    return pdf_files

def reconstruct_document_exclude_toc(data):
    """
    Reconstructs document text excluding elements identified as Table of Contents (TOC).

    Args:
        data (dict): Data containing document elements.

    Returns:
        str: Combined text of the document excluding TOC elements.
    """
    # Get the list of elements from the data
    elements = data.get("elements", [])
    # Initialize an empty list to store the reconstructed text
    reconstructed_text = []

    # Filter out elements where 'Path' contains "TOC"
    for element in elements:
        # Get the path and text of the element
        path = element.get("Path", "")
        text = element.get("Text", "")

        # Exclude TOC elements and empty text
        if "TOC" not in path and text.strip():
            # Add the text to the reconstructed text list
            reconstructed_text.append(text)

    # Combine all the text into a single string
    combined_text = "\n".join(reconstructed_text)

    # Return the combined text
    return combined_text

def get_adobe_api_json_outputs_db(file_name, db_collection):
    """
    Retrieves JSON output for a given file from the Adobe API JSON outputs database.

    Args:
        file_name (str): The name of the file to retrieve.
        db_collection: The MongoDB collection to query.

    Returns:
        dict: The JSON document from the database.
    """
    # Find the document in the database
    file_json = db_collection.find_one({'file_name': file_name})
    # Return the JSON document
    return file_json

def update_documents_data_db(file_name, text, db_collection):
    """
    Updates the documents data database with cleaned text excluding TOC.

    Args:
        file_name (str): The name of the file to update.
        text (str): The text data to clean and update in the database.
        db_collection: The MongoDB collection to update.
    """
    # Remove the file extension from the file name
    file_name = os.path.splitext(file_name)[0]
    # Retrieve the JSON output from the database
    data = get_adobe_api_json_outputs_db(file_name, adobe_api_json_outputs_db)
    if data:
        # Reconstruct the document text excluding TOC
        cleaned_text = reconstruct_document_exclude_toc(text)
        # Update the document in the database
        result = db_collection.update_one(
            {"file_name": file_name},
            {"$set": {"cleaned_text": cleaned_text}}
        )
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
