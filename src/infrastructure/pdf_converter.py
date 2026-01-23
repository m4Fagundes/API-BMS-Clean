"""
Infraestrutura para conversão de PDF em imagens.
"""
import io
import base64
import fitz  # PyMuPDF
from typing import Optional
from dataclasses import dataclass


@dataclass
class PageImage:
    """Representa uma página convertida em imagem."""
    page_number: int
    image_base64: str
    width: int
    height: int


class PdfConverter:
    """Responsável pela conversão de PDFs em imagens."""
    
    DEFAULT_DPI = 150
    DEFAULT_FORMAT = "png"
    
    @staticmethod
    def section_to_images(
        pdf_bytes: bytes,
        start_marker: str,
        end_marker: Optional[str] = None,
        dpi: int = 150
    ) -> list[PageImage]:
        """
        Converte uma seção do PDF em imagens PNG.
        
        Encontra as páginas que contêm o texto entre os marcadores
        e converte cada uma em imagem.
        
        Args:
            pdf_bytes: Bytes do arquivo PDF.
            start_marker: Texto que marca o início da seção.
            end_marker: Texto que marca o fim da seção (opcional).
            dpi: Resolução das imagens (default: 150).
            
        Returns:
            Lista de PageImage com as imagens em base64.
            
        Raises:
            ValueError: Se o marcador de início não for encontrado.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
            # Encontra páginas da seção
            start_page, end_page = PdfConverter._find_section_pages(
                doc, start_marker, end_marker
            )
            
            # Converte páginas em imagens
            images = []
            zoom = dpi / 72  # 72 é o DPI padrão do PDF
            matrix = fitz.Matrix(zoom, zoom)
            
            for page_num in range(start_page, end_page + 1):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=matrix)
                
                # Converte para PNG em memória
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                
                images.append(PageImage(
                    page_number=page_num + 1,  # 1-indexed para o usuário
                    image_base64=img_base64,
                    width=pix.width,
                    height=pix.height
                ))
            
            return images
            
        finally:
            doc.close()
    
    @staticmethod
    def pages_to_images(
        pdf_bytes: bytes,
        pages: Optional[list[int]] = None,
        dpi: int = 150
    ) -> list[PageImage]:
        """
        Converte páginas específicas do PDF em imagens PNG.
        
        Args:
            pdf_bytes: Bytes do arquivo PDF.
            pages: Lista de números de página (1-indexed). None = todas.
            dpi: Resolução das imagens (default: 150).
            
        Returns:
            Lista de PageImage com as imagens em base64.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
            # Define quais páginas processar
            if pages is None:
                page_indices = range(len(doc))
            else:
                page_indices = [p - 1 for p in pages if 0 < p <= len(doc)]
            
            images = []
            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            
            for page_num in page_indices:
                page = doc[page_num]
                pix = page.get_pixmap(matrix=matrix)
                
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                
                images.append(PageImage(
                    page_number=page_num + 1,
                    image_base64=img_base64,
                    width=pix.width,
                    height=pix.height
                ))
            
            return images
            
        finally:
            doc.close()
    
    @staticmethod
    def _find_section_pages(
        doc: fitz.Document,
        start_marker: str,
        end_marker: Optional[str]
    ) -> tuple[int, int]:
        """
        Encontra as páginas inicial e final da seção.
        
        Returns:
            Tupla (start_page, end_page) com índices 0-based.
        """
        start_page = None
        end_page = None
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            # Procura início
            if start_page is None and start_marker in text:
                start_page = page_num
            
            # Procura fim (se especificado)
            if start_page is not None and end_marker:
                if end_marker in text:
                    end_page = page_num
                    break
        
        if start_page is None:
            raise ValueError("Marcador de início não encontrado no documento.")
        
        # Se não encontrou fim, vai até a última página
        if end_page is None:
            end_page = len(doc) - 1
        
        return start_page, end_page
