from app.extensions import db

class Aula(db.Model):
    __tablename__ = 'aulas'

    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola_gestao.id'), nullable=True)
    professor_id = db.Column(db.Integer, db.ForeignKey('professores.id'), nullable=True)
    disciplina = db.Column(db.String(100))
    turma = db.Column(db.String(100))
    carga_horaria = db.Column(db.Integer, default=0)
    turno = db.Column(db.String(50))

    def __repr__(self):
        return f'<Aula {self.disciplina} - {self.turma}>'