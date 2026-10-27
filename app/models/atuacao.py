from app.extensions import db

class Atuacao(db.Model):
    __tablename__ = 'atuacao'

    id = db.Column(db.Integer, primary_key=True)
    professor_id = db.Column(db.Integer, db.ForeignKey('professores.id'), nullable=False)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola_gestao.id'), nullable=False)
    componente_curricular = db.Column(db.String(150), nullable=False)
    atividade = db.Column(db.String(150), default='REGÊNCIA')
    turno = db.Column(db.String(50))
    etapa_modalidade = db.Column(db.String(100))
    area = db.Column(db.String(100))
    turmas_atendidas = db.Column(db.String(200))
    dias_atuacao = db.Column(db.String(100))
    ch_semanal = db.Column(db.Float, nullable=False, default=0.0)
    grupo_atuacao = db.Column(db.String(100))
    natureza_ch = db.Column(db.String(100))
    impacta_matriz = db.Column(db.Boolean, default=True)
    compoe_bloco_regencia = db.Column(db.Boolean, default=True)
    contabiliza_ch = db.Column(db.Boolean, default=True)
    observacoes = db.Column(db.Text)