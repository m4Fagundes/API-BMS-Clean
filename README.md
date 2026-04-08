---
created: 2026-04-08
last_edited_date: 2026-04-08
last_edited_by: Gemini AI
tags:
  - api
  - bms
  - power-automate
  - points-list
---

# API-BMS-Clean: Backend for Points List Automation

**📖 Overview:** This FastAPI application serves as the **intelligent backend** for the [[Points_List_Generator]] Power Automate flow, automating extraction of mechanical specification data from PDFs and generating structured Excel/PDF reports for BMS projects.

## 🔗 Complete Documentation

For full architectural documentation, integration guides, and examples, see the **SetPoint skill documentation**:

📄 **[SKILL/SetPoint/SetPoint_README.md](../SKILL/SetPoint/SetPoint_README.md)**

## 🚀 Quick Start

### Installation

```bash
cd API-BMS-Clean
pip install fastapi uvicorn pdfplumber reportlab pydantic
```

### Running the API

```bash
python main.py
# Access: http://127.0.0.1:8000/docs
```

### Authentication

```http
POST /pdf/extract-toc
Content-Type: application/json
X-API-Key: xxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## 🏗️ Architecture

The API follows a **clean architecture** pattern:

```
src/
├── core/           # Configuration & security
├── domain/         # Data models (DTOs)
├── application/    # Business logic services
├── infrastructure/ # External implementations
└── presentation/   # API routes
```

## 🔧 Key Endpoints

### PDF Operations

- `POST /pdf/extract-toc` - Extract table of contents
- `POST /pdf/extract-section` - Extract specific section between text markers
- `POST /pdf/upload-and-classify` - Upload + classify P&ID vs Layout pages
- `GET /pdf/page/{session_id}/{page}` - Extract individual pages from cached PDF

### Report Generation

- `POST /reports/excel` - Generate structured Excel reports
- `POST /reports/bms-points-excel` - BMS Points List format
- `POST /reports/points-list-excel` - SetPoint standard Points List format

## 📊 Data Models

See `src/domain/models.py` for complete Pydantic models:

1. **`PointsListRequest`** - Standard SetPoint Points List format
2. **`BMSPointsRequest`** - BMS-specific points format
3. **`PIDAnalysisExportRequest`** - P&ID analysis export

## 🔒 Security

### API Key Configuration

```python
# src/core/config.py
api_key: str = "xxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Change for production
```

> [!warning] Production Security
> Always change the default API key in production environments.

## 🤖 Integration with Power Automate

This API is designed to work seamlessly with the **3-flow modular architecture** documented in [[PowerAutomate_Implementation_Strategy]]:

1. **Flow 1:** Points List Generator (specification processing)
2. **Flow 2:** Drawing Analyzer (P&ID/image analysis)
3. **Flow 3:** Master Consolidator (intelligent data merging)

---

> [!note] Documentation Status
> This README provides a quick reference. For complete documentation including **architecture diagrams**, **performance optimizations**, and **integration examples**, refer to the main SetPoint skill documentation.
