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

# --- Bibliotecas PDF (ReportLab) ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

# --- Bibliotecas Excel (OpenPyXL) ---
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# --- Configuração ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BMS_API")

app = FastAPI(title="BMS: PDF & Complex Excel Generator", version="5.0.0")

# --- Segurança ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)
REAL_KEY = "minha-chave-secreta-123" 

async def verify_key(key: str = Security(api_key_header)):
    if key == REAL_KEY:
        return key
    raise HTTPException(401, "Chave inválida")

# ==========================================
#           MODELOS DE DADOS
# ==========================================

class PdfRequest(BaseModel):
    arquivo_base64: str

class SectionRequest(BaseModel):
    arquivo_base64: str
    inicio_texto: str
    fim_texto: Optional[str] = None

class PointData(BaseModel):
    Descriptor: str
    Signal_Type: str
    Notes: Optional[str] = ""

class EquipmentData(BaseModel):
    Tag: str
    Description: Optional[str] = ""
    Status: Optional[str] = ""
    Points: List[PointData] = []

class SystemData(BaseModel):
    System_Name: str
    Equipment: List[EquipmentData] = []

class ProjectReportRequest(BaseModel):
    Focus_Category: Optional[str] = "General"
    Systems: List[SystemData] = []

# ==========================================
#           SERVIÇOS (LÓGICA)
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

def service_generate_points_excel_structured(data: ProjectReportRequest) -> io.BytesIO:
    """
    Gera Excel com células mescladas (Merged Cells) similar à imagem fornecida.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Detailed Points List"

    # --- Estilos ---
    # Cores baseadas na imagem (Azul Escuro para Header Principal, Cinza/Azul para Sub-header)
    COLOR_HEADER_MAIN = "2C3E50"  # Azul escuro
    COLOR_HEADER_SUB = "5D6D7E"   # Cinza azulado
    COLOR_TEXT_WHITE = "FFFFFF"
    
    # Bordas
    thin_border = Side(border_style="thin", color="000000")
    border_all = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thin_border)

    # Fontes e Preenchimentos
    font_main_header = Font(bold=True, color=COLOR_TEXT_WHITE, size=11)
    fill_main_header = PatternFill(start_color=COLOR_HEADER_MAIN, end_color=COLOR_HEADER_MAIN, fill_type="solid")
    
    font_sub_header = Font(bold=True, color=COLOR_TEXT_WHITE, size=10)
    fill_sub_header = PatternFill(start_color=COLOR_HEADER_SUB, end_color=COLOR_HEADER_SUB, fill_type="solid")

    align_top_left = Alignment(horizontal="left", vertical="top", wrap_text=True)
    align_center = Alignment(horizontal="center", vertical="center")

    # 1. Cabeçalho Principal (Linha 1)
    headers = ["System", "Tag", "Description", "Status", "Points List Details", "", ""] # Colunas extras vazias para o merge
    ws.append(headers)

    # Formatar Cabeçalho Principal
    for col_idx, cell in enumerate(ws[1], start=1):
        cell.font = font_main_header
        cell.fill = fill_main_header
        cell.alignment = align_top_left
        cell.border = border_all
    
    # Mesclar as colunas E, F, G para o título "Points List Details"
    ws.merge_cells("E1:G1")

    # 2. Iterar e Preencher Dados
    current_row = 2
    systems_list = data.Systems if data.Systems else []

    for system in systems_list:
        sys_name = system.System_Name
        
        for eq in system.Equipment:
            # Calcular quantas linhas esse equipamento vai ocupar
            # 1 linha para o cabeçalho dos pontos (Descriptor/Signal/Notes) + N linhas de pontos
            # Se não tiver pontos, ocupa pelo menos 1 linha
            num_points = len(eq.Points)
            rows_needed = num_points + 1 if num_points > 0 else 1
            
            end_row = current_row + rows_needed - 1

            # --- Preencher Colunas da Esquerda (Equipamento) ---
            # Escrevemos apenas na primeira célula do bloco, depois mesclamos
            ws.cell(row=current_row, column=1, value=sys_name).alignment = align_top_left
            ws.cell(row=current_row, column=2, value=eq.Tag).alignment = align_top_left
            ws.cell(row=current_row, column=3, value=eq.Description).alignment = align_top_left
            ws.cell(row=current_row, column=4, value=eq.Status).alignment = align_top_left

            # Aplicar bordas nas células da esquerda (loop para garantir borda na área mesclada)
            for r in range(current_row, end_row + 1):
                for c in range(1, 5): # Colunas A a D
                    ws.cell(row=r, column=c).border = border_all

            # Mesclar verticalmente as colunas A, B, C, D
            if rows_needed > 1:
                ws.merge_cells(start_row=current_row, start_column=1, end_row=end_row, end_column=1) # System
                ws.merge_cells(start_row=current_row, start_column=2, end_row=end_row, end_column=2) # Tag
                ws.merge_cells(start_row=current_row, start_column=3, end_row=end_row, end_column=3) # Description
                ws.merge_cells(start_row=current_row, start_column=4, end_row=end_row, end_column=4) # Status

            # --- Preencher Colunas da Direita (Pontos) ---
            
            # Se houver pontos, cria o sub-cabeçalho e lista os pontos
            if num_points > 0:
                # Sub-cabeçalho na primeira linha do bloco
                sub_headers = ["Descriptor", "Signal", "Notes"]
                for i, text in enumerate(sub_headers):
                    c = ws.cell(row=current_row, column=5+i, value=text)
                    c.font = font_sub_header
                    c.fill = fill_sub_header
                    c.border = border_all
                    c.alignment = align_top_left

                # Listar os pontos nas linhas seguintes
                point_row_idx = current_row + 1
                for pt in eq.Points:
                    ws.cell(row=point_row_idx, column=5, value=pt.Descriptor).border = border_all
                    ws.cell(row=point_row_idx, column=6, value=pt.Signal_Type).border = border_all
                    ws.cell(row=point_row_idx, column=7, value=pt.Notes).border = border_all
                    point_row_idx += 1
            else:
                # Se não houver pontos, deixa células vazias com borda ou mensagem
                ws.cell(row=current_row, column=5, value="No Points").border = border_all
                ws.cell(row=current_row, column=6, value="-").border = border_all
                ws.cell(row=current_row, column=7, value="-").border = border_all

            # Avançar o cursor de linha
            current_row += rows_needed

    # 3. Ajuste de Largura das Colunas
    column_widths = [15, 15, 30, 10, 30, 10, 30] # Larguras estimadas para A, B, C, D, E, F, G
    for i, width in enumerate(column_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

# --- Serviço de PDF (Mantido igual) ---
def service_generate_pdf(data: ProjectReportRequest) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=12*mm, leftMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleCustom', parent=styles['Heading1'], alignment=1, fontSize=16, spaceAfter=15)
    normal_style = ParagraphStyle('NormalCustom', parent=styles['Normal'], fontSize=9, leading=11)
    header_style = ParagraphStyle('HeaderCustom', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.white)
    
    elements.append(Paragraph(f"Points List: {data.Focus_Category}", title_style))
    elements.append(Spacer(1, 5*mm))

    HEADER_COLOR = colors.Color(0.26, 0.33, 0.42)
    SUB_HEADER_COLOR = colors.Color(0.35, 0.45, 0.55)
    MAIN_COLS = [40*mm, 30*mm, 50*mm, 20*mm, 130*mm]
    SUB_COLS = [60*mm, 20*mm, 45*mm]

    main_table_data = [[Paragraph("System", header_style), Paragraph("Tag", header_style), Paragraph("Description", header_style), Paragraph("Status", header_style), Paragraph("Points Details", header_style)]]

    systems_list = data.Systems if data.Systems else []

    for system in systems_list:
        sys_name = str(system.System_Name)
        for eq in system.Equipment:
            points_data = [[Paragraph("Descriptor", header_style), Paragraph("Signal", header_style), Paragraph("Notes", header_style)]]
            if eq.Points:
                for pt in eq.Points:
                    points_data.append([Paragraph(str(pt.Descriptor), normal_style), Paragraph(str(pt.Signal_Type), normal_style), Paragraph(str(pt.Notes), normal_style)])
            else:
                points_data.append(["No points", "-", "-"])
            
            sub_table = Table(points_data, colWidths=SUB_COLS, splitByRow=1)
            sub_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), SUB_HEADER_COLOR),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 0), (-1, -1), 8)
            ]))
            
            main_table_data.append([Paragraph(sys_name, normal_style), Paragraph(str(eq.Tag), normal_style), Paragraph(str(eq.Description), normal_style), str(eq.Status), sub_table])

    if len(main_table_data) > 1:
        main_table = Table(main_table_data, colWidths=MAIN_COLS, repeatRows=1, splitByRow=1)
        main_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))
        elements.append(main_table)
    else:
        elements.append(Paragraph("No data", normal_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==========================================
#           ROTAS (ENDPOINTS)
# ==========================================

@app.post("/extract-toc", dependencies=[Depends(verify_key)])
async def get_toc(req: PdfRequest):
    try:
        pdf_bytes = base64.b64decode(req.arquivo_base64)
        text = extract_text_pypdf(pdf_bytes, limit=20, maintain_layout=False)
        return {"text": text}
    except Exception as e:
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
        raise HTTPException(500, str(e))

@app.post("/generate-pdf", dependencies=[Depends(verify_key)])
async def generate_pdf_endpoint(data: ProjectReportRequest):
    try:
        pdf_file = service_generate_pdf(data)
        safe_name = "".join([c for c in (data.Focus_Category or "Report") if c.isalnum() or c in (' ','-','_')]).strip()
        filename = f"{safe_name}.pdf"
        return StreamingResponse(
            pdf_file, 
            media_type="application/pdf", 
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Erro PDF: {e}")
        raise HTTPException(500, str(e))

@app.post("/generate-excel", dependencies=[Depends(verify_key)])
async def generate_excel_endpoint(data: ProjectReportRequest):
    try:
        # Chama o NOVO serviço estruturado
        excel_file = service_generate_points_excel_structured(data)
        
        safe_name = "".join([c for c in (data.Focus_Category or "Report") if c.isalnum() or c in (' ','-','_')]).strip()
        filename = f"{safe_name}.xlsx"
        return StreamingResponse(
            excel_file, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Erro Excel: {e}")
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)