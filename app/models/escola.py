from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class EscolaGestao(db.Model):
    __tablename__ = 'escola_gestao'

    id = db.Column(db.Integer, primary_key=True)
    unidade_escolar = db.Column(db.String(255), nullable=False, default='ECIT ESCOLA MODELO - 3ª GRE')
    codigo_inep = db.Column(db.String(20), unique=True, nullable=False, index=True)
    gre = db.Column(db.String(50), default='3ª GRE')
    modalidade = db.Column(db.String(50))
    gestor = db.Column(db.String(255))

    # --- DADOS DE AUTENTICAÇÃO E SEGURANÇA ---
    senha_hash = db.Column(db.String(255), default=lambda: generate_password_hash('123456'))
    senha_alterada = db.Column(db.Boolean, default=False)
    is_gre = db.Column(db.Boolean, default=False)

    # --- DADOS DE LOCALIZAÇÃO E CONTATO DO SIAGE ---
    endereco = db.Column(db.String(300))
    municipio = db.Column(db.String(100), default='MUNICÍPIO MODELO')
    email = db.Column(db.String(100))
    telefone = db.Column(db.String(50))
    zona = db.Column(db.String(50))

    # --- HOMOLOGAÇÃO E RESPONSÁVEL PELO PREENCHIMENTO ---
    responsavel_preenchimento = db.Column(db.String(255))
    cargo_funcao = db.Column(db.String(100))
    confirmacao_responsavel = db.Column(db.String(50))
    status_confirmacao = db.Column(db.Boolean, default=False)
    data_confirmacao = db.Column(db.DateTime, nullable=True)
    observacoes = db.Column(db.Text)

    # --- DADOS GERAIS E COMPETÊNCIA ---
    qtd_professores = db.Column(db.Integer, default=0)
    qtd_turmas = db.Column(db.Integer, default=8)
    competencia = db.Column(db.String(50), default='AGOSTO/2026')
    ultima_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- GESTÃO E ORGANIZAÇÃO ---
    lideres_turma = db.Column(db.String(10))
    reconhecimento_conselho = db.Column(db.String(10))
    gremio_estudantil = db.Column(db.String(10))
    oferta_eja = db.Column(db.String(10))
    turnos_funcionamento = db.Column(db.String(50))
    conselho_escolar_ativo = db.Column(db.String(10))
    mandato_conselho_vigente = db.Column(db.String(10))
    seguranca_armada = db.Column(db.String(10))

    # --- SECRETARIA ESCOLAR ---
    situacao_secretario = db.Column(db.String(10))
    nome_secretario = db.Column(db.String(150))
    matricula_secretario = db.Column(db.String(20))
    telefone_secretario = db.Column(db.String(20))

    # --- COORDENAÇÃO PEDAGÓGICA ---
    qtd_coord_pedagogico = db.Column(db.Integer, default=0)
    coord_ped_1_nome = db.Column(db.String(150))
    coord_ped_1_mat = db.Column(db.String(20))
    coord_ped_1_tel = db.Column(db.String(20))
    coord_ped_2_nome = db.Column(db.String(150))
    coord_ped_2_mat = db.Column(db.String(20))
    coord_ped_2_tel = db.Column(db.String(20))

    # --- CAF / ASSESSOR FINANCEIRO ---
    situacao_caf = db.Column(db.String(10))
    nome_caf = db.Column(db.String(150))
    matricula_caf = db.Column(db.String(20))
    telefone_caf = db.Column(db.String(20))

    # --- REGIME DE PROGRESSÃO PARCIAL (RPP) ---
    situacao_rpp = db.Column(db.String(10))
    nome_rpp = db.Column(db.String(150))
    matricula_rpp = db.Column(db.String(20))
    telefone_rpp = db.Column(db.String(20))

    # --- RELACIONAMENTOS ---
    # professores = db.relationship('Professor', backref='escola', cascade='all, delete-orphan')
    professores = db.relationship('Professor', back_populates='escola', cascade='all, delete-orphan')
    apoio_clt = db.relationship('ApoioCLT', backref='escola', cascade='all, delete-orphan')
    planejamentos = db.relationship('PlanejamentoArea', backref='escola', cascade='all, delete-orphan')

    # --- MÉTODOS DE SEGURANÇA E AUTENTICAÇÃO DE SENHA ---
    def set_senha(self, nova_senha):
        self.senha_hash = generate_password_hash(nova_senha)
        self.senha_alterada = True

    def verificar_senha(self, senha):
        if not self.senha_hash:
            return False
        return check_password_hash(self.senha_hash, senha)

    # --- PROPRIEDADES E ALIASES ---
    @property
    def confirmado(self):
        return self.status_confirmacao or False

    @confirmado.setter
    def confirmado(self, val):
        self.status_confirmacao = bool(val)

    @property
    def inep(self):
        return self.codigo_inep

    @property
    def codigo(self):
        return self.codigo_inep


# Alias para manter compatibilidade com importações 'Escola'
Escola = EscolaGestao