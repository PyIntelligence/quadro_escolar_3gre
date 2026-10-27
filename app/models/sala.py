from app.extensions import db

class Sala(db.Model):
    __tablename__ = 'salas'

    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola_gestao.id'), nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(100))
    capacidade = db.Column(db.Integer, default=0)
    metragem = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f'<Sala {self.nome}>'