import os
import fitz  # PyMuPDF for text extraction from PDF
from collections import defaultdict
from tqdm import tqdm
import re
import requests
import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
from key_params import endpoint , api_key, uri
import json
from adobe_PDF_extract_API import ExtractTextInfoFromPDF
import re
from text_comparison_openAI_api import compare_strings


# Function to find all PDF files in a directory (including nested directories)

def find_matching_jsons(json_folder, pdf_file1, pdf_file2):
    """
    Find and load JSON files corresponding to the uploaded PDF files.

    Args:
        json_folder (str): Path to the folder where JSON files are stored.
        pdf_file1 (str): Uploaded PDF file name.
        pdf_file2 (str): Uploaded PDF file name.

    Returns:
        tuple: JSON content for the two PDF files.
    """
    # Extract the base names (without extensions) to find corresponding JSONs
    base_name1 = os.path.splitext(pdf_file1)[0]
    base_name2 = os.path.splitext(pdf_file2)[0]

    # Construct JSON file paths
    json_file1_path = os.path.join(json_folder, f"{base_name1}.json")
    json_file2_path = os.path.join(json_folder, f"{base_name2}.json")

    print(base_name1)
    print(json_file1_path)
    # Initialize variables for JSON content
    json1, json2 = None, None

    # Check and load JSON for the first PDF
    if os.path.exists(json_file1_path):
        print(f"Found JSON for {pdf_file1}: {json_file1_path}")
        with open(json_file1_path, 'r', encoding='utf-8') as f:
            json1 = json.load(f)
    else:
        raise FileNotFoundError(f"No matching JSON file found for {pdf_file1}")

    # Check and load JSON for the second PDF
    if os.path.exists(json_file2_path):
        print(f"Found JSON for {pdf_file2}: {json_file2_path}")
        with open(json_file2_path, 'r', encoding='utf-8') as f:
            json2 = json.load(f)
    else:
        raise FileNotFoundError(f"No matching JSON file found for {pdf_file2}")

    return json1, json2

    

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

# Create a new client and connect to the server
client = MongoClient(uri)
capstone_db = client['capstone_db']
adobe_api_json_outputs_db = capstone_db['adobe_api_json_outputs']
#db_collection =  documents_data_db
documents_data_db = capstone_db['documents_data']
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)



def get_cleaned_text_from_mongodb(file_name, file_headings_list, new_file_adobe_json, db_collection):
    data = db_collection.find_one({'file_name': file_name})
    cleaned_text = data.get('cleaned_text')


    """table_of_contents_list = get_table_of_contents(new_file_adobe_json)
    for element in table_of_contents_list:
        if element in cleaned_text:
            cleaned_text = cleaned_text.replace(element, "")
        #else:
            #print(f"Table of contents entry not found in clean text: {element}")"""
    return cleaned_text



def extract_section_texts(heading_curr_new, heading_next_new, heading_curr_old, heading_next_old, cleaned_text_new, cleaned_text_old, end_index_new, end_index_old):
    if heading_next_new != None:
        if heading_curr_new == None:
            heading_curr_index_new = 0
            heading_curr_index_old = 0
        heading_curr_index_new = cleaned_text_new.find(heading_curr_new, end_index_new)
        heading_next_index_new = cleaned_text_new.find(heading_next_new, end_index_new + 1)
        section_text_new = cleaned_text_new[heading_curr_index_new:heading_next_index_new]
        heading_curr_index_old = cleaned_text_old.find(heading_curr_old, end_index_old)
        heading_next_index_old = cleaned_text_old.find(heading_next_old, end_index_old + 1)
        section_text_old = cleaned_text_old[heading_curr_index_old:heading_next_index_old]
        return section_text_new, section_text_old, heading_next_index_new, heading_next_index_old
    else:
        print(f"Next_heading_new {heading_next_new} is None")
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


    while current_heading_index_new < len(new_file_section_headings_list) and next_heading_index_new < len(new_file_section_headings_list):
        #if len(list_of_section_texts) == 0:
        if new_file_section_headings_list[current_heading_index_new] in old_file_section_headings_list:
            #print(f"Current heading in new file: {new_file_section_headings_list[current_heading_index_new]} | Current heading in old file: {old_file_section_headings_list[old_file_section_headings_list.index(new_file_section_headings_list[current_heading_index_new])]}")
            current_heading_index_old = old_file_section_headings_list.index(new_file_section_headings_list[current_heading_index_new])
            print(f"Current heading in new file: {new_file_section_headings_list_with_path[current_heading_index_new]['text']} | Current heading in old file: {old_file_section_headings_list_with_path[current_heading_index_old]['text']}")
            next_heading_index_new = current_heading_index_new + 1
            while new_file_section_headings_list[next_heading_index_new] not in old_file_section_headings_list:
                print("counter_increased")
                print("Heading that is not in old file: ", new_file_section_headings_list[next_heading_index_new])
                next_heading_index_new += 1
            next_heading_index_old = old_file_section_headings_list.index(new_file_section_headings_list[next_heading_index_new])
            print(f"Next heading in new file: {new_file_section_headings_list_with_path[next_heading_index_new]['text']} | Next heading in old file: {old_file_section_headings_list_with_path[next_heading_index_old]['text']}")
            section_text_new, section_text_old, end_index_new, end_index_old = extract_section_texts(
                new_file_section_headings_list_with_path[current_heading_index_new]["text"],
                new_file_section_headings_list_with_path[next_heading_index_new]["text"],
                old_file_section_headings_list_with_path[current_heading_index_old]["text"],
                old_file_section_headings_list_with_path[next_heading_index_old]["text"],
                cleaned_text_new,
                cleaned_text_old,
                end_index_new,
                end_index_old)
            list_of_section_texts.append((section_text_new, section_text_old))
            current_heading_index_new = next_heading_index_new
            next_heading_index_new += 1
            count += 1


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
            list_of_section_texts.append((section_text_new, section_text_old))
            count += 1


    print(f"Total matching headings: {count}, Total headings in new file: {len(new_file_section_headings_list)}")
    print(f"Total section heading pairs: {len(list_of_section_texts)}")


    return list_of_section_texts



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


def search_query_processing(query_text , new_text, old_text):

    match_new = re.search(query_text, new_text)
    match_old = re.search(query_text, old_text)

    if match_new is not None and match_old is not None:
        # Get the start indices
        start_index_new = match_new.start()
        start_index_old = match_old.start()
    # Get the start indices 
    value_at_index = int(new_text[start_index_new - 2])  # Convert to integer
    search_value = str(value_at_index + 1)+ " "  # Add 1 and convert back to string for search
    
# Search for the new value in the text
    match_next_new = re.search(search_value, new_text)
    end_index_new = match_next_new.start()
    #match_next_new = re.search(new_text[start_index_new - 2]+1, new_text)    
    print(start_index_new)
    print(start_index_old)
    print(new_text[start_index_new - 2])
    print(end_index_new)
    print(new_text[end_index_new])
    return start_index_new,start_index_old


def fetch_comparison_results(file_pair, section_heading, db_name="capstone_db", collection_name="sections_data"):
    try:
        # Connect to MongoDB
        client = MongoClient(uri)  # Update with your MongoDB connection string
        db = client[db_name]
        collection = db[collection_name]

        # Query the database for the file pair and section heading
        result = collection.find_one(
            {
                "file_pair": file_pair,
                "sections.section_heading": section_heading
            },
            {
                "sections.$": 1  # Fetch only the matched section
            }
        )

        if result and "sections" in result:
            section = result["sections"][0]  # Extract the first matched section
            formatted_result = (
                f"**Section Heading:**\n{section['section_heading']}\n\n"
                f"**Comparison Results:**\n\n{section['comparison_results']}"
            )
            return formatted_result
        else:
            return None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def fetch_results(file_pair, db_name="capstone_db", collection_name="api_data"):
    try:
        # Connect to MongoDB
        client = MongoClient(uri)  # Update with your MongoDB connection string
        db = client[db_name]
        collection = db[collection_name]

        # Query the database for the file pair and section heading
        result = collection.find_one(
            {
                "file_pair": file_pair
            }
        )

        if result and "file_pair" in result:
            section = result["file_pair"][0]  # Extract the first matched section
            formatted_result = (
                #f"**Section Heading:**\n{section['section_heading']}\n\n"
                f"**Comparison Results:**\n{section['comparison_results']}"
            )
            return formatted_result
        else:
            return None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None







# def compare_section_texts(list_of_section_texts, endpoint, api_key):
#     """
#     Compares texts for each section using GPT-4 and appends results to the section data.
#     """
#     for section_text in list_of_section_texts:
#         new_text = section_text[1]
#         old_text = section_text[2]
#         section_text.append(compare_strings(new_text, old_text, endpoint, api_key))
#     return list_of_section_texts



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

def compare_documents_with_gpt4o(text_new, text_old):
    """Compare two document texts using GPT-4o"""
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

    # Define the system prompt for the initial comparison
    initial_prompt = """
    You are an AI assistant designed to compare text sections of new file and old file. Your task is to:
    1. Identify the differences between the text sections of the new file and old file.
    2. Provide a list of differences with the type of difference (e.g., added, removed, modified).
    3. Include a comprehensive and very detailed summary of the differences as a simple string.

    Return the results in JSON format, but strict adherence to a schema is not required at this stage.
    """

    # Define the system prompt for schema validation
    validation_prompt = """
    You are an AI assistant tasked with formatting JSON output. Given the following JSON data, reformat it to strictly adhere to this schema:

    Schema:
    {
        "type": "object",
        "properties": {
            "differences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "description": {"type": ["string", "null"]},
                        "section": {"type": ["string", "null"]},
                        "new_file_text": {"type": ["string", "null"]},
                        "old_file_text": {"type": ["string", "null"]},
                        "content": {"type": ["string", "null"]},
                        "position": {"type": ["integer", "null"]}
                    },
                    "required": ["type"]
                }
            },
            "summary": {"type": "string"}
        },
        "required": ["differences", "summary"]
    }

    Reformat this JSON to match the schema strictly.
    """

    # Prepare the payload for the API call
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Compare the following two document versions and provide a detailed summary of the changes.\n\nNewer Version:\n{text_new}\n\nOlder Version:\n{text_old}"}
        ],
        "max_tokens": 4096,
        "temperature": 1,
        "top_p": 1,
        "n": 1,
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        completion = response.json()
        return completion['choices'][0]['message']['content']
    except Exception as e:
        return f"Error in document comparison: {str(e)}"

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
        "max_tokens": 4096,
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




def save_to_mongodb(uri, db_name, collection_name, document):
    """Save document to MongoDB"""
    try:
        client = MongoClient(uri)
        db = client[db_name]
        collection = db[collection_name]
        result = collection.insert_one(document)
        return str(result.inserted_id)
    except Exception as e:
        return f"Error saving to MongoDB: {str(e)}"
    
def get_sections_from_db(file_path_new, file_path_old, db_name="capstone_db", collection_name="sections_data"): 
    new_file_name = os.path.splitext(os.path.basename(file_path_new))[0]
    old_file_name = os.path.splitext(os.path.basename(file_path_old))[0]
    file_pair = f"{new_file_name}_{old_file_name}"
    print("searching for file pair: ", file_pair)
    try:
        # Connect to MongoDB
        client = MongoClient(uri)  # Update with your MongoDB connection string
        db = client[db_name]
        collection = db[collection_name]

        # Query the database for the file pair
        result = collection.find_one({"file_pair": file_pair})

        if result and "sections" in result:
            # Extract and return the section headings
            sections = [section.get("section_heading") for section in result["sections"]]
            return sections
        else:
            return []

    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def fetch_old_and_new_text(file_path_new, file_path_old, db_name="capstone_db", collection_name="sections_data"):
    file_name_new = os.path.splitext(file_path_new.name)[0]
    print(file_name_new)
    file_name_old = os.path.splitext(file_path_old.name)[0]
    print(file_name_old) 
    file_pair = f"{file_name_new}_{file_name_old}"
    try:
        # Connect to MongoDB
        client = MongoClient(uri) 
        db = client[db_name]
        collection = db[collection_name]

        # Query the database for the file pair
        result = collection.find_one({"file_pair": file_pair})

        if result and "sections" in result:
            extracted_texts = []
            for section in result["sections"]:
                section_heading = section.get("section_heading", "Unknown Section")
                old_text = section.get("old_text", "No Old Text Found")
                new_text = section.get("new_text", "No New Text Found")
                extracted_texts.append((section_heading, old_text, new_text))
            return extracted_texts
        else:
            return []

    except Exception as e:
        print(f"An error occurred while fetching texts: {e}")
        return []

# def find_section_wise_differences_all_pairs(pairs_list, adobe_api_json_outputs_db, documents_data_db, sections_data):
#     for pair in pairs_list:
#         new_file_name = os.path.splitext(pair[0])[0]
#         old_file_name = os.path.splitext(pair[1])[0]
#         print(pair)

#         new_file_path, old_file_path= get_file_paths_from_pair(pair, root_folder)

#         print(new_file_name)
#         print(old_file_name)


#         new_file_json, old_file_json = get_adobe_api_outputs(new_file_path, old_file_path, adobe_api_json_outputs_db)

#         new_file_section_headings_list, new_file_section_headings_list_with_path, old_file_section_headings_list, old_file_section_headings_list_with_path = get_section_headings_and_processing(new_file_json, old_file_json)

#         new_file_cleaned_text = get_cleaned_text_from_mongodb(new_file_name, documents_data_db)
#         old_file_cleaned_text = get_cleaned_text_from_mongodb(old_file_name, documents_data_db)

#         list_of_section_texts = get_section_texts(new_file_section_headings_list, new_file_section_headings_list_with_path, old_file_section_headings_list, old_file_section_headings_list_with_path, new_file_cleaned_text, old_file_cleaned_text)

#         print(list_of_section_texts)

#         list_of_section_texts_with_results = get_differences_between_sections(list_of_section_texts)

#         file_pair = (new_file_name, old_file_name)

#         upload_compared_sections_to_mongodb(file_pair, list_of_section_texts_with_results, sections_data)


            

def process_and_compare_pdfs(query, file_pair, new_clean_text, old_clean_text, repetitions=3):
    """Process and compare two PDF documents"""
    
    #file_pair = f"{file_name_new}_{file_name_old}"
    #print(file_pair)
    if query != "Select a section":
        result = fetch_comparison_results(file_pair, query, db_name="capstone_db", collection_name="sections_data")
        if result:
            return result
        else:
            err = f"No results found for section '{query}'"
            return err
    else:    

        print("Comparing documents...")
        comparison_result = compare_documents_with_gpt4o(new_clean_text, old_clean_text)
            
        if comparison_result:
            print("\n--- Initial Comparison Results ---")
            print(comparison_result)
        else:
            print("Failed to retrieve differences.")

        
        for i in range(repetitions - 1):  
            print(f"\n--- Iteration: {i+2} ---")
            print("Making API call to GPT-4o for document comparison...")
            new_result = compare_documents_with_gpt4o_loop(new_clean_text, old_clean_text, comparison_result, i, endpoint, api_key)
                
            if new_result:
                print("\n--- Additional Differences Found ---")
                print(new_result)
                comparison_result = new_result
            else:
                print("Failed to retrieve additional differences.")

        

        return comparison_result
            