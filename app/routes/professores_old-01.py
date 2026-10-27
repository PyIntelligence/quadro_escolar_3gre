# app/routes/professores.py

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.extensions import db

# --- Importação Dinâmica e Segura dos Modelos ---
try:
    from app.models.escola import EscolaGestao as Escola
except ImportError:
    try:
        from app.models.escola import Escola
    except ImportError:
        Escola = None

try:
    from app.models.professor import Professor
except ImportError:
    try:
        from app.models.profissional import Profissional as Professor
    except ImportError:
        Professor = None

try:
    from app.models.aula import Aula
except ImportError:
    Aula = None

from app.utils.helpers import normalizar_texto, limpar_float

professores_bp = Blueprint('professores', __name__)


def obter_escola_atual():
    if not Escola:
        return None

    escola_obj = None

    inep_req = (
        request.args.get('inep') 
        or request.args.get('codigo_inep') 
        or request.form.get('codigo_inep_seletor')
    )
    id_req = (
        request.args.get('escola_id') 
        or request.form.get('escola_id')
    )

    if inep_req:
        try:
            escola_obj = Escola.query.filter(
                (getattr(Escola, 'codigo_inep', None) == str(inep_req)) |
                (getattr(Escola, 'inep', None) == str(inep_req))
            ).first()
        except Exception:
            db.session.rollback()

    if not escola_obj and id_req:
        try:
            escola_obj = Escola.query.get(int(id_req))
        except Exception:
            db.session.rollback()

    if not escola_obj:
        escola_id_sessao = session.get('escola_id')
        if escola_id_sessao:
            try:
                escola_obj = Escola.query.get(int(escola_id_sessao))
            except Exception:
                db.session.rollback()

    if not escola_obj:
        try:
            escola_obj = Escola.query.order_by(Escola.id).first()
        except Exception:
            db.session.rollback()

    if escola_obj:
        session.permanent = True
        session['escola_id'] = escola_obj.id
        inep_val = getattr(escola_obj, 'codigo_inep', getattr(escola_obj, 'inep', str(escola_obj.id)))
        session['inep_selecionado'] = inep_val

    return escola_obj


def converter_data(data_str):
    if not data_str:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(data_str.strip(), fmt).date()
        except ValueError:
            pass
    return None


def limpar_float_seguro(valor, padrao=0.0):
    if valor is None or str(valor).strip() == '':
        return padrao
    try:
        return float(str(valor).replace(',', '.').strip())
    except ValueError:
        return padrao


@professores_bp.route('/step4', methods=['GET', 'POST'], endpoint='step4')
@professores_bp.route('/professores', methods=['GET', 'POST'], endpoint='professores')
def step4():
    escola_atual = obter_escola_atual()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add' and escola_atual:
            matricula = request.form.get('matricula', '').strip()
            nome = request.form.get('nome', '').strip().upper()

            if not matricula or not nome:
                flash('Matrícula e Nome são obrigatórios!', 'danger')
                return redirect(url_for('professores.step4'))

            novo_prof = Professor() if Professor else None
            if novo_prof:
                if hasattr(novo_prof, 'escola_id'):
                    novo_prof.escola_id = escola_atual.id
                
                inep_val = getattr(escola_atual, 'codigo_inep', getattr(escola_atual, 'inep', None))
                if hasattr(novo_prof, 'escola_inep') and inep_val:
                    novo_prof.escola_inep = str(inep_val)

                if hasattr(novo_prof, 'matricula'): novo_prof.matricula = matricula
                if hasattr(novo_prof, 'cpf'): novo_prof.cpf = request.form.get('cpf', '').strip()
                if hasattr(novo_prof, 'nome'): novo_prof.nome = nome
                if hasattr(novo_prof, 'vinculo'): novo_prof.vinculo = request.form.get('vinculo', 'EFETIVO')
                if hasattr(novo_prof, 'utb_esta_escola'): novo_prof.utb_esta_escola = request.form.get('utb_esta_escola', 'SIM')
                if hasattr(novo_prof, 'utb_informada'): novo_prof.utb_informada = request.form.get('utb_informada', '').strip().upper()
                if hasattr(novo_prof, 'forma_atuacao'): novo_prof.forma_atuacao = request.form.get('forma_atuacao', '')
                if hasattr(novo_prof, 'carga_horaria_original'): novo_prof.carga_horaria_original = limpar_float_seguro(request.form.get('carga_horaria_original'), 40.0)
                if hasattr(novo_prof, 'possui_ch_fora'): novo_prof.possui_ch_fora = request.form.get('possui_ch_fora', 'NÃO')
                if hasattr(novo_prof, 'outra_unidade'): novo_prof.outra_unidade = request.form.get('outra_unidade', '').strip().upper()
                if hasattr(novo_prof, 'ch_fora'): novo_prof.ch_fora = limpar_float_seguro(request.form.get('ch_fora'), 0.0)
                if hasattr(novo_prof, 'conselho_escolar'): novo_prof.conselho_escolar = request.form.get('conselho_escolar', 'NÃO PARTICIPA')
                if hasattr(novo_prof, 'areas_planejamento'): novo_prof.areas_planejamento = request.form.get('areas_planejamento', '')
                if hasattr(novo_prof, 'dias_planejamento'): novo_prof.dias_planejamento = request.form.get('dias_planejamento', '').strip().upper()
                if hasattr(novo_prof, 'reducao_legal_vigente'): novo_prof.reducao_legal_vigente = request.form.get('reducao_legal_vigente', 'NÃO')
                if hasattr(novo_prof, 'carga_horaria_autorizada'): novo_prof.carga_horaria_autorizada = limpar_float_seguro(request.form.get('carga_horaria_autorizada'), 40.0)
                
                if hasattr(novo_prof, 'regencia_autorizada'):
                    regencia = request.form.get('regencia_autorizada')
                    novo_prof.regencia_autorizada = limpar_float_seguro(regencia, None) if regencia else None
                
                if hasattr(novo_prof, 'ato_autorizacao'): novo_prof.ato_autorizacao = request.form.get('ato_autorizacao', '').strip().upper()
                if hasattr(novo_prof, 'fundamento_legal'): novo_prof.fundamento_legal = request.form.get('fundamento_legal', '').strip().upper()
                if hasattr(novo_prof, 'validade_ato'): novo_prof.validade_ato = converter_data(request.form.get('validade_ato'))
                if hasattr(novo_prof, 'situacao_cadastro'): novo_prof.situacao_cadastro = request.form.get('situacao_cadastro', 'SIM')
                if hasattr(novo_prof, 'observacoes'): novo_prof.observacoes = request.form.get('observacoes', '').strip().upper()

                try:
                    db.session.add(novo_prof)
                    db.session.commit()
                    flash(f'Professor {nome} cadastrado com sucesso!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Erro ao cadastrar professor: {str(e)}', 'danger')

            return redirect(url_for('professores.step4'))

        elif action == 'delete' and escola_atual:
            prof_id = request.form.get('id')
            if prof_id and Professor:
                prof = Professor.query.filter_by(id=prof_id).first()
                if prof:
                    try:
                        db.session.delete(prof)
                        db.session.commit()
                        flash('Professor removido com sucesso!', 'info')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Erro ao remover professor: {str(e)}', 'danger')
            return redirect(url_for('professores.step4'))

    # BUSCA ABRANGENTE DE PROFESSORES (Filtra por escola_id OU por escola_inep)
    lista_professores = []
    if Professor and escola_atual:
        try:
            inep_val = str(getattr(escola_atual, 'codigo_inep', getattr(escola_atual, 'inep', '')))
            
            condicoes = [Professor.escola_id == escola_atual.id]
            if hasattr(Professor, 'escola_inep') and inep_val:
                condicoes.append(Professor.escola_inep == inep_val)

            lista_professores = Professor.query.filter(db.or_(*condicoes)).all()
        except Exception:
            db.session.rollback()

    return render_template(
        'professores.html',
        escola=escola_atual,
        registros=lista_professores,
        professores=lista_professores
    )


@professores_bp.route('/step4_edit/<int:prof_id>', methods=['GET', 'POST'])
def editar_professor(prof_id):
    escola_atual = obter_escola_atual()
    if not escola_atual or not Professor:
        flash('Nenhuma escola ativa.', 'warning')
        return redirect(url_for('professores.step4'))

    professor = Professor.query.filter_by(id=prof_id).first_or_404()

    if request.method == 'POST':
        for campo in request.form:
            if hasattr(professor, campo) and campo not in ['id', 'escola_id', 'csrf_token']:
                val = request.form.get(campo)
                if 'carga_horaria' in campo or 'ch_' in campo or campo == 'regencia_autorizada':
                    setattr(professor, campo, limpar_float_seguro(val))
                elif 'validade' in campo or 'data' in campo:
                    setattr(professor, campo, converter_data(val))
                else:
                    setattr(professor, campo, val.strip().upper() if isinstance(val, str) else val)

        try:
            db.session.commit()
            flash('Dados do docente atualizados com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar professor: {str(e)}', 'danger')

        return redirect(url_for('professores.step4'))

    return render_template('step4_edit.html', professor=professor, escola=escola_atual)