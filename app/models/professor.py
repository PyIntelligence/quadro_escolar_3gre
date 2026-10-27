# app/models/professor.py

from app.extensions import db

class Professor(db.Model):
    __tablename__ = 'professores'

    # --- Identificadores e Chaves ---
    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola_gestao.id'), nullable=True)
    escola_inep = db.Column(db.String(20), index=True, nullable=True)
    
    # --- Dados Pessoais e Funcionais ---
    matricula = db.Column(db.String(30), index=True, nullable=True)
    cpf = db.Column(db.String(14), index=True, nullable=True)
    nome = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    telefone = db.Column(db.String(20), nullable=True)
    
    # --- Alocação e Atuação Docente ---
    cargo = db.Column(db.String(100), nullable=True)
    componente_curricular = db.Column(db.String(150), nullable=True)
    carga_horaria = db.Column(db.String(20), nullable=True)
    vinculo = db.Column(db.String(50), default='EFETIVO')
    situacao = db.Column(db.String(50), default='ATIVO')

    # --- Campos Específicos do Sistema ---
    utb_esta_escola = db.Column(db.String(10), default='SIM')
    utb_informada = db.Column(db.String(100))
    forma_atuacao = db.Column(db.String(150))
    carga_horaria_original = db.Column(db.Float, default=40.0)
    possui_ch_fora = db.Column(db.String(10), default='NÃO')
    outra_unidade = db.Column(db.String(150))
    ch_fora = db.Column(db.Float, default=0.0)
    conselho_escolar = db.Column(db.String(100))
    areas_planejamento = db.Column(db.String(150))
    dias_planejamento = db.Column(db.String(100))

    # --- Atos Legais e Autorizações ---
    reducao_legal_vigente = db.Column(db.String(10), default='NÃO')
    carga_horaria_autorizada = db.Column(db.Float, default=40.0)
    regencia_autorizada = db.Column(db.Float, nullable=True)
    ato_autorizacao = db.Column(db.String(100))
    fundamento_legal = db.Column(db.String(255))
    validade_ato = db.Column(db.Date, nullable=True)
    situacao_cadastro = db.Column(db.String(50), default='COMPLETO')
    observacoes = db.Column(db.Text)

    # --- Relacionamentos ORM ---
    atuacoes = db.relationship('Atuacao', backref='professor', cascade='all, delete-orphan')
    
    # Associação direta com EscolaGestao via back_populates
    escola = db.relationship('EscolaGestao', back_populates='professores')

    def __repr__(self):
        return f"<Professor {self.nome} - Matrícula: {self.matricula}>"