from adobe_PDF_extract_API import ExtractTextInfoFromPDF
import os
import re
import pandas as pd
import json
from pymongo.mongo_client import MongoClient
from key_params import uri
import requests
from text_comparison_openAI_api import compare_strings

def upload_json_file_to_mongodb(file_path, db_collection):
    """
    Upload a single JSON file to MongoDB collection with duplicate checking.
    
    Args:
        file_path (str): Absolute path to the JSON file to be uploaded
        db_collection: MongoDB collection object where the file will be stored
    
    Behavior:
        1. Extracts filename without extension
        2. Checks if document already exists in collection using filename
        3. If not exists:
           - Reads JSON file content
           - Creates document with structured fields:
             * file_name: Name of original file
             * version: Document version information
             * extended_metadata: Additional document metadata
             * elements: Document content elements
             * pages: Page-specific information
        4. Prints status messages for upload process
    
    Note:
        - Skips non-JSON files
        - Prevents duplicate uploads
        - Maintains original document structure in database
    """
    filename = os.path.basename(file_path)
    if filename.lower().endswith('.json'):
        # Check if the file is already in the database
        if db_collection.count_documents({'file_name': os.path.splitext(filename)[0]}) > 0:
            print(f"{filename} is already in the database")
            return
        print(f"Uploading {filename} to MongoDB")
        with open(file_path, 'r', encoding='utf-8') as file:
            json_data = json.load(file)
            db_collection.insert_one({
                'file_name': os.path.splitext(filename)[0],
                'version': json_data.get('version'),
                'extended_metadata': json_data.get('extended_metadata'),
                'elements': json_data.get('elements'),
                'pages': json_data.get('pages')
            })
        print(f"Uploaded {filename} to MongoDB")
    else:
        print(f"{filename} is not a JSON file")


def upload_json_files_to_mongodb(folder_path, db_collection):
    """
    Recursively upload all JSON files from a directory to MongoDB collection.
    
    Args:
        folder_path (str): Path to directory containing JSON files
        db_collection: MongoDB collection object for storing documents
    
    Behavior:
        1. Walks through all subdirectories recursively
        2. For each JSON file found:
           - Checks for existing document in database
           - If not exists:
             * Reads JSON content
             * Creates structured document with fields:
               - file_name: Original filename without extension
               - version: Document version
               - extended_metadata: Additional metadata
               - elements: Document content
               - pages: Page information
           - Prints upload status
    
    Note:
        - Processes only .json files
        - Implements duplicate checking
        - Maintains directory structure tracking
        - Provides progress feedback
    """
    for foldername, subfolders, filenames in os.walk(folder_path):
        for filename in filenames:
            if filename.lower().endswith('.json'):
                # Check if the file is already in the database
                if db_collection.count_documents({'file_name': os.path.splitext(filename)[0]}) > 0:
                    print(f"{filename} is already in the database")
                    continue
                print(f"Uploading {filename} to MongoDB")
                file_path = os.path.join(foldername, filename)
                with open(file_path, 'r', encoding='utf-8') as file:
                    json_data = json.load(file)
                    db_collection.insert_one({
                        'file_name': os.path.splitext(filename)[0],
                        'version': json_data.get('version'),
                        'extended_metadata': json_data.get('extended_metadata'),
                        'elements': json_data.get('elements'),
                        'pages': json_data.get('pages')
                    })
                print(f"Uploaded {filename} to MongoDB")

def get_json_path(input_pdf):
    base_name = os.path.splitext(os.path.basename(input_pdf))[0]
    return os.path.join("Adobe PDF Extract API outputs", f"{base_name}.json")


def print_document_structure(structure, level=0):
    if structure is None:
        return
    
    for key, value in structure.items():
        print("  " * level + f"{key}: {value['title']}")
        if value['subsections']:
            print_document_structure(value['subsections'], level + 1)


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
        print(f"Checking folder: {foldername}")  # Debug: See which folder is being checked
        for filename in filenames:
            if filename.lower().endswith('.pdf'):  # Check if the file is a PDF
                full_path = os.path.join(foldername, filename)
                print(f"Found PDF: {filename} in {full_path}")  # Debug: Report found PDFs
                pdf_files[filename] = full_path  # Store the file name and its full path
    return pdf_files


def get_json_for_all_pdfs(pdf_files):
    for pdf_name, pdf_path in pdf_files.items():
        print(f"Processing PDF: {pdf_name}")
        json_file_path = get_json_path(pdf_path)
        if os.path.exists(json_file_path):
            print(f"JSON file already exists at: {json_file_path}")
        else:
            # Create an instance of the ExtractTextInfoFromPDF class
            extractor = ExtractTextInfoFromPDF(pdf_path)
            # Extract the text
            json_file_path = extractor.extract_text()
            print(f"JSON file created at: {json_file_path}")

        if json_file_path:
            document_structure = ExtractTextInfoFromPDF.get_document_structure(json_file_path)
            print_document_structure(document_structure)
        
        print("--------------------------------------------\n\n")


def get_adobe_api_outputs(new_file_path, old_file_path, db_collection):
    new_file_name = os.path.basename(new_file_path)
    old_file_name = os.path.basename(old_file_path)

    # Check if the new file is in the database
    if db_collection.count_documents({'file_name': os.path.splitext(new_file_name)[0]}) == 0:
        # Create an instance of the ExtractTextInfoFromPDF class
        extractor = ExtractTextInfoFromPDF(new_file_path)
        # Extract the text
        new_file_path_json = extractor.extract_text()
        print(f"JSON file created at: {new_file_path_json}")
        # Upload JSON files to MongoDB
        upload_json_file_to_mongodb(new_file_path_json, db_collection)
        new_file_json = db_collection.find_one({'file_name': os.path.splitext(new_file_name)[0]})
    else:
        print(f"{new_file_name} is already in the database")
        # Get the JSON file from MongoDB
        new_file_json = db_collection.find_one({'file_name': os.path.splitext(new_file_name)[0]})

    # Check if the old file is in the database
    if db_collection.count_documents({'file_name': os.path.splitext(old_file_name)[0]}) == 0:
        # Create an instance of the ExtractTextInfoFromPDF class
        extractor = ExtractTextInfoFromPDF(old_file_path)
        # Extract the text
        old_file_path_json = extractor.extract_text()
        print(f"JSON file created at: {old_file_path_json}")
        # Upload JSON files to MongoDB
        upload_json_file_to_mongodb(old_file_path_json, db_collection)
        old_file_json = db_collection.find_one({'file_name': os.path.splitext(old_file_name)[0]})
    else:
        print(f"{old_file_name} is already in the database")
        # Get the JSON file from MongoDB
        old_file_json = db_collection.find_one({'file_name': os.path.splitext(old_file_name)[0]})

    return new_file_json, old_file_json

#new_file_json, old_file_json = get_adobe_api_outputs(new_file_path, old_file_path, adobe_api_json_outputs_db)


def get_table_of_contents(json_data):
    """
    Extract table of contents from document JSON data.
    
    Args:
        json_data (dict): Processed JSON data from PDF extraction
    
    Returns:
        list: Ordered list of table of contents entries
    
    Behavior:
        1. Identifies TOC elements in document structure
        2. Extracts:
           - Section numbers
           - Section titles
           - Page numbers
           - Reference information
        3. Maintains hierarchical structure
        4. Preserves formatting and spacing
    
    Note:
        - Handles multiple TOC formats
        - Preserves original document ordering
        - Includes reference markers
        - Maintains section relationships
    """
    table_of_contents_list = []
    for element in json_data['elements']:
        if "TOC" in element.get("Path"):
            if element.get("Text",None):
                table_of_contents_list.append(element['Text'])
    return table_of_contents_list

#print(get_table_of_contents(new_file_json))

def get_section_headings_and_processing(new_file_json,old_file_json, regex_pattern = r'^\d+(\.\d+)*\s+'):
    
    new_file_section_headings_list_cleaned = []
    old_file_section_headings_list_cleaned = []
    
    new_file_section_headings_list_with_path = ExtractTextInfoFromPDF.get_section_headings(new_file_json)

    for heading in new_file_section_headings_list_with_path:
        heading = re.sub(regex_pattern, '', heading["text"]).strip()
        if heading != '':
            new_file_section_headings_list_cleaned.append(heading)

    old_file_section_headings_list_with_path = ExtractTextInfoFromPDF.get_section_headings(old_file_json)

    for heading in old_file_section_headings_list_with_path:
        heading = re.sub(regex_pattern, '', heading["text"]).strip()
        if heading != '':
            old_file_section_headings_list_cleaned.append(heading)

    return new_file_section_headings_list_cleaned, new_file_section_headings_list_with_path, old_file_section_headings_list_cleaned, old_file_section_headings_list_with_path

#new_file_section_headings_list, new_file_section_headings_list_with_path, old_file_section_headings_list, old_file_section_headings_list_with_path = get_section_headings_and_processing(new_file_json, old_file_json)


def get_cleaned_text_from_mongodb(file_name, db_collection):
    data = db_collection.find_one({'file_name': file_name})
    cleaned_text = data.get('cleaned_text')

    """table_of_contents_list = get_table_of_contents(new_file_adobe_json)
    for element in table_of_contents_list:
        if element in cleaned_text:
            cleaned_text = cleaned_text.replace(element, "")
        #else:
            #print(f"Table of contents entry not found in clean text: {element}")"""
    return cleaned_text

#new_file_cleaned_text = get_cleaned_text_from_mongodb(os.path.splitext(new_file_name)[0], documents_data_db)
#old_file_cleaned_text = get_cleaned_text_from_mongodb(os.path.splitext(old_file_name)[0], documents_data_db)

#print(new_file_cleaned_text[:10000])
#print(old_file_cleaned_text[:10000])


def extract_section_texts(heading_curr_new, heading_next_new, heading_curr_old, heading_next_old, cleaned_text_new, cleaned_text_old, end_index_new, end_index_old):
    if heading_next_new != None:
        if heading_curr_new == None and heading_curr_old == None:
            heading_curr_index_new = 0
            heading_curr_index_old = 0
        else:
            heading_curr_index_new = cleaned_text_new.find(heading_curr_new, end_index_new)
            heading_curr_index_old = cleaned_text_old.find(heading_curr_old, end_index_old)
        
        heading_next_index_new = cleaned_text_new.find(heading_next_new, end_index_new + 1)
        section_text_new = cleaned_text_new[heading_curr_index_new:heading_next_index_new]
        heading_next_index_old = cleaned_text_old.find(heading_next_old, end_index_old + 1)
        section_text_old = cleaned_text_old[heading_curr_index_old:heading_next_index_old]
        return section_text_new, section_text_old, heading_next_index_new, heading_next_index_old
    else:
        #print(f"Next_heading_new {heading_next_new} is None")
        heading_curr_index_new = cleaned_text_new.find(heading_curr_new, end_index_new)
        section_text_new = cleaned_text_new[heading_curr_index_new:]
        heading_curr_index_old = cleaned_text_old.find(heading_curr_old, end_index_old)
        section_text_old = cleaned_text_old[heading_curr_index_old:]
        return section_text_new, section_text_old, len(cleaned_text_new), len(cleaned_text_old)



def get_section_texts(new_file_section_headings_list, new_file_section_headings_list_with_path, old_file_section_headings_list, old_file_section_headings_list_with_path, cleaned_text_new, cleaned_text_old):
    list_of_section_texts = []
    end_index_new = 0
    end_index_old = 0
    current_heading_index_new = 0
    next_heading_index_new = 0

    count = 0

    while new_file_section_headings_list[current_heading_index_new] not in old_file_section_headings_list:
        current_heading_index_new += 1
        if current_heading_index_new >= len(new_file_section_headings_list):

            list_of_section_texts.append(["Entire document", cleaned_text_new, cleaned_text_old, "Entire document was provided"])
            return list_of_section_texts
    
    current_heading_index_old = old_file_section_headings_list.index(new_file_section_headings_list[current_heading_index_new])
    section_text_new, section_text_old, end_index_new, end_index_old = extract_section_texts(
                None,
                new_file_section_headings_list_with_path[current_heading_index_new]["text"],
                None,
                old_file_section_headings_list_with_path[current_heading_index_old]["text"],
                cleaned_text_new,
                cleaned_text_old,
                end_index_new,
                end_index_old)
    list_of_section_texts.append(["Initial content", section_text_new, section_text_old, new_file_section_headings_list[current_heading_index_new]])

    while current_heading_index_new < len(new_file_section_headings_list) and next_heading_index_new < len(new_file_section_headings_list):
        
        if new_file_section_headings_list[current_heading_index_new] in old_file_section_headings_list:
            current_heading_index_old = old_file_section_headings_list.index(new_file_section_headings_list[current_heading_index_new])
            next_heading_index_new = current_heading_index_new + 1
            reached_end_of_old_file = False
            while (next_heading_index_new < len(new_file_section_headings_list)) and (new_file_section_headings_list[next_heading_index_new] not in old_file_section_headings_list):
                next_heading_index_new += 1

                if next_heading_index_new >= len(new_file_section_headings_list):
                    reached_end_of_old_file = True

            if reached_end_of_old_file:
            
                break
            next_heading_index_old = old_file_section_headings_list.index(new_file_section_headings_list[next_heading_index_new])
            section_text_new, section_text_old, end_index_new, end_index_old = extract_section_texts(
                new_file_section_headings_list_with_path[current_heading_index_new]["text"],
                new_file_section_headings_list_with_path[next_heading_index_new]["text"],
                old_file_section_headings_list_with_path[current_heading_index_old]["text"],
                old_file_section_headings_list_with_path[next_heading_index_old]["text"],
                cleaned_text_new,
                cleaned_text_old,
                end_index_new,
                end_index_old)
            list_of_section_texts.append([new_file_section_headings_list[current_heading_index_new], section_text_new, section_text_old, new_file_section_headings_list[next_heading_index_new]])
            current_heading_index_new = next_heading_index_new
            next_heading_index_new += 1
            count += 1
        else:
            current_heading_index_new += 1

    if current_heading_index_new < len(new_file_section_headings_list) and next_heading_index_new >= len(new_file_section_headings_list):
        if new_file_section_headings_list[current_heading_index_new] in old_file_section_headings_list:
            current_heading_index_old = old_file_section_headings_list.index(new_file_section_headings_list[current_heading_index_new])
            next_heading_index_old = len(old_file_section_headings_list) - 1
            section_text_new, section_text_old, end_index_new, end_index_old = extract_section_texts(
                new_file_section_headings_list_with_path[current_heading_index_new]["text"],
                None,
                old_file_section_headings_list_with_path[current_heading_index_old]["text"],
                None,
                cleaned_text_new,
                cleaned_text_old,
                end_index_new,
                end_index_old)
            list_of_section_texts.append([new_file_section_headings_list[current_heading_index_new], section_text_new, section_text_old, "Last section: No section after this."])
            count += 1

    print(f"Total matching headings: {count}, Total headings in new file: {len(new_file_section_headings_list)}")
    print(f"Total section heading pairs: {len(list_of_section_texts)}")

    return list_of_section_texts

#list_of_section_texts = get_section_texts(new_file_section_headings_list, new_file_section_headings_list_with_path, old_file_section_headings_list, old_file_section_headings_list_with_path, new_file_cleaned_text, old_file_cleaned_text)



def reconstruct_document_exclude_toc(json_file_path):
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

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

# Usage
#json_path = r"D:\Google Drive University\Nexteer AI Docs Capstone Project\Ideas\Adobe PDF Extract API outputs\Ford-IATF-CSR-for-IATF-16949-1May2017.json"
#document_text = reconstruct_document_exclude_toc(json_path)

# Output the text or use it further
#print(document_text)  # Print the document text



sample_response = """
| Section   | Change                                                                                         |
|-----------|------------------------------------------------------------------------------------------------|
| 10/01/16  | New release. Timing for new requirements presented below.                                      |
| 03/31/17  | Certification requirement for Accessory parts identified by Mopar as safety or installed at Mopar Custom Shops. |
| 04/12/18  |                                                                                                 |
| Table Of Contents | Updated: "SUMMARY OF IATF 16949 SECTIONS WITH CUSTOMER-SPECIFIC CONTENT" simplified.   |
| 1.1       | Added note referencing CSR for FCA Italy SpA                                                   |
| 1.2       | - Implementation timing note (3/31/17 due date) in Table 1 for MOPAR certification upgrade removed |
|           | - Moved Bulk Metallic Commodity Exemptions tables to Appendix A                                |
| 2.A       | - Reference to CQI-16: ISO/TS 16949:2009 Guidance Manual removed                               |
|           | - References to the following documents added:                                                 |
|           | -- CQI-27: Special Process: Casting System Assessment                                          |
|           | -- IATF 16949:2016 Sanctioned Interpretations                                                  |
|           | -- QR.00001 Global Product Assurance Testing                                                   |
|           | -- SQ.00001 Additional Quality Requirements (AQR)                                              |
|           | -- SQ.00007 Master Process Failure Mode and Effects Analysis (MPFMEA)                          |
|           | -- SQ.00008 Product Demonstration Run (PDR)                                                    |
|           | -- SQ.00010 Advanced Quality Planning (AQP) and Product Part Approval Process (PPAP)           |
|           | -- SQ.00012 Forever Requirements                                                               |
|           | -- SQN-A0469 Supplier Incident Management – NATFA                                              |
|           | -- SQN-A0489 Third Party Containment and Problem Resolution                                    |
|           | -- SQN-A0490 Launch Risk Mitigation                                                            |
| 2.B       | Reference to IATF 16949 Sanctioned Interpretations added                                       |
| 3.1       | - Revised definitions for:                                                                     |
|           | -- Consigned Part                                                                              |
|           | -- Directed Part                                                                               |
|           | -- External Balanced Scorecard (now Global External Balanced Scorecard)                        |
|           | -- Process Audit                                                                               |
|           | - Added definitions for:                                                                       |
|           | -- Additional Quality Requirements (AQR)                                                       |
|           | -- Advance Quality Planning (AQP)                                                              |
|           | -- Launch Risk Mitigation (LRM)                                                                |
|           | -- Master Process Failure Mode and Effects Analysis (MPFMEA)                                   |
| 3.2       | - No changes found in this section between the two versions of the document.                   |
| 4.1       | - No changes found in this section between the two versions of the document.                   |
| 4.2       | - No changes found in this section between the two versions of the document.                   |
| 4.3       | - No changes found in this section between the two versions of the document.                   |
| 4.4       | - This section is newly added in this version of the document.                                 |
| 5.3.1     | Requirement for SIC maintenance added (existing requirement; 30 days grace granted to ensure implementation) |
| 6         | - No changes found in this section between the two versions of the document.                   |
| 7.2.2     | - Requirement for CQR (Common Quality Reporting) removed (note – access to application is restricted to FCA US personnel) |
|           | - GEBCS substituted for EBSC; beStandard and SIC (5.3.1) added                                 |
| 7.5.3.2.1 | Clarified scope of "organization-controlled documents"                                         |
| 8.3.2.1   | Product development process requirement revised (PPR/PA removed, AQP/PPAP added). (As noted, change required with start of next product development program – 30 days grace granted for organization acquisition and review of process document). |
| 8.2.3.1   | References to AQR and MPFMEA added (existing requirements relocated to new standard – 30 days grace granted for organization acquisition and review of process document). |
| 8.3.3.2   | References to AQR and MPFMEA added (existing requirements relocated to new standard – 30 days grace granted for organization acquisition and review of process document). |
| 8.4.2.3   | Added "risk-based thinking" as a criterion for establishing extent and timing of supplier QMS development |
| 8.4.2.4.1 | Clarified requirement for supplier self-certification process                                  |
| 8.5.6.1   | Existing requirements relocated to new standard. (30 days grace granted for organization acquisition and review) |
| 8.6.2     | Clarified scope of layout inspection requirements                                              |
| 8.7.1.1   | Documenting existing requirement (PPA Manual, section 5c; PPAP Tool 3.5)                       |
| 8.7.1.2   | Existing requirements for control of nonconforming material relocated to new standard. (30 days grace granted for organization acquisition and review of process document). |
| 8.7.1.3   | Documented existing requirement                                                                |
| 8.7.1.4   | Documenting existing requirement (PPA Manual, section 5c; PPAP Tool 3.5)                       |
| 9.1.2     | Updated to support release of Global External Balanced Scorecard                               |
| 9.1.2.1   | Revised "OEM performance complaint" and "Quality New Business Hold" to more closely align with the Rules and current practice. |
| 9.2.2.3   | Self-assessment submission requirements for CQI-9 added under "Special Process Assessments – Additional Considerations" (note – this is a current requirement) |
| 9.2.2.4   | Existing requirements relocated to new standard. (30 days grace granted for organization acquisition and review of process document). |
| 9.3.3.1   | Simplified Automotive Warranty Management requirement                                          |
| Appendix A| New (requirements moved from 1.2)                                                              |
| Appendix B| New note – added in support revision of 9.2.2.3                                                |

"""


sample_response_edge_cases = """
| Section   | Change                                                                                         |
|-----------|------------------------------------------------------------------------------------------------|
| 1         | - No changes                                                                                   |
| 2         | - No changes                                                                                   |
| 3.1       | - No changes                                                                                   |
| 3.2       | - Newly added section                                                                          |
| 4.1       | - No changes                                                                                   |
| 4.2       | - Newly added section                                                                          |
| 4.3       | - No changes                                                                                   |
| 4.4       | - Newly added section                                                                          |
| 5.1       | - No changes                                                                                   |
| 5.2       | - Section removed                                                                              |
"""


# Function to make an API call to GPT-4o for finding differences between two texts
def compare_documents_with_gpt4o(text_new, text_old, endpoint, api_key):
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }

    system_prompt = f"""You are an expert in document comparison. Your task is to identify the differences between newer and older versions of a document.
    You need to compare the two versions on a very granular level, which means you have to compare differences in each section and sub-section and then list the changes explicitly.
    Each sub-section should be listed along with the changes in that sub-section.
    If there are changes in specific section or sub-section, please provide a detailed summary of the changes for each section or the sub-section along with the changes in each section or the sub-section.
    If some of the sections are completely missing or newly added or there are no changes, you need to also make a note of it in the output. The example of this output is given below: \n\n{sample_response_edge_cases}
    An example of how the output should look like is given below:\n\n{sample_response}"""

    # Prepare the payload for the API call
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Compare the following two document versions and provide a detailed summary of the changes.\n\nNewer Version:\n{text_new}\n\nOlder Version:\n{text_old}"}
        ],
        "max_tokens": 16384,
        "temperature": 1,
        "top_p": 1,
        "n": 1,
    }

    response = requests.post(endpoint, headers=headers, json=payload)
    
    if response.status_code == 200:
        completion = response.json()
        return completion['choices'][0]['message']['content']
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None
    


# Function to make an API call to GPT-4o for finding differences between two texts
def compare_documents_with_gpt4o_loop(text_new, text_old, differences, iteration, endpoint, api_key):
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }

    system_prompt = f"""You are an expert in document comparison. Your task is to identify the differences between newer and older versions of a document. 
    You need to compare the two versions on a very granular level, which means you have to compare differences in each section and sub-section and then list the changes explicitly. 
    Each sub-section should be listed along with the changes in that sub-section. 
    If there are changes in specific section or sub-section, please provide a detailed summary of the changes for each section or the sub-section along with the changes in each section or the sub-section. 
    If some of the sections are completely missing or newly added or there are no changes, you need to also make a note of it in the output. The example of this output is given below: \n\n{sample_response_edge_cases}
    An example of how the output should look like is given below:\n\n{sample_response}"""

    chain_prompt = f""" You are following up on the previous response of the LLM. The previous response was a preliminary analysis of the differences between the two document versions. 
    The LLM has provided a summary of the changes in the document. 
    Your task is to review the summary provided by the LLM and provide a more detailed summary of the changes in the document.
    You must also check if the previous response has missed any important changes or some sections and sub-sections and provide a detailed summary of those changes along with the changes provided by the previous LLM.
    The differences provided by the previous LLM are as follows:\n\n{differences}
    The LLM was prompted with the following system prompt:\n\n{system_prompt}
    You also need to follow the same system prompt and build up on the previous response.
    """

    temp = 1 - 0.2 * iteration
    # Prepare the payload for the API call
    payload = {
        "messages": [
            {"role": "system", "content": chain_prompt},
            {"role": "user", "content": f"Compare the following two document versions and provide a detailed summary of the changes.\n\nNewer Version:\n{text_new}\n\nOlder Version:\n{text_old}"}
        ],
        "max_tokens": 16384,
        "temperature": temp,
        "top_p": 1,
        "n": 1,
    }

    response = requests.post(endpoint, headers=headers, json=payload)
    
    if response.status_code == 200:
        completion = response.json()
        return completion['choices'][0]['message']['content']
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None
    


def get_differences_between_sections(list_of_section_texts):
    for section_text in list_of_section_texts:
        new_text = section_text[1]
        old_text = section_text[2]

        # Find the differences between the two texts
        result = compare_strings(new_text, old_text)
        result_string = ""
        # Display the results
        if result:
            print("Section heading: ", section_text[0])
            print("Differences:")
            result_string = result_string + "Differences:\n"
            for diff in result.differences:
                print(f"Type: {diff.type}, Description: {diff.description}")
                result_string = result_string + f"Type: {diff.type}, Description: {diff.description}\n"
                if diff.section:
                    result_string = result_string + f"Section: {diff.section}\n"
                    print(f"Section: {diff.section}")
                if diff.new_file_text or diff.old_file_text:
                    result_string = result_string + f"New content: {diff.new_file_text}\n"
                    result_string = result_string + f"Old content: {diff.old_file_text}\n"
                    print(f"New content: {diff.new_file_text}")
                    print(f"Old content: {diff.old_file_text}")
                if diff.content:
                    result_string = result_string + f"Content: {diff.content}\n"
                    print(f"Content: {diff.content}")
                if diff.position is not None:
                    result_string = result_string + f"Position: {diff.position}\n"
                    print(f"Position: {diff.position}")

            result_string = result_string + "\n\nSummary:"
            result_string = result_string + result.summary
            result_string = result_string + "\n\n-----------------------------------------------\n\n"
            print("\nSummary:")
            print(result.summary)

            print("\n\n-----------------------------------------------\n\n")
        else:
            print("Error in comparing the two texts")

        section_text.append(result_string)

    return list_of_section_texts


def upload_compared_sections_to_mongodb(file_pair, list_of_section_texts_with_results, db_collection):
    """
    Uploads compared sections to a MongoDB collection.

    Args:
        file_pair (tuple): A tuple containing two strings representing the file pair being compared.
        list_of_section_texts_with_results (list): A list of tuples containing:
            - Section heading
            - New text
            - Old text
            - Next section heading
            - Comparison results
        db_collection: The MongoDB collection where data will be stored.

    Returns:
        None
    """
    # Convert file_pair tuple to a string for MongoDB compatibility
    file_pair_str = f"{file_pair[0]}_{file_pair[1]}"  # Create a unique string identifier

    # Prepare the sections data for insertion
    sections = []
    for section in list_of_section_texts_with_results:
        section_data = {
            'section_heading': section[0],
            'new_text': section[1],
            'old_text': section[2],
            'next_section_heading': section[3],
            'comparison_results': section[4]
        }
        sections.append(section_data)

    # Insert or update the entire document for the file pair
    db_collection.update_one(
        {'file_pair': file_pair_str},
        {
            '$set': {
                'file_pair': file_pair_str,
                'sections': sections
            }
        },
        upsert=True
    )
    print(f"Data for file pair {file_pair} successfully uploaded to MongoDB.")

def find_section_wise_differences_all_pairs(pairs_list, adobe_api_json_outputs_db, documents_data_db, sections_data):
    for pair in pairs_list:
        new_file_name = os.path.splitext(pair[0])[0]
        old_file_name = os.path.splitext(pair[1])[0]
        print(pair)

        # Assuming get_file_paths_from_pair is a function that retrieves file paths
        new_file_path, old_file_path = get_file_paths_from_pair(pair)

        print(new_file_name)
        print(old_file_name)

        # Extract JSON data
        new_file_json, old_file_json = get_adobe_api_outputs(new_file_path, old_file_path, adobe_api_json_outputs_db)

        # Get section headings
        new_file_section_headings_list, new_file_section_headings_list_with_path, old_file_section_headings_list, old_file_section_headings_list_with_path = get_section_headings_and_processing(new_file_json, old_file_json)

        # Fetch cleaned text from MongoDB
        new_file_cleaned_text = get_cleaned_text_from_mongodb(new_file_name, documents_data_db)
        old_file_cleaned_text = get_cleaned_text_from_mongodb(old_file_name, documents_data_db)

        # Extract section texts
        list_of_section_texts = get_section_texts(new_file_section_headings_list, new_file_section_headings_list_with_path, old_file_section_headings_list, old_file_section_headings_list_with_path, new_file_cleaned_text, old_file_cleaned_text)

        print(list_of_section_texts)

        # Compare sections
        list_of_section_texts_with_results = get_differences_between_sections(list_of_section_texts)

        # Store results in MongoDB
        upload_compared_sections_to_mongodb((new_file_name, old_file_name), list_of_section_texts_with_results, sections_data)


def get_mongodb_connection(uri):
    """
    Establishes a connection to MongoDB and returns the client and database object.
    """
    client = MongoClient(uri)
    try:
        client.admin.command('ping')
        print("Successfully connected to MongoDB!")
    except Exception as e:
        raise ConnectionError(f"Error connecting to MongoDB: {e}")
    return client, client['capstone_db']


def get_file_pairs_from_excel(file_path):
    """
    Reads an Excel file to extract file pairs for comparison.

    Args:
        file_path (str): Path to the Excel file containing document version information.

    Returns:
        list: A list of tuples representing file pairs.
    """
    document_list_df = pd.read_excel(file_path)
    pairs_list = []

    for _, row in document_list_df.iterrows():
        if pd.isna(row['old_version_1']):
            pairs_list.append((row['new_version'], row['old_version']))
        else:
            pairs_list.append((row['new_version'], row['old_version']))
            pairs_list.append((row['new_version'], row['old_version_1']))
            pairs_list.append((row['old_version_1'], row['old_version']))

    return pairs_list


def check_and_upload_json(file_path, db_collection):
    """
    Checks if a JSON file is in the MongoDB collection and uploads it if not.

    Args:
        file_path (str): Path to the JSON file.
        db_collection: MongoDB collection to store the data.
    """
    filename = os.path.basename(file_path)
    if db_collection.count_documents({'file_name': os.path.splitext(filename)[0]}) > 0:
        print(f"{filename} is already in the database.")
        return
    with open(file_path, 'r', encoding='utf-8') as file:
        json_data = json.load(file)
        db_collection.insert_one({
            'file_name': os.path.splitext(filename)[0],
            'version': json_data.get('version'),
            'extended_metadata': json_data.get('extended_metadata'),
            'elements': json_data.get('elements'),
            'pages': json_data.get('pages')
        })
    print(f"Uploaded {filename} to MongoDB.")


def get_adobe_api_outputs(new_file_path, old_file_path, db_collection):
    """
    Retrieves Adobe API outputs for given file paths. If outputs are not found in MongoDB,
    they are extracted and uploaded.

    Returns:
        tuple: JSON data for new and old files.
    """
    def extract_or_fetch(file_path):
        file_name = os.path.basename(file_path)
        base_name = os.path.splitext(file_name)[0]

        if db_collection.count_documents({'file_name': base_name}) == 0:
            extractor = ExtractTextInfoFromPDF(file_path)
            json_file_path = extractor.extract_text()
            check_and_upload_json(json_file_path, db_collection)
        return db_collection.find_one({'file_name': base_name})

    return extract_or_fetch(new_file_path), extract_or_fetch(old_file_path)


def get_section_headings(json_data, regex_pattern=r'^\d+(\.\d+)*\s+'):
    """
    Extracts and cleans section headings from JSON data.
    """
    section_headings = ExtractTextInfoFromPDF.get_section_headings(json_data)
    return [re.sub(regex_pattern, '', heading["text"]).strip() for heading in section_headings if heading["text"].strip()]


def get_cleaned_text(file_name, db_collection):
    """
    Fetches cleaned text for a document from MongoDB.
    """
    data = db_collection.find_one({'file_name': file_name})
    return data.get('cleaned_text') if data else None


def compare_section_texts(list_of_section_texts, endpoint, api_key):
    """
    Compares texts for each section using GPT-4 and appends results to the section data.
    """
    for section_text in list_of_section_texts:
        new_text = section_text[1]
        old_text = section_text[2]
        section_text.append(compare_strings(new_text, old_text, endpoint, api_key))
    return list_of_section_texts


def upload_comparison_results(file_pair, section_texts_with_results, db_collection):
    """
    Uploads the comparison results to MongoDB.
    """
    file_pair_str = f"{file_pair[0]}__{file_pair[1]}"
    sections = [
        {
            'section_heading': section[0],
            'new_text': section[1],
            'old_text': section[2],
            'next_section_heading': section[3],
            'comparison_results': section[4]
        } for section in section_texts_with_results
    ]
    db_collection.update_one(
        {'file_pair': file_pair_str},
        {'$set': {'file_pair': file_pair_str, 'sections': sections}},
        upsert=True
    )
    print(f"Uploaded comparison results for {file_pair} to MongoDB.")


def find_all_pdfs(root_folder):
    """
    Finds all PDF files in the given root folder and its subfolders.
    """
    pdf_files = []
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if file.endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    return pdf_files

def find_section_wise_differences_in_files(new_file_path, old_file_path, adobe_api_json_outputs_db, documents_data_db, sections_data):
    new_file_name = os.path.splitext(os.path.basename(new_file_path))[0]
    old_file_name = os.path.splitext(os.path.basename(old_file_path))[0]

    #print(new_file_name)
    #print(old_file_name)
    new_file_json, old_file_json = get_adobe_api_outputs(new_file_path, old_file_path, adobe_api_json_outputs_db)

    new_file_section_headings_list, new_file_section_headings_list_with_path, old_file_section_headings_list, old_file_section_headings_list_with_path = get_section_headings_and_processing(new_file_json, old_file_json)

    print(new_file_name)

    new_file_cleaned_text = get_cleaned_text_from_mongodb(new_file_name, documents_data_db)
    print(old_file_name)
    old_file_cleaned_text = get_cleaned_text_from_mongodb(old_file_name, documents_data_db)

    list_of_section_texts = get_section_texts(new_file_section_headings_list, new_file_section_headings_list_with_path, old_file_section_headings_list, old_file_section_headings_list_with_path, new_file_cleaned_text, old_file_cleaned_text)

    print(list_of_section_texts)

    list_of_section_texts_with_results = get_differences_between_sections(list_of_section_texts)

    file_pair = (new_file_name, old_file_name)

    upload_compared_sections_to_mongodb(file_pair, list_of_section_texts_with_results, sections_data)

    return sections_data

def main():
    # Establish MongoDB connection
    client, capstone_db = get_mongodb_connection(uri)
    adobe_api_json_outputs_db = capstone_db['adobe_api_json_outputs']

    # Define root folder and find all PDFs
    root_folder = r"D:\Google Drive University\Nexteer AI Docs Capstone Project\Resources from client"
    pdf_files = find_all_pdfs(root_folder)

    # Process PDFs and upload JSON to MongoDB
    for pdf_file in pdf_files:
        json_file_path = ExtractTextInfoFromPDF(pdf_file).extract_text()
        check_and_upload_json(json_file_path, adobe_api_json_outputs_db)

    # Example usage: Compare sections of two documents
    file_pairs = get_file_pairs_from_excel("path_to_excel.xlsx")
    for new_file, old_file in file_pairs:
        new_json, old_json = get_adobe_api_outputs(new_file, old_file, adobe_api_json_outputs_db)
        new_headings = get_section_headings(new_json)
        old_headings = get_section_headings(old_json)
        section_texts = [(heading, get_cleaned_text(heading, adobe_api_json_outputs_db)) for heading in new_headings]
        section_texts_with_results = compare_section_texts(section_texts, "api_endpoint", "api_key")
        upload_comparison_results((new_file, old_file), section_texts_with_results, adobe_api_json_outputs_db)

if __name__ == "__main__":
    main()
