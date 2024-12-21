# Import necessary libraries and modules
import os
import logging
import json
import zipfile
from datetime import datetime
from dotenv import load_dotenv
from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
from adobe.pdfservices.operation.exception.exceptions import ServiceApiException, ServiceUsageException, SdkException
from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
from adobe.pdfservices.operation.pdf_services import PDFServices
from adobe.pdfservices.operation.pdfjobs.jobs.extract_pdf_job import ExtractPDFJob
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_element_type import ExtractElementType
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_pdf_params import ExtractPDFParams
from adobe.pdfservices.operation.pdfjobs.result.extract_pdf_result import ExtractPDFResult

# Configure logging to display info level messages
logging.basicConfig(level=logging.INFO)

class ExtractTextInfoFromPDF:
    """
    A class to handle the extraction of text information from PDF files using Adobe PDF Services.

    Attributes:
        input_pdf_path (str): The path to the input PDF file.
        credentials (ServicePrincipalCredentials): Credentials for Adobe PDF Services.
        pdf_services (PDFServices): An instance of the PDFServices class.
    """

    def __init__(self, input_pdf_path):
        """
        Initializes the ExtractTextInfoFromPDF class with the path to the PDF file.

        Args:
            input_pdf_path (str): The path to the input PDF file.
        """
        # Load environment variables
        load_dotenv()
        # Set up credentials for Adobe PDF Services
        self.credentials = ServicePrincipalCredentials(
            client_id=os.getenv('PDF_SERVICES_CLIENT_ID'),
            client_secret=os.getenv('PDF_SERVICES_CLIENT_SECRET')
        )
        # Initialize PDFServices with the credentials
        self.pdf_services = PDFServices(credentials=self.credentials)
        # Store the input PDF path
        self.input_pdf_path = input_pdf_path

    def extract_text(self):
        """
        Extracts text from the PDF file and saves it as a JSON file.

        Returns:
            str: The path to the JSON file containing the extracted text.

        Raises:
            ServiceApiException: If there is an API error.
            ServiceUsageException: If there is a usage error.
            SdkException: If there is an SDK error.
        """
        try:
            # Open the PDF file and read its content
            with open(self.input_pdf_path, 'rb') as file:
                input_stream = file.read()

            # Upload the PDF file to Adobe PDF Services
            input_asset = self.pdf_services.upload(input_stream=input_stream, mime_type=PDFServicesMediaType.PDF)
            # Set parameters to extract text elements
            extract_pdf_params = ExtractPDFParams(elements_to_extract=[ExtractElementType.TEXT])
            # Create an extract PDF job
            extract_pdf_job = ExtractPDFJob(input_asset=input_asset, extract_pdf_params=extract_pdf_params)

            # Submit the job and get the location of the result
            location = self.pdf_services.submit(extract_pdf_job)
            pdf_services_response = self.pdf_services.get_job_result(location, ExtractPDFResult)

            # Get the result asset and its content
            result_asset = pdf_services_response.get_result().get_resource()
            stream_asset = self.pdf_services.get_content(result_asset)

            # Create an output file path
            output_file_path = self.create_output_file_path()
            # Write the extracted content to the output file
            with open(output_file_path, "wb") as file:
                file.write(stream_asset.get_input_stream())

            # Process the output file and return the path to the JSON file
            return self.process_output(output_file_path)

        except (ServiceApiException, ServiceUsageException, SdkException) as e:
            # Log any exceptions encountered during the extraction process
            logging.exception(f'Exception encountered while executing operation: {e}')
            return None

    @staticmethod
    def create_output_file_path():
        """
        Creates a unique file path for the output file based on the current timestamp.

        Returns:
            str: The path to the output file.
        """
        # Generate a timestamp for the output file name
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        # Ensure the output directory exists
        os.makedirs("output/ExtractTextInfoFromPDF", exist_ok=True)
        # Return the complete path for the output file
        return f"output/ExtractTextInfoFromPDF/extract{timestamp}.zip"

    def process_output(self, output_file_path):
        """
        Processes the output file, extracts JSON data, and saves it to a specified folder.

        Args:
            output_file_path (str): The path to the output file.

        Returns:
            str: The path to the JSON file containing the processed data.
        """
        # Define the folder to store the extracted JSON data
        output_folder = "Adobe PDF Extract API outputs"
        # Ensure the output folder exists
        os.makedirs(output_folder, exist_ok=True)

        # Extract the JSON data from the zip file
        with zipfile.ZipFile(output_file_path, 'r') as archive:
            with archive.open('structuredData.json') as jsonentry:
                data = json.load(jsonentry)

        # Create a JSON file name based on the input PDF file name
        input_file_name = os.path.basename(self.input_pdf_path)
        output_json_name = os.path.splitext(input_file_name)[0] + ".json"
        output_json_path = os.path.join(output_folder, output_json_name)

        # Write the extracted data to the JSON file
        with open(output_json_path, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)

        # Log the location of the saved JSON file
        logging.info(f"JSON output saved to: {output_json_path}")

        # Remove the temporary output file
        os.remove(output_file_path)

        return output_json_path
    
    @staticmethod
    def get_document_structure(output_json_path):
        """
        Constructs a hierarchical structure of the document based on headings.

        Args:
            output_json_path (str): The path to the JSON file containing extracted data.

        Returns:
            dict: A dictionary representing the document structure.
        """
        try:
            # Open and load the JSON data from the file
            with open(output_json_path, 'r', encoding='utf-8') as json_file:
                data = json.load(json_file)

            # Initialize the document structure and section stack
            document_structure = {}
            current_section = document_structure
            section_stack = [document_structure]

            # Iterate over elements to build the document structure
            for element in data.get("elements", []):
                path = element.get("Path", "").replace("//Document/", "")
                if path[0] == "H" and path[1].isdigit():
                    level = int(path[1])
                    text = element.get("Text", "No Text")

                    # Adjust the section stack based on heading level
                    while len(section_stack) > level:
                        section_stack.pop()

                    # Create a new section and update the current section
                    new_section = {"title": text, "subsections": {}}
                    current_section = section_stack[-1]
                    current_section[f"H{level}_{len(current_section)}"] = new_section
                    section_stack.append(new_section["subsections"])

            return document_structure

        except Exception as e:
            # Print any errors encountered during processing
            print(f"An error occurred while processing the JSON file: {e}")
            return None

    @staticmethod
    def get_section_headings(data):
        """
        Extracts section headings from the document data.

        Args:
            data (dict): The JSON data containing document elements.

        Returns:
            list: A list of dictionaries containing path and text of section headings.
        """
        # Initialize a list to store section headings
        section_headings = []
        i = 0
        # Iterate over elements to find section headings
        for element in data.get("elements", []):
            path = element.get("Path", "").replace("//Document/", "")
            if path[0:2] == "H1": #and path[1].isdigit():
                section_headings.append({"path": path, "text": element.get("Text", "No Text")})
                i += 1

        return section_headings
