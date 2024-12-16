from pydantic import BaseModel, Field, ValidationError
from openai import AzureOpenAI
from openai.types.chat import ChatCompletion
from key_params import endpoint, api_key

# Initialize the Azure OpenAI client
client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version="2024-08-01-preview"
)

# Define the Pydantic model for structured output
class Difference(BaseModel):
    type: str = Field(description="Type of difference: 'added', 'removed', or 'modified'")
    description: str | None = Field(description="Description of the difference", default=None)
    section: str | None = Field(description="Section of the text where the difference occurs", default=None)
    new_file_text: str | None = Field(description="The content in the new file text where the difference occurs", default=None)
    old_file_text: str | None = Field(description="The content in the old file text where the difference occurs", default=None)
    content: str | None = Field(description="Specific content that differs", default=None)
    position: int | None = Field(description="The approximate index of the difference in the new file text", default=None)

class ComparisonResult(BaseModel):
    differences: list[Difference] = Field(description="List of differences between the two strings")
    summary: str = Field(description="Summary of the main differences")

# Function to compare strings using Azure OpenAI
def compare_strings(new_file_text: str, old_file_text: str) -> ComparisonResult | None:
    try:
        # Construct the messages for the prompt
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant designed to compare text sections of a new file and an old file. "
                    "Identify the differences, categorize them as 'added', 'removed', or 'modified', and provide a detailed summary. "
                    "Please return the response strictly in JSON format."
                )
            },
            {
                "role": "user",
                "content": (
                    "Compare the following text sections and return the differences in JSON format:\n\n"
                    f"New File text: {new_file_text}\n\nOld File text: {old_file_text}"
                )
            }
        ]

        # Make the API call with structured output using response_format
        completion: ChatCompletion = client.beta.chat.completions.parse(
            model="gpt-4o",  # Replace with your deployment name if different
            messages=messages,
            response_format=ComparisonResult
        )

        # Get the parsed response
        response_content = completion.choices[0].message.content

        # Validate the response content using Pydantic
        result = ComparisonResult.model_validate_json(response_content)
        return result

    except ValidationError as ve:
        print("Validation error:", ve)
        print("Validation errors detail:", ve.errors())
    except Exception as e:
        print(f"Error during API call or processing: {e}")

    return None

# Main execution logic for testing
if __name__ == "__main__":
    new_file_text = "The quick brown fox jumps over the lazy dog."
    old_file_text = "The quick brown fox jumps over a very lazy dog."

    result = compare_strings(new_file_text, old_file_text)

    if result:
        print("Differences:")
        for diff in result.differences:
            print(f"Type: {diff.type}, Description: {diff.description}")
            if diff.section:
                print(f"Section: {diff.section}")
            if diff.new_file_text or diff.old_file_text:
                print(f"New content: {diff.new_file_text}")
                print(f"Old content: {diff.old_file_text}")
            if diff.content:
                print(f"Content: {diff.content}")
            if diff.position is not None:
                print(f"Position: {diff.position}")

        print("\nSummary:")
        print(result.summary)
    else:
        print("Error in comparing the two texts.")