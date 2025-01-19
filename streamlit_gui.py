# Import necessary libraries and modules
import streamlit as st
from pymongo import MongoClient
import os
from adobe_PDF_extract_API import ExtractTextInfoFromPDF
from app import upload_json_file_to_mongodb, find_section_wise_differences_in_files
from section_processing import process_and_upload_pdf
from document_comparison import get_sections_from_db, fetch_old_and_new_text, process_and_compare_pdfs
import shutil
from dotenv import load_dotenv


load_dotenv()
# Load environment variables from .env file
uri = os.getenv('uri')

# MongoDB connection setup
# Connect to the MongoDB client using the provided URI
client = MongoClient(uri)
# Select the 'capstone_db' database
capstone_db = client['capstone_db']
# Select the 'documents_data' collection
documents_data_db = capstone_db['documents_data']
# Select the 'adobe_api_json_outputs' collection
adobe_api_json_outputs_db = capstone_db['adobe_api_json_outputs']
# Select the 'sections_data' collection
sections_data_db = capstone_db['sections_data']

# Clear the contents of the folder at startup
def clear_upload_dir():
    """
    Clears the contents of the upload directory to ensure a fresh start.

    This function is called at the beginning of the application to remove any existing files in the upload directory.
    """
    # Check if the upload directory exists
    if os.path.exists(UPLOAD_DIR):
        # Iterate over the files in the upload directory
        for file_name in os.listdir(UPLOAD_DIR):
            # Construct the full path to the file
            file_path = os.path.join(UPLOAD_DIR, file_name)
            try:
                # Check if the file is a file or a link
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    # Remove the file or link
                    os.unlink(file_path)
                # Check if the file is a directory
                elif os.path.isdir(file_path):
                    # Remove the directory
                    shutil.rmtree(file_path)
            except Exception as e:
                # Print an error message if the file cannot be deleted
                print(f"Failed to delete {file_path}: {e}")

# Directory to save uploaded PDF files
UPLOAD_DIR = "uploaded_pdfs"
# Create the upload directory if it does not exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Clear folder at startup
# Call the function to clear the upload directory
clear_upload_dir()

# Helper function to get the base name without extension
def get_base_filename(file):
    """
    Returns the base name of a file without its extension.

    Args:
        file: The file object.

    Returns:
        str: The base name of the file.
    """
    # Extract the base name from the file name
    return os.path.splitext(file.name)[0]

# Function to save uploaded file
def save_uploaded_file(uploaded_file):
    """
    Saves the uploaded PDF file to the upload directory.

    Args:
        uploaded_file: The uploaded file object.

    Returns:
        str | None: The path to the saved file or None if not a PDF.
    """
    # Check if the uploaded file is a PDF
    if uploaded_file.type == "application/pdf":
        # Construct the full path to the file
        file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        # Open the file in binary write mode
        with open(file_path, "wb") as f:
            # Write the file buffer to the path
            f.write(uploaded_file.getbuffer())
        # Return the path to the saved file
        return file_path
    else:
        # Display an error message if the file is not a PDF
        st.error("Uploaded file is not a PDF.")
        # Return None
        return None

# Streamlit UI setup
# Set the title of the app
st.title("PDF Document Comparison")

# Upload PDFs
# Upload the new file
uploaded_pdf1 = st.sidebar.file_uploader("Upload the new File")
# Upload the old file
uploaded_pdf2 = st.sidebar.file_uploader("Upload the old File")

# Check if both files are uploaded
if uploaded_pdf1 and uploaded_pdf2:
    # Save uploaded PDFs
    # Save the new file
    file_path1 = save_uploaded_file(uploaded_pdf1)
    # Save the old file
    file_path2 = save_uploaded_file(uploaded_pdf2)

    # Check if both files are saved successfully
    if file_path1 and file_path2:
        # Display subheader
        st.subheader("Uploaded Files")
        # Display the new file name
        st.text(f"New File: {uploaded_pdf1.name}")
        # Display the old file name
        st.text(f"Old File: {uploaded_pdf2.name}")

        # Check if the first file is in the MongoDB collections
        # Check if the file is in the 'adobe_api_json_outputs' collection
        file1_in_adobe = adobe_api_json_outputs_db.find_one({"file_name": get_base_filename(uploaded_pdf1)})
        # Check if the file is in the 'documents_data' collection
        file1_in_documents = documents_data_db.find_one({"file_name": get_base_filename(uploaded_pdf1)})

        # Display results for the first file
        # Check if the file is in the 'adobe_api_json_outputs' collection
        if file1_in_adobe:
            # Display a success message
            st.success(f"{uploaded_pdf1.name} is present in the Adobe API outputs collection.")
        else:
            # Display a warning message
            st.warning(f"{uploaded_pdf1.name} is not present in the Adobe API outputs collection.")
            # Display an info message
            st.info(f"Processing {uploaded_pdf1.name} with Adobe API...")
            # Create an instance of the ExtractTextInfoFromPDF class
            extractor = ExtractTextInfoFromPDF(file_path1)
            # Extract the text from the PDF
            json_path = extractor.extract_text()
            # Check if the text is extracted successfully
            if json_path:
                # Upload the JSON file to the 'adobe_api_json_outputs' collection
                upload_json_file_to_mongodb(json_path, adobe_api_json_outputs_db)
                # Display a success message
                st.success(f"Processed and uploaded {uploaded_pdf1.name} to Adobe API outputs collection.")

        # Check if the file is in the 'documents_data' collection
        if file1_in_documents:
            # Display a success message
            st.success(f"{uploaded_pdf1.name} is present in the documents data collection.")
        else:
            # Process and upload the file to the 'documents_data' collection
            process_and_upload_pdf(file_path1)

        # Check if the second file is in the MongoDB collections
        # Check if the file is in the 'adobe_api_json_outputs' collection
        file2_in_adobe = adobe_api_json_outputs_db.find_one({"file_name": get_base_filename(uploaded_pdf2)})
        # Check if the file is in the 'documents_data' collection
        file2_in_documents = documents_data_db.find_one({"file_name": get_base_filename(uploaded_pdf2)})

        # Display results for the second file
        # Check if the file is in the 'adobe_api_json_outputs' collection
        if file2_in_adobe:
            # Display a success message
            st.success(f"{uploaded_pdf2.name} is present in the Adobe API outputs collection.")
        else:
            # Display a warning message
            st.warning(f"{uploaded_pdf2.name} is not present in the Adobe API outputs collection.")
            # Display an info message
            st.info(f"Processing {uploaded_pdf2.name} with Adobe API...")
            # Create an instance of the ExtractTextInfoFromPDF class
            extractor = ExtractTextInfoFromPDF(file_path2)
            # Extract the text from the PDF
            json_path = extractor.extract_text()
            # Check if the text is extracted successfully
            if json_path:
                # Upload the JSON file to the 'adobe_api_json_outputs' collection
                upload_json_file_to_mongodb(json_path, adobe_api_json_outputs_db)
                # Display a success message
                st.success(f"Processed and uploaded {uploaded_pdf2.name} to Adobe API outputs collection.")

        # Check if the file is in the 'documents_data' collection
        if file2_in_documents:
            # Display a success message
            st.success(f"{uploaded_pdf2.name} is present in the documents data collection.")
        else:
            # Process and upload the file to the 'documents_data' collection
            process_and_upload_pdf(file_path2)

        # Get the base names of the files without extensions
        new_file_name = os.path.splitext(os.path.basename(file_path1))[0]
        old_file_name = os.path.splitext(os.path.basename(file_path2))[0]
        # Construct the file pair name
        file_pair = f"{new_file_name}_{old_file_name}"
        # Check if the result is in the 'sections_data' collection
        result = sections_data_db.find_one({"file_pair": file_pair})
        # Check if the result is not found
        if not result:
            # Print a message
            print("Result not found in MongoDB")
            # Find the section-wise differences in the files
            find_section_wise_differences_in_files(file_path1, file_path2, adobe_api_json_outputs_db, documents_data_db, sections_data_db)
        else:
            # Print a message
            print("Result found in MongoDB")

        # Get the sections from the database
        sections = get_sections_from_db(file_path1, file_path2)
        # Add a placeholder to the sections list
        sections_with_placeholder = ["Select a section"] + sections

        # Check if sections are found
        if sections:
            # Create a selectbox to select a section
            user_query = st.selectbox("Select a section to view differences", sections_with_placeholder)
        else:
            # Display a warning message
            st.warning("No sections found for the uploaded documents. You can manually enter a query below.")
            # Create a text input to enter a query
            user_query = st.text_input("Enter the section of the file to view differences:")

        # Get the cleaned text for the new and old files
        new_file_cleaned_text = str(documents_data_db.find_one({"file_name": new_file_name}).get("cleaned_text", "No cleaned text found for the given file name."))
        old_file_cleaned_text = str(documents_data_db.find_one({"file_name": old_file_name}).get("cleaned_text", "No cleaned text found for the given file name."))

        # Compare documents
        # Check if the "Compare Documents" button is clicked
        if st.button("Compare Documents"):
            """
            Compares the uploaded documents and displays the differences.

            This function is called when the "Compare Documents" button is clicked. It processes the uploaded files, 
            fetches the old and new text, and then compares the documents.
            """
            # Process files
            with st.spinner("Processing and comparing documents..."):
                # Fetch the old and new text
                old_new_texts = fetch_old_and_new_text(uploaded_pdf1, uploaded_pdf2)
                # Get the selected texts
                selected_texts = [text for text in old_new_texts if text[0] == user_query]
                # Process and compare the PDFs
                result = process_and_compare_pdfs(user_query, file_pair, new_file_cleaned_text, old_file_cleaned_text, repetitions=2)
                
            # Check if the result is an error message
            if isinstance(result, str) and result.startswith("Error"):
                # Display an error message
                st.error(f"Error: {result}")
            else:
                # Display a success message
                st.success("Comparison completed successfully!")
                
                # Display the result
                st.write(result) 
                # Check if selected texts are found
                if selected_texts:
                    # Get the section heading, old text, and new text
                    section_heading, old_text, new_text = selected_texts[0]

                    # Create two columns
                    col1, col2 = st.columns(2)
                    # Display the old text in the first column
                    with col1:
                        st.text_area("Old File", old_text, height=200)
                    # Display the new text in the second column
                    with col2:
                        st.text_area("New File", new_text, height=200)
                else:
                    # Display an empty string
                    st.write("")
                
                
                # Create a download button to download the comparison report
                st.download_button(
                    label="Download Comparison Report",
                    data=result)

            # Display a success message
            st.success("Document comparison completed.")

        
else:
    # Display a warning message
    st.warning("Please upload both documents to proceed.")

# Sidebar exit button with cleanup
# Check if the "Exit Application" button is clicked
if st.sidebar.button("Exit Application"):
    """
    Exits the application and performs cleanup.

    This function is called when the "Exit Application" button is clicked. It stops the Streamlit application and 
    performs any necessary cleanup.
    """
    # Display a warning message
    st.warning("Exiting the application...")
    # Force exit the application
    os._exit(0)
