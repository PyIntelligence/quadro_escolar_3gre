import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env local, se existir
load_dotenv()

class Config:
    # Segurança
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-trocar-em-producao')

    # Banco de Dados (Neon.tech / SQLite)
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    
    # Compatibilidade com prefixo antigo 'postgres://' em alguns PaaS
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Previne conexões mortas no Neon.tech (Postgres serverless)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Configurações do SMTP (Redefinição de Senha)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)

    # Credenciais e URLs de Integração (SIAGE e Metabase)
    SIAGE_BASE_URL = os.environ.get('SIAGE_BASE_URL')
    SIAGE_USER = os.environ.get('SIAGE_USER')
    SIAGE_PASSWORD = os.environ.get('SIAGE_PASSWORD')
    METABASE_URL = os.environ.get('METABASE_URL')