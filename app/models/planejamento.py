from app.extensions import db

class PlanejamentoArea(db.Model):
    __tablename__ = 'planejamento_area'

    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola_gestao.id'), nullable=False)
    area_conhecimento = db.Column(db.String(100), nullable=False)
    dia_semana = db.Column(db.String(50), nullable=False)
    horario_inicio = db.Column(db.Time, nullable=True)
    horario_fim = db.Column(db.Time, nullable=True)
    turnos = db.Column(db.String(50))
    responsavel_articulador = db.Column(db.String(255))
    observacoes = db.Column(db.Text)