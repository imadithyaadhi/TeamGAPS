import os
import fitz  # PyMuPDF
import docx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

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

# Example: Loading documents
documents = []
labels = []  # Labels for classification (e.g., 'invoice', 'contract')
data_folder = "C:\\Users\\Administrator\\Desktop\\genAI\\documents"

for filename in os.listdir(data_folder):
    file_path = os.path.join(data_folder, filename)
    text = extract_text(file_path)
    documents.append(text)
    labels.append("unknown")  # Replace with actual classification

# Feature extraction & classification
vectorizer = TfidfVectorizer(stop_words="english")
X = vectorizer.fit_transform(documents)
classifier = MultinomialNB()
classifier.fit(X, labels)

print("Document ingestion and basic classification setup is ready!")