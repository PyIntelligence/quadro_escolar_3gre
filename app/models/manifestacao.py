from app.extensions import db

class ManifestacaoComponente(db.Model):
    __tablename__ = 'manifestacao_componente'

    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola_gestao.id'), nullable=False)
    componente = db.Column(db.String(150), nullable=False)
    manifestacao = db.Column(db.String(255))
    justificativa = db.Column(db.Text)