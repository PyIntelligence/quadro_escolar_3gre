import os
from flask import Flask
from dotenv import load_dotenv
from app.config import Config
from app.extensions import db

# Carrega as variáveis do arquivo .env com codificação UTF-8
load_dotenv(encoding='utf-8')


def create_app(config_class=Config):
    # Instancia o Flask utilizando o padrão do pacote (procura em app/templates e app/static)
    app = Flask(__name__)
    
    # Carrega as configurações principais (chaves, URIs de banco, etc.)
    app.config.from_object(config_class)

    # --- TRATAMENTO DE ENCODING NO POSTGRESQL ---
    # Adiciona 'client_encoding=utf8' à URI para evitar UnicodeDecodeError no psycopg2 no Windows
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_uri and 'postgresql' in db_uri and 'client_encoding' not in db_uri:
        separador = '&' if '?' in db_uri else '?'
        app.config['SQLALCHEMY_DATABASE_URI'] = f"{db_uri}{separador}client_encoding=utf8"

    # --- GARANTIA DE SESSÃO E SEGURANÇA ---
    # Garante a existência de uma SECRET_KEY para persistir sessions/cookies
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or 'chave_secreta_desenvolvimento_3gre_2026_super_segura'
    
    # Ajustes nos cookies de sessão para navegação via IP da rede local (ex: http://192.168.1.71:5000)
    app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
    app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config.setdefault('SESSION_COOKIE_SECURE', False)  # Desativado para conexões HTTP locais

    # Inicializa o SQLAlchemy com o app
    db.init_app(app)

    # --- IMPORTAÇÃO E REGISTRO DOS BLUEPRINTS ---
    from app.routes.auth import auth_bp
    from app.routes.escolas import escolas_bp
    from app.routes.professores import professores_bp
    from app.routes.apoio import apoio_bp
    from app.routes.planejamento import planejamento_bp
    from app.routes.atuacao import atuacao_bp
    from app.routes.api import api_bp
    from app.routes.quadro_informado import quadro_informado_bp
    from app.routes.quadro_escolar import quadro_escolar_bp
    from app.routes.conferencia_final import conferencia_final_bp
    from app.routes.confirmacao_final import confirmacao_final_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(escolas_bp)
    app.register_blueprint(planejamento_bp)
    app.register_blueprint(professores_bp)
    app.register_blueprint(apoio_bp)
    app.register_blueprint(atuacao_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(quadro_informado_bp)
    app.register_blueprint(quadro_escolar_bp)
    app.register_blueprint(conferencia_final_bp)
    app.register_blueprint(confirmacao_final_bp)

    # --- CRIAÇÃO DE TABELAS E MAPEAMENTO DE MODELOS ---
    with app.app_context():
        try:
            from app.models.escola import Escola
            from app.models.sala import Sala
            from app.models.profissional import Profissional
        except ImportError:
            pass

        try:
            db.create_all()
        except Exception as e:
            print(f"Aviso na inicialização do db.create_all(): {e}")

    return app