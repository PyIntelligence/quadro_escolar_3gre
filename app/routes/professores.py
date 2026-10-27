# app/routes/professores.py

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from app.extensions import db
from app.models.professor import Professor

professores_bp = Blueprint('professores', __name__)


class EscolaView:
    """Wrapper para passagem segura de atributos de escola ao Jinja2."""
    def __init__(self, e_id, inep, nome):
        self.id = e_id
        self.inep_visual = str(inep or '').strip()
        self.codigo_inep = str(inep or '').strip()
        self.inep = str(inep or '').strip()
        self.nome = nome or "ESCOLA"
        self.unidade_escolar = nome or "ESCOLA"

    def __getattr__(self, name):
        return ""


@professores_bp.route('/professores', methods=['GET', 'POST'])
def professores():
    # Pega identificadores na URL, Formulário ou Sessão
    inep_req = (
        request.args.get('inep') or 
        request.args.get('codigo_inep') or 
        request.args.get('escola_id') or 
        request.args.get('id')
    )

    inep_sessao = (
        session.get('active_inep') or
        session.get('escola_inep') or 
        session.get('codigo_inep') or 
        session.get('inep') or 
        session.get('inep_selecionado') or
        session.get('escola_id')
    )

    escola_row = None
    alvo = inep_req or inep_sessao

    if alvo:
        val_str = str(alvo).strip()
        val_clean = val_str.lstrip('0')
        try:
            sql = db.text("""
                SELECT id, inep_visual, nome 
                FROM escola 
                WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :clean
                   OR TRIM(CAST(inep_visual AS VARCHAR)) = :raw
                   OR CAST(id AS VARCHAR) = :raw
                LIMIT 1
            """)
            escola_row = db.session.execute(sql, {"clean": val_clean, "raw": val_str}).fetchone()
        except Exception:
            db.session.rollback()

    if not escola_row:
        try:
            sql_f = db.text("SELECT id, inep_visual, nome FROM escola ORDER BY id LIMIT 1")
            escola_row = db.session.execute(sql_f).fetchone()
        except Exception:
            db.session.rollback()

    if escola_row:
        e_id, e_inep, e_nome = escola_row[0], str(escola_row[1] or '').strip(), str(escola_row[2] or '').strip()
    else:
        e_id, e_inep, e_nome = None, "", "ESCOLA"

    if e_inep:
        session.permanent = True
        session['active_inep'] = e_inep
        session['escola_inep'] = e_inep
        session['codigo_inep'] = e_inep
        session['inep'] = e_inep
        session['inep_selecionado'] = e_inep
        session['escola_id'] = e_id
        session['id'] = e_id
        session['escola_nome'] = e_nome

    escola_ativa = EscolaView(e_id, e_inep, e_nome)

    # Operações de POST (Adicionar / Excluir)
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add' and e_id:
            try:
                total_profs = db.session.query(db.func.count(Professor.id)).scalar() or 0
                novo_prof = Professor(
                    escola_id=e_id,
                    escola_inep=e_inep.lstrip('0') or None,
                    matricula=f"000.{total_profs + 1:03d}-0",
                    cpf="",
                    nome="NOVO PROFESSOR",
                    vinculo="EFETIVO",
                    utb_esta_escola="SIM",
                    utb_informada="",
                    forma_atuacao="CUMPRE INTEGRALMENTE A CH NESTA UNIDADE",
                    carga_horaria_original=40.0,
                    possui_ch_fora="NÃO",
                    outra_unidade_funcao="",
                    ch_fora=0.0,
                    conselho_escolar="NÃO PARTICIPA",
                    areas_planejamento="LINGUAGENS",
                    dias_planejamento="",
                    reducao_legal_vigente="NÃO",
                    carga_horaria_autorizada=40.0,
                    regencia_autorizada=0.0,
                    ato_autorizacao="",
                    fundamento_legal="",
                    validade_ato="",
                    situacao_cadastro="SIM",
                    observacoes=""
                )
                db.session.add(novo_prof)
                db.session.commit()
            except Exception:
                db.session.rollback()

            return redirect(url_for('professores.professores', inep=e_inep))

        elif action == 'delete':
            prof_id = request.form.get('id')
            if prof_id:
                try:
                    prof = Professor.query.get(prof_id)
                    if prof:
                        db.session.delete(prof)
                        db.session.commit()
                except Exception:
                    db.session.rollback()

            return redirect(url_for('professores.professores', inep=e_inep))

    # Carrega professores da escola no PostgreSQL
    registros = []
    if e_id or e_inep:
        clean_inep = e_inep.lstrip('0')
        try:
            sql_profs = db.text("""
                SELECT p.id 
                FROM professores p
                WHERE p.escola_id = :eid 
                   OR LTRIM(TRIM(CAST(p.escola_inep AS VARCHAR)), '0') = :inep
                   OR p.escola_id IN (
                       SELECT id FROM escola 
                       WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :inep
                   )
                ORDER BY p.nome
            """)
            p_ids = [r[0] for r in db.session.execute(sql_profs, {"eid": e_id, "inep": clean_inep}).fetchall()]
            if p_ids:
                registros = Professor.query.filter(Professor.id.in_(p_ids)).order_by(Professor.nome).all()
        except Exception:
            db.session.rollback()

    # Preenche o dropdown de escolas
    todas_escolas = []
    try:
        sql_todas = db.text("SELECT id, inep_visual, nome FROM escola ORDER BY nome")
        rows_todas = db.session.execute(sql_todas).fetchall()
        todas_escolas = [EscolaView(r[0], r[1], r[2]) for r in rows_todas]
    except Exception:
        db.session.rollback()

    return render_template(
        'professores.html',
        registros=registros,
        professores=registros,
        escola_ativa=escola_ativa,
        escola=escola_ativa,
        registro=escola_ativa,
        todas_escolas=todas_escolas,
        inep_selecionado=e_inep
    )


@professores_bp.route('/professores/atualizar_campo', methods=['POST'])
def atualizar_campo():
    """Salva instantaneamente a edição de qualquer célula da planilha no PostgreSQL."""
    data = request.get_json() or {}
    prof_id = data.get('id')
    campo = data.get('campo')
    valor = data.get('valor')

    if not prof_id or not campo:
        return jsonify({'sucesso': False, 'erro': 'Parâmetros inválidos'}), 400

    try:
        prof = Professor.query.get(prof_id)
        if not prof:
            return jsonify({'sucesso': False, 'erro': 'Professor não encontrado'}), 404

        # Tratamento de valores numéricos
        if campo in ['carga_horaria_original', 'ch_fora', 'carga_horaria_autorizada', 'regencia_autorizada']:
            try:
                valor = float(valor) if valor else 0.0
            except ValueError:
                valor = 0.0

        # Tratamento de aliases de atributos no modelo SQLAlchemy
        campos_para_tentar = [campo]
        if campo == 'outra_unidade_funcao':
            campos_para_tentar.append('outra_unidade')
        elif campo == 'outra_unidade':
            campos_para_tentar.append('outra_unidade_funcao')

        salvou = False
        for c in campos_para_tentar:
            if hasattr(prof, c):
                setattr(prof, c, valor)
                salvou = True

        if salvou:
            db.session.commit()
            return jsonify({'sucesso': True})

        # Fallback via SQL direto caso o atributo seja uma coluna física sem mapeamento ORM explícito
        for c in campos_para_tentar:
            try:
                sql_dyn = db.text(f"UPDATE professores SET {c} = :val WHERE id = :pid")
                db.session.execute(sql_dyn, {"val": valor, "pid": prof_id})
                db.session.commit()
                return jsonify({'sucesso': True})
            except Exception:
                db.session.rollback()

        return jsonify({'sucesso': False, 'erro': f'Campo {campo} não encontrado no modelo'}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500