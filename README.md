# BMS Spec Extractor & Generator API

## 📖 Overview

This is a **FastAPI** application designed to automate documentation workflows for Building Management Systems (BMS). It serves two main purposes:
1.  **PDF Parsing:** Extracts text and specific sections from PDF specifications (uploaded as Base64 strings).
2.  **Report Generation:** Generates professional PDF "Points List Schedules" with nested tables based on structured JSON data.

It is optimized for integration with automation tools like **Microsoft Power Automate**, Logic Apps, or custom Python scripts.

## 🛠️ Tech Stack

* **Python 3.8+**
* **FastAPI:** High-performance web framework.
* **PDFPlumber:** For robust text extraction from existing PDFs.
* **ReportLab:** For programmatic generation of complex PDF layouts.
* **Pydantic:** For strict data validation.

## 🚀 Installation

1.  **Clone the repository** or download the source code.
2.  **Install dependencies**:
    Create a `requirements.txt` file (or run directly):
    ```bash
    pip install fastapi uvicorn pdfplumber reportlab pydantic
    ```

## ⚙️ Configuration

### Authentication
The API is protected by a static API Key in the Header.
* **Header Name:** `X-API-Key`
* **Default Key:** `minha-chave-secreta-123`
    * *Note: Update the `REAL_KEY` variable in `main.py` for production use.*
