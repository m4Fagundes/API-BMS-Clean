"""
Infraestrutura para conversão de PDF em imagens.
"""
import io
import base64
import struct
import fitz
from typing import Optional, Generator
from dataclasses import dataclass


@dataclass
class PageImage:
    """Representa uma página convertida em imagem."""
    page_number: int
    image_base64: str
    width: int
    height: int


@dataclass
class PageImageBytes:
    """Representa uma página convertida em imagem (bytes raw)."""
    page_number: int
    image_bytes: bytes
    width: int
    height: int


class PdfConverter:
    """Responsável pela conversão de PDFs em imagens."""
    
    DEFAULT_DPI = 150
    DEFAULT_FORMAT = "png"
    
    @staticmethod
    def get_page_count(pdf_bytes: bytes) -> int:
        """
        Retorna o número total de páginas do PDF.
        
        Args:
            pdf_bytes: Bytes do arquivo PDF.
            
        Returns:
            Número total de páginas.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            return len(doc)
        finally:
            doc.close()
    
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
        dpi: int = 150,
        img_format: str = "png",
        quality: int = 85,
        grayscale: bool = False,
        max_dimension: int = 0
    ) -> list[PageImage]:
        """
        Converte páginas específicas do PDF em imagens com processamento inteligente.
        
        Pipeline: Render alta res → Sharpen → Resize → Compress
        
        Args:
            pdf_bytes: Bytes do arquivo PDF.
            pages: Lista de números de página (1-indexed). None = todas.
            dpi: Resolução de renderização (default: 150).
            img_format: Formato: "png" ou "jpeg" (default: "png").
            quality: Qualidade JPEG 1-100 (default: 85).
            grayscale: Converte para escala de cinza (default: False).
            max_dimension: Dimensão máxima em pixels (0 = sem limite).
                          Redimensiona mantendo proporção. Útil para IA.
            
        Returns:
            Lista de PageImage com as imagens em base64.
        """
        from PIL import Image, ImageFilter
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
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
                
                # Converte pixmap para PIL Image
                img_data = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_data))
                
                # Converte para grayscale se solicitado
                if grayscale:
                    pil_img = pil_img.convert("L")
                
                # Pipeline de processamento para IA
                if max_dimension > 0:
                    w, h = pil_img.size
                    max_side = max(w, h)
                    
                    if max_side > max_dimension:
                        # Aplica sharpening ANTES de redimensionar
                        # para preservar texto e linhas finas
                        pil_img = pil_img.filter(ImageFilter.SHARPEN)
                        
                        # Redimensiona mantendo proporção com Lanczos (melhor para texto)
                        ratio = max_dimension / max_side
                        new_w = int(w * ratio)
                        new_h = int(h * ratio)
                        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                        
                        # Aplica UnsharpMask após resize para recuperar nitidez
                        # radius=2, percent=150, threshold=3
                        pil_img = pil_img.filter(
                            ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3)
                        )
                
                # Salva no formato desejado
                buffer = io.BytesIO()
                if img_format.lower() == "jpeg":
                    if pil_img.mode == "RGBA":
                        pil_img = pil_img.convert("RGB")
                    pil_img.save(buffer, format="JPEG", quality=quality, optimize=True)
                else:
                    pil_img.save(buffer, format="PNG", optimize=True)
                
                img_bytes = buffer.getvalue()
                img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                
                images.append(PageImage(
                    page_number=page_num + 1,
                    image_base64=img_base64,
                    width=pil_img.width,
                    height=pil_img.height
                ))
            
            return images
            
        finally:
            doc.close()
    
    @staticmethod
    def page_to_sections(
        pdf_bytes: bytes,
        page: int,
        rows: int = 2,
        cols: int = 2,
        dpi: int = 200
    ) -> list[PageImage]:
        """
        Divide uma página do PDF em seções (grid) com alta resolução.
        
        Args:
            pdf_bytes: Bytes do arquivo PDF.
            page: Número da página (1-indexed).
            rows: Número de linhas do grid (default: 2).
            cols: Número de colunas do grid (default: 2).
            dpi: Resolução das imagens (default: 200).
            
        Returns:
            Lista de PageImage, uma para cada seção.
        """
        from PIL import Image
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
            page_idx = page - 1
            if page_idx < 0 or page_idx >= len(doc):
                return []
            
            pdf_page = doc[page_idx]
            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            
            # Renderiza a página inteira em alta resolução
            full_pix = pdf_page.get_pixmap(matrix=matrix)
            
            # Converte para PIL para crop confiável
            full_img = Image.open(io.BytesIO(full_pix.tobytes("png")))
            full_w, full_h = full_img.size
            
            section_w = full_w // cols
            section_h = full_h // rows
            
            sections = []
            section_num = 0
            
            for r in range(rows):
                for c in range(cols):
                    section_num += 1
                    
                    x0 = c * section_w
                    y0 = r * section_h
                    x1 = full_w if c == cols - 1 else (c + 1) * section_w
                    y1 = full_h if r == rows - 1 else (r + 1) * section_h
                    
                    # Recorta usando PIL
                    section_img = full_img.crop((x0, y0, x1, y1))
                    
                    buffer = io.BytesIO()
                    section_img.save(buffer, format="PNG")
                    img_bytes = buffer.getvalue()
                    img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                    
                    sections.append(PageImage(
                        page_number=section_num,
                        image_base64=img_base64,
                        width=section_img.width,
                        height=section_img.height
                    ))
            
            return sections
            
        finally:
            doc.close()
    
    @staticmethod
    def pages_to_images_bytes(
        pdf_bytes: bytes,
        pages: Optional[list[int]] = None,
        dpi: int = 150
    ) -> Generator[PageImageBytes, None, None]:
        """
        Generator que converte páginas do PDF em imagens PNG (bytes raw).
        
        Processa página por página sem acumular em memória.
        Ideal para streaming e transferência entre APIs.
        
        Args:
            pdf_bytes: Bytes do arquivo PDF.
            pages: Lista de números de página (1-indexed). None = todas.
            dpi: Resolução das imagens (default: 150).
            
        Yields:
            PageImageBytes com os bytes da imagem PNG.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        try:
            # Define quais páginas processar
            if pages is None:
                page_indices = range(len(doc))
            else:
                page_indices = [p - 1 for p in pages if 0 < p <= len(doc)]
            
            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            
            for page_num in page_indices:
                page = doc[page_num]
                pix = page.get_pixmap(matrix=matrix)
                
                img_bytes = pix.tobytes("png")
                
                yield PageImageBytes(
                    page_number=page_num + 1,
                    image_bytes=img_bytes,
                    width=pix.width,
                    height=pix.height
                )
                
        finally:
            doc.close()
    
    @staticmethod
    def pages_to_stream(
        pdf_bytes: bytes,
        pages: Optional[list[int]] = None,
        dpi: int = 150
    ) -> Generator[bytes, None, None]:
        """
        Generator que produz stream binário das imagens.
        
        Formato do stream por imagem:
        - 4 bytes: número da página (uint32 big-endian)
        - 4 bytes: largura (uint32 big-endian)
        - 4 bytes: altura (uint32 big-endian)
        - 4 bytes: tamanho dos bytes da imagem (uint32 big-endian)
        - N bytes: bytes da imagem PNG
        
        Args:
            pdf_bytes: Bytes do arquivo PDF.
            pages: Lista de números de página (1-indexed). None = todas.
            dpi: Resolução das imagens (default: 150).
            
        Yields:
            Chunks de bytes para streaming.
        """
        for img in PdfConverter.pages_to_images_bytes(pdf_bytes, pages, dpi):
            # Header: page_number, width, height, size (cada um 4 bytes)
            header = struct.pack(
                ">IIII",
                img.page_number,
                img.width,
                img.height,
                len(img.image_bytes)
            )
            yield header
            yield img.image_bytes
    
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
