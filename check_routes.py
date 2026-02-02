import sys
import os

# Adiciona o diretório atual ao path para importar corretamente
sys.path.append(os.getcwd())

from main import app

print("\n=== ROTAS REGISTRADAS ===")
for route in app.routes:
    methods = ", ".join(route.methods) if hasattr(route, "methods") else "None"
    print(f"{methods:20} {route.path}")
print("=========================\n")
