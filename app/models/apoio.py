# app/models/apoio.py

from datetime import datetime
from app.extensions import db

try:
    from app.models.escola import Escola
except ImportError:
    from app.models.escola import EscolaGestao as Escola


class ApoioCLT(db.Model):
    __tablename__ = 'apoio_clt'

    id = db.Column(db.Integer, primary_key=True)
    
    # Chave estrangeira vinculada à Escola
    escola_id = db.Column(db.Integer, db.ForeignKey(Escola.id), nullable=False)
    
    cpf = db.Column(db.String(14), nullable=False, index=True)
    nome = db.Column(db.String(150), nullable=False)
    registro_empresa = db.Column(db.String(50))
    empresa_contrato = db.Column(db.String(150), nullable=False)
    funcao_contratada = db.Column(db.String(100), nullable=False)
    funcao_exercida = db.Column(db.String(100), nullable=False)
    setor_atuacao = db.Column(db.String(100), nullable=False)
    atividade_principal = db.Column(db.String(200))
    carga_horaria = db.Column(db.Integer, default=40)
    turnos = db.Column(db.String(50), nullable=False)
    dias = db.Column(db.String(50), nullable=False)
    telefone = db.Column(db.String(20))
    data_inicio = db.Column(db.Date)
    situacao = db.Column(db.String(50), default='EM EXERCÍCIO')
    observacoes = db.Column(db.Text)
    conferencia = db.Column(db.String(50), default='CONFORME DECLARADO')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ApoioCLT {self.nome} - {self.cpf}>"