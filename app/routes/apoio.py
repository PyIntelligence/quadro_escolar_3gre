from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.extensions import db

# Importação dos Modelos com Fallback
try:
    from app.models.escola import Escola
except ImportError:
    from app.models.escola import EscolaGestao as Escola

try:
    from app.models.apoio import ApoioCLT
except ImportError:
    try:
        from app.models.apoio_clt import ApoioCLT
    except ImportError:
        ApoioCLT = None

try:
    from app.models.profissional import Profissional
except ImportError:
    Profissional = None

from app.utils.helpers import normalizar_texto, limpar_float

apoio_bp = Blueprint('apoio', __name__)


def buscar_escola_por_inep(inep_val):
    """
    Busca a escola garantindo rollback em caso de falha de coluna/transação.
    Prioriza 'codigo_inep' (da tabela escola_gestao) e trata falhas de SQL.
    """
    if not inep_val:
        return None

    inep_str = str(inep_val).strip().lstrip('0')

    # 1. Tenta via ORM testando os nomes de atributo mais comuns
    try:
        for attr in ['codigo_inep', 'inep_visual', 'inep']:
            if hasattr(Escola, attr):
                col = getattr(Escola, attr)
                escola = Escola.query.filter(db.cast(col, db.String).like(f"%{inep_str}%")).first()
                if escola:
                    return escola
    except Exception:
        db.session.rollback()

    # 2. Tenta via SQL direto com rollback explícito se uma tabela/coluna não existir
    buscas = [
        ("escola_gestao", "codigo_inep"),
        ("escola_gestao", "inep_visual"),
        ("escola", "codigo_inep"),
        ("escola", "inep_visual")
    ]

    for tabela, col in buscas:
        try:
            sql = db.text(f"""
                SELECT id FROM {tabela} 
                WHERE LTRIM(TRIM(CAST({col} AS VARCHAR)), '0') = :inep
                   OR CAST({col} AS VARCHAR) LIKE :inep_like
                LIMIT 1
            """)
            row = db.session.execute(sql, {"inep": inep_str, "inep_like": f"%{inep_str}%"}).fetchone()
            if row and row[0]:
                escola_obj = Escola.query.get(row[0])
                if escola_obj:
                    return escola_obj
        except Exception:
            db.session.rollback()

    return None


def obter_escola_atual():
    """Recupera a escola ativa da URL (INEP) ou da sessão de forma segura."""
    escola_id = session.get('escola_id')
    inep = request.args.get('inep') or request.form.get('inep')

    # Se recebeu o parâmetro INEP, resolve e atualiza a sessão
    if inep:
        escola = buscar_escola_por_inep(inep)
        if escola:
            session['escola_id'] = escola.id
            return escola

    # Se já existir ID na sessão, recupera a escola
    if escola_id:
        try:
            escola = Escola.query.get(escola_id)
            if escola:
                return escola
        except Exception:
            db.session.rollback()

    return None


@apoio_bp.route('/step5', methods=['GET', 'POST'], endpoint='step5')
@apoio_bp.route('/apoio_clt', methods=['GET', 'POST'], endpoint='apoio_clt')
def apoio_clt():
    escola = obter_escola_atual()

    if not escola:
        flash('Selecione uma escola válida para acessar o Apoio CLT.', 'warning')
        inep_param = request.args.get('inep')
        if inep_param:
            return redirect(url_for('escolas.index', inep=inep_param))
        return redirect('/escolas')

    inep_param = (
        request.args.get('inep')
        or request.form.get('inep')
        or getattr(escola, 'codigo_inep', getattr(escola, 'inep_visual', getattr(escola, 'inep', '')))
    )

    if request.method == 'POST':
        action = request.form.get('action')

        # Cadastrar Novo Profissional CLT
        if action == 'add':
            dt_inicio = None
            raw_dt = request.form.get('data_inicio')
            if raw_dt:
                try:
                    dt_inicio = datetime.strptime(raw_dt, '%Y-%m-%d').date()
                except ValueError:
                    pass

            if ApoioCLT:
                try:
                    novo_terceirizado = ApoioCLT(
                        escola_id=escola.id,
                        cpf=request.form.get('cpf', '').strip(),
                        nome=normalizar_texto(request.form.get('nome', '')),
                        registro_empresa=normalizar_texto(request.form.get('registro_empresa', '')),
                        empresa_contrato=normalizar_texto(request.form.get('empresa_contrato', '')),
                        funcao_contratada=normalizar_texto(request.form.get('funcao_contratada', '')),
                        funcao_exercida=normalizar_texto(request.form.get('funcao_exercida', '')),
                        setor_atuacao=normalizar_texto(request.form.get('setor_atuacao', '')),
                        atividade_principal=normalizar_texto(request.form.get('atividade_principal', '')),
                        carga_horaria=int(limpar_float(request.form.get('carga_horaria', '40')) or 40),
                        turnos=normalizar_texto(request.form.get('turnos', '')),
                        dias=normalizar_texto(request.form.get('dias', '')),
                        telefone=request.form.get('telefone', '').strip(),
                        data_inicio=dt_inicio,
                        situacao=normalizar_texto(request.form.get('situacao', 'EM EXERCÍCIO')),
                        observacoes=normalizar_texto(request.form.get('observacoes', '')),
                        conferencia='CONFORME DECLARADO'
                    )
                    db.session.add(novo_terceirizado)
                    db.session.commit()
                    flash('Profissional terceirizado cadastrado com sucesso!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Erro ao cadastrar profissional: {str(e)}', 'danger')

        # Excluir Registro
        elif action == 'delete':
            reg_id = request.form.get('id')
            if reg_id and ApoioCLT:
                try:
                    reg = ApoioCLT.query.filter_by(id=reg_id, escola_id=escola.id).first()
                    if reg:
                        db.session.delete(reg)
                        db.session.commit()
                        flash('Registro removido com sucesso!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Erro ao excluir registro: {str(e)}', 'danger')

        # Atualização em Lote Legada
        else:
            prof_ids = request.form.getlist('prof_id[]')
            funcoes = request.form.getlist('funcao[]')
            cargas = request.form.getlist('carga_horaria[]')

            if prof_ids and Profissional:
                try:
                    for p_id, func, carga in zip(prof_ids, funcoes, cargas):
                        prof = Profissional.query.get(p_id)
                        if prof and prof.escola_id == escola.id:
                            prof.funcao = normalizar_texto(func)
                            prof.carga_horaria = limpar_float(carga)

                    db.session.commit()
                    flash('Equipe de apoio atualizada com sucesso!', 'success')
                except Exception:
                    db.session.rollback()

        return redirect(url_for('apoio.apoio_clt', inep=inep_param))

    # Busca registros do PostgreSQL
    registros = []
    if ApoioCLT:
        try:
            registros = ApoioCLT.query.filter_by(escola_id=escola.id).order_by(ApoioCLT.nome.asc()).all()
        except Exception:
            db.session.rollback()

    equipe_apoio = []
    if Profissional:
        try:
            equipe_apoio = Profissional.query.filter_by(escola_id=escola.id).all()
        except Exception:
            db.session.rollback()

    return render_template(
        'apoio_clt.html',
        escola=escola,
        inep=inep_param,
        registros=registros,
        equipe_apoio=equipe_apoio
    )


@apoio_bp.route('/resumo', methods=['GET'])
def resumo():
    escola = obter_escola_atual()

    if not escola:
        flash('Selecione uma escola válida.', 'warning')
        return redirect('/')

    return render_template('resumo.html', escola=escola)