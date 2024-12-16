import streamlit as st
from pymongo import MongoClient
import os
from adobe_PDF_extract_API import ExtractTextInfoFromPDF
from app import upload_json_file_to_mongodb, find_section_wise_differences_in_files
from section_processing import process_and_upload_pdf
from document_comparison import get_sections_from_db, fetch_old_and_new_text, process_and_compare_pdfs
import shutil
from key_params import endpoint, api_key, uri

# MongoDB connection setup
client = MongoClient(uri)
capstone_db = client['capstone_db']
documents_data_db = capstone_db['documents_data']
adobe_api_json_outputs_db = capstone_db['adobe_api_json_outputs']
sections_data_db = capstone_db['sections_data']

# Clear the contents of the folder at startup
def clear_upload_dir():
    if os.path.exists(UPLOAD_DIR):
        for file_name in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, file_name)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")

# Directory to save uploaded PDF files
UPLOAD_DIR = "uploaded_pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Clear folder at startup
clear_upload_dir()

# Helper function to get the base name without extension
def get_base_filename(file):
    return os.path.splitext(file.name)[0]

# Function to save uploaded file
def save_uploaded_file(uploaded_file):
    if uploaded_file.type == "application/pdf":
        file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    else:
        st.error("Uploaded file is not a PDF.")
        return None

# Streamlit UI setup
st.title("PDF Document Comparison")

# Upload PDFs
uploaded_pdf1 = st.sidebar.file_uploader("Upload the new File")
uploaded_pdf2 = st.sidebar.file_uploader("Upload the old File")

if uploaded_pdf1 and uploaded_pdf2:
    # Save uploaded PDFs
    file_path1 = save_uploaded_file(uploaded_pdf1)
    file_path2 = save_uploaded_file(uploaded_pdf2)

    if file_path1 and file_path2:
        st.subheader("Uploaded Files")
        st.text(f"New File: {uploaded_pdf1.name}")
        st.text(f"Old File: {uploaded_pdf2.name}")

        # Check if the first file is in the MongoDB collections
        file1_in_adobe = adobe_api_json_outputs_db.find_one({"file_name": get_base_filename(uploaded_pdf1)})
        file1_in_documents = documents_data_db.find_one({"file_name": get_base_filename(uploaded_pdf1)})

        # Display results for the first file
        if file1_in_adobe:
            st.success(f"{uploaded_pdf1.name} is present in the Adobe API outputs collection.")
        else:
            st.warning(f"{uploaded_pdf1.name} is not present in the Adobe API outputs collection.")
            st.info(f"Processing {uploaded_pdf1.name} with Adobe API...")
            extractor = ExtractTextInfoFromPDF(file_path1)
            json_path = extractor.extract_text()
            if json_path:
                upload_json_file_to_mongodb(json_path, adobe_api_json_outputs_db)
                st.success(f"Processed and uploaded {uploaded_pdf1.name} to Adobe API outputs collection.")

        if file1_in_documents:
            st.success(f"{uploaded_pdf1.name} is present in the documents data collection.")
        else:
            # Process and upload to documents_data_db
            process_and_upload_pdf(file_path1)

        # Check if the second file is in the MongoDB collections
        file2_in_adobe = adobe_api_json_outputs_db.find_one({"file_name": get_base_filename(uploaded_pdf2)})
        file2_in_documents = documents_data_db.find_one({"file_name": get_base_filename(uploaded_pdf2)})

        # Display results for the second file
        if file2_in_adobe:
            st.success(f"{uploaded_pdf2.name} is present in the Adobe API outputs collection.")
        else:
            st.warning(f"{uploaded_pdf2.name} is not present in the Adobe API outputs collection.")
            st.info(f"Processing {uploaded_pdf2.name} with Adobe API...")
            extractor = ExtractTextInfoFromPDF(file_path2)
            json_path = extractor.extract_text()
            if json_path:
                upload_json_file_to_mongodb(json_path, adobe_api_json_outputs_db)
                st.success(f"Processed and uploaded {uploaded_pdf2.name} to Adobe API outputs collection.")

        if file2_in_documents:
            st.success(f"{uploaded_pdf2.name} is present in the documents data collection.")
        else:
            # Process and upload to documents_data_db
            process_and_upload_pdf(file_path2)

        new_file_name = os.path.splitext(os.path.basename(file_path1))[0]
        old_file_name = os.path.splitext(os.path.basename(file_path2))[0]
        file_pair = f"{new_file_name}_{old_file_name}"
        result = sections_data_db.find_one({"file_pair": file_pair})
        if not result:
            print("Result not found in MongoDB")
            find_section_wise_differences_in_files(file_path1, file_path2, adobe_api_json_outputs_db, documents_data_db, sections_data_db)
        else:
            print("Result found in MongoDB")

        # Call your function to get sections
        sections = get_sections_from_db(file_path1, file_path2)
        sections_with_placeholder = ["Select a section"] + sections

        if sections:
            user_query = st.selectbox("Select a section to view differences", sections_with_placeholder)
        else:
            st.warning("No sections found for the uploaded documents. You can manually enter a query below.")
            user_query = st.text_input("Enter the section of the file to view differences:")

        new_file_cleaned_text = str(documents_data_db.find_one({"file_name": new_file_name}).get("cleaned_text", "No cleaned text found for the given file name."))
        old_file_cleaned_text = str(documents_data_db.find_one({"file_name": old_file_name}).get("cleaned_text", "No cleaned text found for the given file name."))

        if st.button("Compare Documents"):

            # Process files
            with st.spinner("Processing and comparing documents..."):
                old_new_texts = fetch_old_and_new_text(uploaded_pdf1, uploaded_pdf2)
                selected_texts = [text for text in old_new_texts if text[0] == user_query]
                result = process_and_compare_pdfs(user_query, file_pair, new_file_cleaned_text, old_file_cleaned_text, repetitions=2)
                
            if isinstance(result, str) and result.startswith("Error"):
                st.error(f"Error: {result}")
            else:
                st.success("Comparison completed successfully!")
                
                st.write(result) 
                if selected_texts:
                    section_heading, old_text, new_text = selected_texts[0]

                    #st.subheader(f"Section: {section_heading}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text_area("Old File", old_text, height=200)
                    with col2:
                        st.text_area("New File", new_text, height=200)
                else:
                    st.write("")
                
                
                st.download_button(
                    label="Download Comparison Report",
                    data=result)


            st.success("Document comparison completed.")

        
else:
    st.warning("Please upload both documents to proceed.")

# Sidebar exit button with cleanup
if st.sidebar.button("Exit Application"):
    st.warning("Exiting the application...")
    os._exit(0)
