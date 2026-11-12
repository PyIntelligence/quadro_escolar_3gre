import os
from app import create_app
from flask_cors import CORS  # Importação adicionada

# Cria a instância da aplicação Flask usando a Application Factory
app = create_app()

# Habilita o CORS para a aplicação, permitindo requisições do seu frontend
CORS(app)

if __name__ == '__main__':
    # Configurações de execução (debug ligado apenas em desenvolvimento)
    debug = os.getenv('FLASK_DEBUG', 'True').lower() in ['true', '1']
    port = int(os.getenv('PORT', 5000))
    
    app.run(host='0.0.0.0', port=port, debug=debug)
