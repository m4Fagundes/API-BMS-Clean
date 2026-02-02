import requests
import base64
import json
import sys

# URL da API
BASE_URL = "http://127.0.0.1:8000"
API_KEY = "minha-chave-secreta-123"

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def print_result(name, success, details=""):
    status = "✅ SUCESSO" if success else "❌ FALHA"
    print(f"{status} - {name} {details}")

def test_legacy_route():
    """Testa uma rota antiga (extract-toc)"""
    # Cria um PDF "vazio" válido em base64 (hello world)
    dummy_pdf_b64 = "JVBERi0xLjcKCjEgMCBvYmogICUgZW50cnkgcG9pbnQKPDwKICAvVHlwZSAvQ2F0YWxvZwogIC9QYWdlcyAyIDAgUgo+PgplbmRvYmoKCjIgMCBvYmogCjw8CiAgL1R5cGUgL1BhZ2VzCiAgL01lZGlhQm94IFsgMCAwIDIwMCAyMDAgXQogIC9Db3VudCAxCiAgL0tpZHMgWyAzIDAgUiBdCj4+CmVuZG9iagoMMyAwIG9iago8PAogIC9UeXBlIC9QYWdlCiAgL1BhcmVudCAyIDAgUgogIC9SZXNvdXJjZXMgPDwKICAgIC9Gb250IDw8CiAgICAgIC9FMSA0IDAgUgogICAgPj4KICA+PgogIC9Db250ZW50cyA1IDAgUgo+PgplbmRvYmoKCjQgMCBvYmogCjw8CiAgL1R5cGUgL0ZvbnQKICAvU3VidHlwZSAvVHlwZTEKICAvQmFzZUZvbnQgL0hlaHZldGljYQo+PgplbmRvYmoKCjUgMCBvYmogCjw8IC9MZW5ndGggNDQgPj4Kc3RyZWFtCkJUCjcwIDUwIFRECi9FMSAxMiBUZgooSGVsbG8gV29ybGQhKSBUagpFVAplbmRzdHJlYW0KZW5kb2JqCgp4cmVmCjAgNgowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMTAgMDAwMDAgbiAKMDAwMDAwMDA2MCAwMDAwMCBuIAowMDAwMDAwMTU3IDAwMDAwIG4gCjAwMDAwMDAyNTUgMDAwMDAgbiAKMDAwMDAwMDM0MSAwMDAwMCBuIAp0cmFpbGVyCjw8CiAgL1NpemUgNgogIC9Sb290IDEgMCBSCj4+CnN0YXJ0eHJlZgo0MzYKJSVFT0YK"
    
    payload = {
        "arquivo_base64": dummy_pdf_b64
    }
    
    try:
        response = requests.post(f"{BASE_URL}/extract-toc", json=payload, headers=HEADERS)
        if response.status_code == 200:
            print_result("Rota Legada (/extract-toc)", True, "(Retornou 200 OK)")
        else:
            print_result("Rota Legada (/extract-toc)", False, f"(Status: {response.status_code} - {response.text})")
    except Exception as e:
        print_result("Rota Legada (/extract-toc)", False, f"(Erro de conexão: {str(e)})")

def test_new_route():
    """Testa a nova rota (pages-to-base64)"""
    dummy_pdf_b64 = "JVBERi0xLjcKCjEgMCBvYmogICUgZW50cnkgcG9pbnQKPDwKICAvVHlwZSAvQ2F0YWxvZwogIC9QYWdlcyAyIDAgUgo+PgplbmRvYmoKCjIgMCBvYmogCjw8CiAgL1R5cGUgL1BhZ2VzCiAgL01lZGlhQm94IFsgMCAwIDIwMCAyMDAgXQogIC9Db3VudCAxCiAgL0tpZHMgWyAzIDAgUiBdCj4+CmVuZG9iagoMMyAwIG9iago8PAogIC9UeXBlIC9QYWdlCiAgL1BhcmVudCAyIDAgUgogIC9SZXNvdXJjZXMgPDwKICAgIC9Gb250IDw8CiAgICAgIC9FMSA0IDAgUgogICAgPj4KICA+PgogIC9Db250ZW50cyA1IDAgUgo+PgplbmRvYmoKCjQgMCBvYmogCjw8CiAgL1R5cGUgL0ZvbnQKICAvU3VidHlwZSAvVHlwZTEKICAvQmFzZUZvbnQgL0hlaHZldGljYQo+PgplbmRvYmoKCjUgMCBvYmogCjw8IC9MZW5ndGggNDQgPj4Kc3RyZWFtCkJUCjcwIDUwIFRECi9FMSAxMiBUZgooSGVsbG8gV29ybGQhKSBUagpFVAplbmRzdHJlYW0KZW5kb2JqCgp4cmVmCjAgNgowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMTAgMDAwMDAgbiAKMDAwMDAwMDA2MCAwMDAwMCBuIAowMDAwMDAwMTU3IDAwMDAwIG4gCjAwMDAwMDAyNTUgMDAwMDAgbiAKMDAwMDAwMDM0MSAwMDAwMCBuIAp0cmFpbGVyCjw8CiAgL1NpemUgNgogIC9Sb290IDEgMCBSCj4+CnN0YXJ0eHJlZgo0MzYKJSVFT0YK"

    payload = {
        "arquivo_base64": dummy_pdf_b64,
        "include_data_uri": True
    }

    try:
        response = requests.post(f"{BASE_URL}/pdf/pages-to-base64", json=payload, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            if "images" in data and len(data["images"]) > 0:
                print_result("Nova Rota (/pdf/pages-to-base64)", True, f"(Gerou {len(data['images'])} imagens)")
            else:
                print_result("Nova Rota (/pdf/pages-to-base64)", False, "(JSON inválido retornou)")
        else:
            print_result("Nova Rota (/pdf/pages-to-base64)", False, f"(Status: {response.status_code} - {response.text})")
    except Exception as e:
        print_result("Nova Rota (/pdf/pages-to-base64)", False, f"(Erro de conexão: {str(e)})")

if __name__ == "__main__":
    print("\n--- TESTANDO API BMS ---")
    
    # Teste de conectividade básica
    try:
        requests.get(BASE_URL)
        print("API Online: SIM")
    except:
        print("API Online: NÃO (Verifique se 'main.py' está rodando)")
        sys.exit(1)

    test_legacy_route()
    test_new_route()
    print("------------------------\n")
