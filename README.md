# Nexteer AI Docs Capstone Project

This project is designed to process and compare PDF documents using various APIs and libraries. It includes functionalities for extracting text from PDFs using Adobe PDF Extract API, storing and retrieving data from MongoDB for limiting API costs and faster processing, and comparing document sections using GPT-4o.

## Getting Started

Follow these instructions to set up the project on your local machine.

### Prerequisites

- [Git](https://git-scm.com/)
- [Anaconda](https://www.anaconda.com/products/distribution) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html) for Conda environment, or [Python](https://www.python.org/downloads/) for virtual environment

### Environment Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/4ashutosh98/Nexteer-AI-Docs.git
   cd final-application
   ```

2. **Create a virtual environment**

- It is recommended to use a python version of 3.11.11 to ensure compatibility with the dependencies.
- It is also recommended to use Conda to manage the environment.

   Using Conda:
   ```bash
   conda create --name nexteer_env python=3.11.11
   conda activate nexteer_env
   ```

   Using venv:
   ```bash
   python -m venv nexteer_env
   nexteer_env\Scripts\activate  # On Windows
   # source nexteer_env/bin/activate  # On macOS/Linux
   ```

3. **Upgrade pip and wheel**

   Open a terminal and run the following commands to ensure you have the latest versions of pip, setuptools, and wheel:

   ```bash
   python.exe -m pip install --upgrade pip
   pip install --upgrade pip setuptools wheel
   ```

4. **Install the required packages**

   ```bash
   pip install -r requirements.txt
   ```

### Configuration

- Create a MongoDB cluster and obtain the connection URI. More information can be found [here](https://www.mongodb.com/docs/guides/).
- More information on obtaining credentials for the Adobe PDF Services API can be found [here](https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/gettingstarted/).
- More information on obtaining the OpenAI API endpoint and key can be found [here](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#deploy-a-model).
- During the deployment of OpenAI endpoint, the version of OpenAI API should be `GPT-4o` Version `2024-08-01-preview` or newer.

- Ensure that the `.env` file is stored as:

  ```plaintext
  PDF_SERVICES_CLIENT_ID="<your Adobe PDF services client ID>"
  PDF_SERVICES_CLIENT_SECRET="<your Adobe PDF services client secret>"
  endpoint = "<your endpoint from Azure OpenAI deployment>"
  api_key = "<your API key from Azure OpenAI deployment>"
  uri = "<your mongoDB atlas URI>"
  ```

- Create the environment variables from the `.env` file by using a tool like `python-dotenv` or manually setting them in your system's environment. For example, you can use the following Python code snippet to load them:

  ```python
  from dotenv import load_dotenv
  load_dotenv()
  ```

  Alternatively, set them manually in your system's environment settings.

- Optionally, you can download MongoDB Compass from the following [link](https://www.mongodb.com/products/tools/compass) and connect to your MongoDB cluster using the URI. MongoDB Compass provides a graphical interface to interact with your MongoDB data.

### Running the Application

1. **Start the MongoDB server**
   - Ensure your MongoDB server is running and accessible.

2. **Run the Streamlit application**

   ```bash
   streamlit run streamlit_gui.py
   ```

   This will start the Streamlit server and open the application in your default web browser.

### Usage

- Upload PDF documents through the Streamlit interface to process and compare them.
- The application will store extracted data in MongoDB and provide comparison results.

### The deployment of the application is accessible on the following link: [Nexteer Document Comparison Tool](https://nexteer-ai-docs-abumbwfz2xlbmcgvtrfvkr.streamlit.app/)


### Acknowledgments

- Nexteer Automotive
- Heinz College of Information Systems and Public Policy
