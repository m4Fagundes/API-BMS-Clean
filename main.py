import uvicorn
import io
import base64
import logging
import pdfplumber

from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import List, Optional

# --- Bibliotecas de PDF (ReportLab) ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

# --- Configuração ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BMS_API")

app = FastAPI(title="BMS Spec Extractor & Generator API", version="2.0.0")

# --- Segurança ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)
REAL_KEY = "minha-chave-secreta-123" 

async def verify_key(key: str = Security(api_key_header)):
    if key == REAL_KEY:
        return key
    raise HTTPException(401, "Chave inválida")

# ==========================================
#    MODELOS DE DADOS (Request Bodies)
# ==========================================

# Modelos para Extração de Texto (Existentes)
class PdfRequest(BaseModel):
    arquivo_base64: str

class SectionRequest(BaseModel):
    arquivo_base64: str
    inicio_texto: str
    fim_texto: Optional[str] = None

# Novos Modelos para Geração de PDF (Estrutura do JSON vindo do Power Automate)
class PointData(BaseModel):
    Descriptor: str
    Signal_Type: str
    Notes: Optional[str] = ""

class EquipmentData(BaseModel):
    Tag: str
    Description: str
    Status: Optional[str] = "New"
    Points: List[PointData]

class SystemData(BaseModel):
    System_Name: str
    Equipment: List[EquipmentData]

class ProjectData(BaseModel):
    Project_Name: str
    Systems: List[SystemData]

# ==========================================
#          SERVIÇOS (Lógica Pura)
# ==========================================

def extract_text_pypdf(pdf_bytes, limit=None, maintain_layout=True):
    """Lógica de extração de texto do PDF (Mantida igual)"""
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = pdf.pages[:limit] if limit else pdf.pages
        for page in pages:
            extracted = page.extract_text(layout=maintain_layout) 
            if extracted:
                text += extracted + "\n"
    return text

def service_generate_pdf(data: ProjectData) -> io.BytesIO:
    """
    Lógica complexa de desenho do PDF com tabelas aninhadas.
    Retorna um buffer de bytes (o arquivo em memória).
    """
    buffer = io.BytesIO()
    
    # Configuração da página (Paisagem/Landscape para caber mais colunas)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10*mm, leftMargin=10*mm,
        topMargin=10*mm, bottomMargin=10*mm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos Personalizados
    title_style = ParagraphStyle('TitleCustom', parent=styles['Heading1'], alignment=1, fontSize=16, spaceAfter=15)
    normal_style = ParagraphStyle('NormalCustom', parent=styles['Normal'], fontSize=9, leading=11)
    header_style = ParagraphStyle('HeaderCustom', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.white)
    
    # Título do Projeto
    elements.append(Paragraph(f"Points List Schedule: {data.Project_Name}", title_style))

    # --- Construção da Tabela Mestra ---
    # Cabeçalho
    main_table_data = [
        [
            Paragraph("System", header_style), 
            Paragraph("Tag", header_style), 
            Paragraph("Description", header_style), 
            Paragraph("Status", header_style), 
            Paragraph("Points List Details", header_style)
        ]
    ]

    # Definição de Cores (Estilo "Slate/Blue" profissional)
    HEADER_COLOR = colors.Color(0.26, 0.33, 0.42) # Azul Petróleo Escuro
    SUB_HEADER_COLOR = colors.Color(0.35, 0.45, 0.55) 
    ROW_BG = colors.Color(0.96, 0.96, 0.96)

    span_commands = [] # Lista para guardar onde vamos mesclar a coluna "System"
    row_index = 1      # Índice atual da linha (0 é cabeçalho)

    for system in data.Systems:
        start_row = row_index
        
        # Se o sistema não tem equipamentos, pula
        if not system.Equipment:
            continue

        for eq in system.Equipment:
            # --- 1. Construir a SUB-TABELA (Pontos) ---
            # Esta tabela vai DENTRO da célula da coluna 5
            
            # Cabeçalho da Sub-tabela
            points_data = [[
                Paragraph("Descriptor", header_style),
                Paragraph("Signal", header_style),
                Paragraph("Notes", header_style)
            ]]
            
            # Linhas da Sub-tabela
            for pt in eq.Points:
                points_data.append([
                    Paragraph(pt.Descriptor, normal_style),
                    pt.Signal_Type,
                    Paragraph(pt.Notes or "", normal_style)
                ])

            # Criar objeto Tabela Interna
            sub_table = Table(points_data, colWidths=[70*mm, 25*mm, 55*mm])
            sub_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), SUB_HEADER_COLOR), # Cabeçalho interno
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ]))

            # --- 2. Adicionar linha na Tabela Principal ---
            main_table_data.append([
                Paragraph(system.System_Name, normal_style), # Col 1 (será mesclada)
                Paragraph(eq.Tag, normal_style),             # Col 2
                Paragraph(eq.Description, normal_style),     # Col 3
                eq.Status,                                   # Col 4
                sub_table                                    # Col 5 (A tabela inteira)
            ])
            
            row_index += 1

        # Lógica de Mesclagem (SPAN) para a coluna "System"
        # Se houve mais de 1 equipamento nesse sistema, mescla as células verticais
        if row_index - 1 > start_row:
            span_commands.append(('SPAN', (0, start_row), (0, row_index - 1)))
            span_commands.append(('VALIGN', (0, start_row), (0, row_index - 1), 'TOP')) # Alinha texto ao topo

    # --- Configuração Final da Tabela Mestra ---
    # Larguras das colunas principais (Total ~280mm para A4 Landscape)
    main_col_widths = [40*mm, 25*mm, 45*mm, 20*mm, 150*mm]
    
    main_table = Table(main_table_data, colWidths=main_col_widths, repeatRows=1)
    
    # Estilos Gerais
    main_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_COLOR),     # Cabeçalho Principal
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),      # Texto Cabeçalho Branco
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),       # Bordas Pretas na tabela externa
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),               # Alinhamento padrão topo
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    
    # Adiciona os comandos de SPAN calculados no loop
    main_styles.extend(span_commands)
    
    main_table.setStyle(TableStyle(main_styles))
    
    elements.append(main_table)
    doc.build(elements)
    
    buffer.seek(0)
    return buffer

# ==========================================
#                ENDPOINTS
# ==========================================

@app.post("/extract-toc", dependencies=[Depends(verify_key)])
async def get_toc(req: PdfRequest):
    """Extrai Sumário (Mantido)"""
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        text = extract_text_pypdf(pdf_bytes, limit=20, maintain_layout=False)
        return {"text": text}
    except Exception as e:
        logger.error(f"Erro TOC: {e}")
        raise HTTPException(500, str(e))

@app.post("/extract-section", dependencies=[Depends(verify_key)])
async def get_section(req: SectionRequest):
    """Extrai Seção Específica (Mantido)"""
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        full_text = extract_text_pypdf(pdf_bytes, maintain_layout=True)
        
        idx_start = full_text.find(req.inicio_texto)
        if idx_start == -1:
             raise HTTPException(404, f"Marcador '{req.inicio_texto}' não encontrado.")

        if req.fim_texto:
            idx_end = full_text.find(req.fim_texto, idx_start)
            if idx_end == -1:
                final_text = full_text[idx_start:]
            else:
                final_text = full_text[idx_start:idx_end]
        else:
            final_text = full_text[idx_start:]
            
        return {"section_text": final_text}
        
    except Exception as e:
        logger.error(f"Erro Section: {e}")
        raise HTTPException(500, str(e))

@app.post("/generate-pdf", dependencies=[Depends(verify_key)])
async def generate_pdf_endpoint(data: ProjectData):
    """
    NOVO ENDPOINT: Recebe o JSON estruturado e retorna um arquivo PDF binário.
    O Power Automate vai salvar esse binário como arquivo .pdf.
    """
    try:
        pdf_file = service_generate_pdf(data)
        
        # Nome do arquivo limpo
        safe_name = "".join([c for c in data.Project_Name if c.isalnum() or c in (' ','-','_')]).rstrip()
        filename = f"Points_List_{safe_name.replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            pdf_file, 
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        raise HTTPException(500, f"Erro na geração do PDF: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)