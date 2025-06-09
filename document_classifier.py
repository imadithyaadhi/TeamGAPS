import os
import fitz  # PyMuPDF for PDFs
import docx

def extract_text(file_path):
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        return " ".join([page.get_text() for page in doc])
    elif file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        return " ".join([para.text for para in doc.paragraphs])
    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# Load documents from a folder
data_folder = "C:\\Users\\Administrator\\Desktop\\genAI\\documents"
documents = []
labels = []  # Placeholder for classification labels

for filename in os.listdir(data_folder):
    file_path = os.path.join(data_folder, filename)
    text = extract_text(file_path)
    documents.append(text)
    labels.append("unknown")  # Replace with actual labels
    
for filename in os.listdir(data_folder):
    file_path = os.path.join(data_folder, filename)
    text = extract_text(file_path)
    
    # Identify file type
    if filename.endswith(".pdf"):
        file_type = "PDF"
    elif filename.endswith(".docx"):
        file_type = "DOCX"
    elif filename.endswith(".txt"):
        file_type = "TXT"
    else:
        file_type = "Unknown"

    print(f"Processing {filename} | Type: {file_type}")
    documents.append(text)
    labels.append("unknown")  # Replace with actual labels

# Display processing summary
total_documents = len(documents)
unique_categories = len(set(labels))  # Count unique classifications

print(f"Total Documents Processed: {total_documents}")
print(f"Unique Categories Identified: {unique_categories}")

for filename in os.listdir(data_folder):
    file_path = os.path.join(data_folder, filename)
    text = extract_text(file_path)

    # Identify file type
    if filename.endswith(".pdf"):
        file_type = "PDF"
    elif filename.endswith(".docx"):
        file_type = "DOCX"
    elif filename.endswith(".txt"):
        file_type = "TXT"
    else:
        file_type = "Unknown"

    # Print extracted text preview
    print(f"Extracted Text from {filename}:")
    print(f"\"{text[:100]}...\"")  # Show only first 100 characters for readability

    documents.append(text)
    labels.append("unknown")  # Replace with actual labels