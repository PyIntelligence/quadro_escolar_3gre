from app.extensions import db

class Profissional(db.Model):
    __tablename__ = 'profissionais'

    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola_gestao.id'), nullable=False)
    nome = db.Column(db.String(255), nullable=False)
    cargo = db.Column(db.String(100))
    matricula = db.Column(db.String(50))
    cpf = db.Column(db.String(20))
    email = db.Column(db.String(100))
    telefone = db.Column(db.String(50))

    def __repr__(self):
        return f'<Profissional {self.nome} - {self.cargo}>'