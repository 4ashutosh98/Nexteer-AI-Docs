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

logging.basicConfig(level=logging.INFO)

class ExtractTextInfoFromPDF:
    def __init__(self, input_pdf_path):
        load_dotenv()
        self.credentials = ServicePrincipalCredentials(
            client_id=os.getenv('PDF_SERVICES_CLIENT_ID'),
            client_secret=os.getenv('PDF_SERVICES_CLIENT_SECRET')
        )
        self.pdf_services = PDFServices(credentials=self.credentials)
        self.input_pdf_path = input_pdf_path

    def extract_text(self):
        try:
            with open(self.input_pdf_path, 'rb') as file:
                input_stream = file.read()

            input_asset = self.pdf_services.upload(input_stream=input_stream, mime_type=PDFServicesMediaType.PDF)
            extract_pdf_params = ExtractPDFParams(elements_to_extract=[ExtractElementType.TEXT])
            extract_pdf_job = ExtractPDFJob(input_asset=input_asset, extract_pdf_params=extract_pdf_params)

            location = self.pdf_services.submit(extract_pdf_job)
            pdf_services_response = self.pdf_services.get_job_result(location, ExtractPDFResult)

            result_asset = pdf_services_response.get_result().get_resource()
            stream_asset = self.pdf_services.get_content(result_asset)

            output_file_path = self.create_output_file_path()
            with open(output_file_path, "wb") as file:
                file.write(stream_asset.get_input_stream())

            return self.process_output(output_file_path)

        except (ServiceApiException, ServiceUsageException, SdkException) as e:
            logging.exception(f'Exception encountered while executing operation: {e}')
            return None

    @staticmethod
    def create_output_file_path():
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        os.makedirs("output/ExtractTextInfoFromPDF", exist_ok=True)
        return f"output/ExtractTextInfoFromPDF/extract{timestamp}.zip"

    def process_output(self, output_file_path):
        output_folder = "Adobe PDF Extract API outputs"
        os.makedirs(output_folder, exist_ok=True)

        with zipfile.ZipFile(output_file_path, 'r') as archive:
            with archive.open('structuredData.json') as jsonentry:
                data = json.load(jsonentry)

        input_file_name = os.path.basename(self.input_pdf_path)
        output_json_name = os.path.splitext(input_file_name)[0] + ".json"
        output_json_path = os.path.join(output_folder, output_json_name)

        with open(output_json_path, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)

        logging.info(f"JSON output saved to: {output_json_path}")

        os.remove(output_file_path)

        return output_json_path
    
    @staticmethod
    def get_document_structure(output_json_path):
        try:
            with open(output_json_path, 'r', encoding='utf-8') as json_file:
                data = json.load(json_file)

            document_structure = {}
            current_section = document_structure
            section_stack = [document_structure]

            for element in data.get("elements", []):
                path = element.get("Path", "").replace("//Document/", "")
                if path[0] == "H" and path[1].isdigit():
                    level = int(path[1])
                    text = element.get("Text", "No Text")

                    while len(section_stack) > level:
                        section_stack.pop()

                    new_section = {"title": text, "subsections": {}}
                    current_section = section_stack[-1]
                    current_section[f"H{level}_{len(current_section)}"] = new_section
                    section_stack.append(new_section["subsections"])

            return document_structure

        except Exception as e:
            print(f"An error occurred while processing the JSON file: {e}")
            return None

    @staticmethod
    def get_section_headings(data):
        section_headings = []
        i = 0
        for element in data.get("elements", []):
            path = element.get("Path", "").replace("//Document/", "")
            if path[0:2] == "H1": #and path[1].isdigit():
                section_headings.append({"path": path, "text": element.get("Text", "No Text")})
                i += 1

        return section_headings
