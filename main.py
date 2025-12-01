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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

# --- Configuração ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BMS_API")

app = FastAPI(title="BMS Spec Extractor & Generator API", version="2.2.0")

# --- Segurança ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)
REAL_KEY = "minha-chave-secreta-123" 

async def verify_key(key: str = Security(api_key_header)):
    if key == REAL_KEY:
        return key
    raise HTTPException(401, "Chave inválida")

# ==========================================
#    MODELOS DE DADOS
# ==========================================

class PdfRequest(BaseModel):
    arquivo_base64: str

class SectionRequest(BaseModel):
    arquivo_base64: str
    inicio_texto: str
    fim_texto: Optional[str] = None

# Modelos do JSON do Power Automate
class PointData(BaseModel):
    Descriptor: Optional[str] = "Unknown Point"
    Signal_Type: Optional[str] = "-"
    Notes: Optional[str] = ""

class EquipmentData(BaseModel):
    Tag: Optional[str] = "No Tag"
    Description: Optional[str] = ""
    Status: Optional[str] = "New"
    Points: List[PointData] = []

class SystemData(BaseModel):
    System_Name: Optional[str] = "System"
    Equipment: List[EquipmentData] = []

class ProjectData(BaseModel):
    Project_Name: Optional[str] = "Project Report"
    Systems: List[SystemData] = []

# ==========================================
#          SERVIÇOS
# ==========================================

def extract_text_pypdf(pdf_bytes, limit=None, maintain_layout=True):
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
    Gera o PDF com tabelas aninhadas.
    Versão Corrigida 2.2: Correção de erro 'NoneType > int' e layout seguro.
    """
    print(f"--- Iniciando Geração de PDF para: {data.Project_Name} ---")
    buffer = io.BytesIO()
    
    # A4 Landscape: 297mm x 210mm
    # Margens seguras: 12mm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12*mm, leftMargin=12*mm,
        topMargin=12*mm, bottomMargin=12*mm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos Customizados
    title_style = ParagraphStyle('TitleCustom', parent=styles['Heading1'], alignment=1, fontSize=16, spaceAfter=15)
    normal_style = ParagraphStyle('NormalCustom', parent=styles['Normal'], fontSize=9, leading=11)
    header_style = ParagraphStyle('HeaderCustom', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.white)
    
    # Sanitização do Nome do Projeto
    p_name = str(data.Project_Name or "Project Report")
    elements.append(Paragraph(f"Points List Schedule: {p_name}", title_style))
    elements.append(Spacer(1, 5*mm))

    # --- Definição de Cores ---
    HEADER_COLOR = colors.Color(0.26, 0.33, 0.42)
    SUB_HEADER_COLOR = colors.Color(0.35, 0.45, 0.55)
    ROW_BG_ODD = colors.Color(0.95, 0.95, 0.95)
    
    # --- Definição de Larguras (Matemática Segura) ---
    # Largura Útil A4 Land: 297 - 24 = 273mm.
    # Total Main Table: 40 + 30 + 50 + 20 + 130 = 270mm (OK)
    MAIN_COLS = [40*mm, 30*mm, 50*mm, 20*mm, 130*mm]
    
    # Sub Table: Deve caber na col 5 (130mm) - padding.
    # Total Sub Table: 60 + 20 + 45 = 125mm (OK)
    SUB_COLS = [60*mm, 20*mm, 45*mm]

    # --- Construção dos Dados ---
    # Cabeçalho Mestre
    main_table_data = [
        [
            Paragraph("System", header_style), 
            Paragraph("Tag", header_style), 
            Paragraph("Description", header_style), 
            Paragraph("Status", header_style), 
            Paragraph("Points List Details", header_style)
        ]
    ]

    # Sanitização da lista de sistemas
    systems_list = data.Systems if data.Systems else []

    # Se não houver sistemas, cria um dummy para não dar erro de tabela vazia
    if not systems_list:
        systems_list = [SystemData(System_Name="No Data", Equipment=[])]

    for system in systems_list:
        sys_name = str(system.System_Name or "System")
        equip_list = system.Equipment if system.Equipment else []
        
        # Bloco de Sistema (Para manter junto se possível)
        system_rows = [] 

        for eq in equip_list:
            # Sanitização de Equipamento
            tag = str(eq.Tag or "-")
            desc = str(eq.Description or "")
            status = str(eq.Status or "New")
            
            # --- Construir Sub-Tabela de Pontos ---
            points_data = [[
                Paragraph("Descriptor", header_style),
                Paragraph("Signal", header_style),
                Paragraph("Notes", header_style)
            ]]
            
            p_list = eq.Points if eq.Points else []
            for pt in p_list:
                # Sanitização de Pontos
                p_desc = str(pt.Descriptor or "Point")
                p_sig = str(pt.Signal_Type or "-")
                p_note = str(pt.Notes or "")
                
                points_data.append([
                    Paragraph(p_desc, normal_style),
                    Paragraph(p_sig, normal_style), # Usando Paragraph para quebra de linha segura
                    Paragraph(p_note, normal_style)
                ])

            # Criar Tabela Interna (Sub-Table)
            # splitByRow=1 permite que a tabela interna quebre se for muito longa
            sub_table = Table(points_data, colWidths=SUB_COLS, splitByRow=1)
            sub_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), SUB_HEADER_COLOR),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))

            # Adicionar linha à tabela principal
            main_table_data.append([
                Paragraph(sys_name, normal_style), # Coluna System repetida (sem SPAN para evitar erro de quebra)
                Paragraph(tag, normal_style),
                Paragraph(desc, normal_style),
                status,
                sub_table
            ])

    # --- Criação da Tabela Mestra ---
    # splitByRow=1 é CRÍTICO aqui. Permite que a tabela principal seja dividida entre páginas.
    main_table = Table(main_table_data, colWidths=MAIN_COLS, repeatRows=1, splitByRow=1)
    
    main_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    elements.append(main_table)
    
    try:
        doc.build(elements)
        print("--- PDF Gerado com Sucesso ---")
    except Exception as e:
        print(f"ERRO CRÍTICO REPORTLAB: {e}")
        # Em caso de erro fatal, gera um PDF de erro simples para não travar o Power Automate
        buffer = io.BytesIO()
        c = SimpleDocTemplate(buffer)
        c.build([Paragraph(f"Erro ao gerar relatório: {str(e)}", styles['Normal'])])
        buffer.seek(0)
        return buffer
    
    buffer.seek(0)
    return buffer

# ==========================================
#                ENDPOINTS
# ==========================================

@app.post("/extract-toc", dependencies=[Depends(verify_key)])
async def get_toc(req: PdfRequest):
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        text = extract_text_pypdf(pdf_bytes, limit=20, maintain_layout=False)
        return {"text": text}
    except Exception as e:
        logger.error(f"Erro TOC: {e}")
        raise HTTPException(500, str(e))

@app.post("/extract-section", dependencies=[Depends(verify_key)])
async def get_section(req: SectionRequest):
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        full_text = extract_text_pypdf(pdf_bytes, maintain_layout=True)
        idx_start = full_text.find(req.inicio_texto)
        if idx_start == -1: raise HTTPException(404, "Marcador não encontrado.")
        
        final_text = full_text[idx_start:]
        if req.fim_texto:
            idx_end = full_text.find(req.fim_texto, idx_start)
            if idx_end != -1: final_text = full_text[idx_start:idx_end]
            
        return {"section_text": final_text}
    except Exception as e:
        logger.error(f"Erro Section: {e}")
        raise HTTPException(500, str(e))

@app.post("/generate-pdf", dependencies=[Depends(verify_key)])
async def generate_pdf_endpoint(data: ProjectData):
    try:
        pdf_file = service_generate_pdf(data)
        safe_name = "".join([c for c in (data.Project_Name or "Report") if c.isalnum() or c in (' ','-','_')]).rstrip()
        filename = f"Points_List_{safe_name.replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            pdf_file, 
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        raise HTTPException(500, f"Erro interno PDF: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
