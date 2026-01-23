"""
Serviço para geração de relatórios PDF.
"""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

from src.domain.models import ProjectReportRequest


class PdfReportService:
    """Serviço responsável pela geração de relatórios em PDF."""
    
    # Constantes de estilo
    HEADER_COLOR = colors.Color(0.26, 0.33, 0.42)
    SUB_HEADER_COLOR = colors.Color(0.35, 0.45, 0.55)
    MAIN_COLS = [40*mm, 30*mm, 50*mm, 20*mm, 130*mm]
    SUB_COLS = [60*mm, 20*mm, 45*mm]
    
    def __init__(self):
        self._styles = getSampleStyleSheet()
        self._title_style = ParagraphStyle(
            'TitleCustom', 
            parent=self._styles['Heading1'], 
            alignment=1, 
            fontSize=16, 
            spaceAfter=15
        )
        self._normal_style = ParagraphStyle(
            'NormalCustom', 
            parent=self._styles['Normal'], 
            fontSize=9, 
            leading=11
        )
        self._header_style = ParagraphStyle(
            'HeaderCustom', 
            parent=self._styles['Normal'], 
            fontSize=10, 
            fontName='Helvetica-Bold', 
            textColor=colors.white
        )
    
    def generate(self, data: ProjectReportRequest) -> io.BytesIO:
        """
        Gera um relatório PDF a partir dos dados do projeto.
        
        Args:
            data: Dados do projeto para o relatório.
            
        Returns:
            Buffer contendo o arquivo PDF gerado.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(A4), 
            rightMargin=12*mm, 
            leftMargin=12*mm, 
            topMargin=12*mm, 
            bottomMargin=12*mm
        )
        
        elements = self._build_elements(data)
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    def _build_elements(self, data: ProjectReportRequest) -> list:
        """Constrói os elementos do documento PDF."""
        elements = []
        
        # Título
        elements.append(Paragraph(f"Points List: {data.Focus_Category}", self._title_style))
        elements.append(Spacer(1, 5*mm))
        
        # Tabela principal
        main_table_data = self._build_header_row()
        main_table_data.extend(self._build_data_rows(data))
        
        if len(main_table_data) > 1:
            main_table = self._create_main_table(main_table_data)
            elements.append(main_table)
        else:
            elements.append(Paragraph("No data", self._normal_style))
        
        return elements
    
    def _build_header_row(self) -> list:
        """Constrói a linha de cabeçalho da tabela."""
        return [[
            Paragraph("System", self._header_style), 
            Paragraph("Tag", self._header_style), 
            Paragraph("Description", self._header_style), 
            Paragraph("Status", self._header_style), 
            Paragraph("Points Details", self._header_style)
        ]]
    
    def _build_data_rows(self, data: ProjectReportRequest) -> list:
        """Constrói as linhas de dados da tabela."""
        rows = []
        systems_list = data.Systems if data.Systems else []
        
        for system in systems_list:
            sys_name = str(system.System_Name)
            for eq in system.Equipment:
                sub_table = self._create_points_subtable(eq.Points)
                rows.append([
                    Paragraph(sys_name, self._normal_style), 
                    Paragraph(str(eq.Tag), self._normal_style), 
                    Paragraph(str(eq.Description), self._normal_style), 
                    str(eq.Status), 
                    sub_table
                ])
        
        return rows
    
    def _create_points_subtable(self, points) -> Table:
        """Cria a subtabela de pontos."""
        points_data = [[
            Paragraph("Descriptor", self._header_style), 
            Paragraph("Signal", self._header_style), 
            Paragraph("Notes", self._header_style)
        ]]
        
        if points:
            for pt in points:
                points_data.append([
                    Paragraph(str(pt.Descriptor), self._normal_style), 
                    Paragraph(str(pt.Signal_Type), self._normal_style), 
                    Paragraph(str(pt.Notes), self._normal_style)
                ])
        else:
            points_data.append(["No points", "-", "-"])
        
        sub_table = Table(points_data, colWidths=self.SUB_COLS, splitByRow=1)
        sub_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.SUB_HEADER_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 8)
        ]))
        
        return sub_table
    
    def _create_main_table(self, data: list) -> Table:
        """Cria a tabela principal do relatório."""
        main_table = Table(data, colWidths=self.MAIN_COLS, repeatRows=1, splitByRow=1)
        main_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.HEADER_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))
        return main_table
