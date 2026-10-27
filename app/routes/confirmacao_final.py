# app/routes/confirmacao_final.py

from flask import Blueprint, render_template, request, session, redirect, url_for
from datetime import datetime
from app.extensions import db
from app.models.professor import Professor

confirmacao_final_bp = Blueprint('confirmacao_final', __name__)


class EscolaView:
    """Wrapper para passagem segura de atributos de escola ao Jinja2."""
    def __init__(self, e_id, inep, nome, gestor="", responsavel="", cargo="", status_conf=False, dt_conf=None):
        self.id = e_id
        self.inep_visual = str(inep or '').strip()
        self.codigo_inep = str(inep or '').strip()
        self.inep = str(inep or '').strip()
        self.nome = nome or "ESCOLA"
        self.unidade_escolar = nome or "ESCOLA"
        self.gestor = gestor or "NÃO INFORMADO"
        self.responsavel_preenchimento = responsavel or ""
        self.cargo_funcao = cargo or ""
        self.status_confirmacao = status_conf
        self.data_confirmacao = dt_conf
        self.confirmacao_responsavel = "HOMOLOGADO" if status_conf else "PENDENTE"
        self.gre = "3ª GRE"

    def __getattr__(self, name):
        return ""


def garantir_colunas_escola():
    """Cria automaticamente as colunas de homologação no PostgreSQL se ainda não existirem."""
    try:
        sql_alter = db.text("""
            ALTER TABLE escola ADD COLUMN IF NOT EXISTS gestor VARCHAR(255);
            ALTER TABLE escola ADD COLUMN IF NOT EXISTS responsavel_preenchimento VARCHAR(255);
            ALTER TABLE escola ADD COLUMN IF NOT EXISTS cargo_funcao VARCHAR(255);
            ALTER TABLE escola ADD COLUMN IF NOT EXISTS status_confirmacao BOOLEAN DEFAULT FALSE;
            ALTER TABLE escola ADD COLUMN IF NOT EXISTS data_confirmacao TIMESTAMP;
        """)
        db.session.execute(sql_alter)
        db.session.commit()
    except Exception as e:
        db.session.rollback()


@confirmacao_final_bp.route('/confirmacao_final', methods=['GET', 'POST'])
def confirmacao_final():
    # 0. Garante estrutura de colunas na tabela escola
    garantir_colunas_escola()

    # 1. Recupera o INEP da URL ou da Sessão Ativa
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
                SELECT id, inep_visual, nome, 
                       COALESCE(gestor, ''), 
                       COALESCE(responsavel_preenchimento, ''), 
                       COALESCE(cargo_funcao, ''), 
                       COALESCE(status_confirmacao, FALSE), 
                       data_confirmacao
                FROM escola 
                WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :clean
                   OR TRIM(CAST(inep_visual AS VARCHAR)) = :raw
                   OR CAST(id AS VARCHAR) = :raw
                LIMIT 1
            """)
            escola_row = db.session.execute(sql, {"clean": val_clean, "raw": val_str}).fetchone()
        except Exception as e:
            print(f"[ERRO CONFIRMAÇÃO FINAL - BUSCA ESCOLA]: {e}")
            db.session.rollback()

    if not escola_row:
        try:
            sql_f = db.text("""
                SELECT id, inep_visual, nome, 
                       COALESCE(gestor, ''), 
                       COALESCE(responsavel_preenchimento, ''), 
                       COALESCE(cargo_funcao, ''), 
                       COALESCE(status_confirmacao, FALSE), 
                       data_confirmacao
                FROM escola 
                ORDER BY id LIMIT 1
            """)
            escola_row = db.session.execute(sql_f).fetchone()
        except Exception as e:
            print(f"[ERRO CONFIRMAÇÃO FINAL - ESCOLA FALLBACK]: {e}")
            db.session.rollback()

    if escola_row:
        e_id = escola_row[0]
        e_inep = str(escola_row[1] or '').strip()
        e_nome = str(escola_row[2] or '').strip()
        e_gestor = str(escola_row[3] or '').strip()
        e_resp = str(escola_row[4] or '').strip()
        e_cargo = str(escola_row[5] or '').strip()
        e_status = bool(escola_row[6]) if escola_row[6] is not None else False
        e_dt = escola_row[7]
    else:
        e_id, e_inep, e_nome, e_gestor, e_resp, e_cargo, e_status, e_dt = None, "", "ESCOLA", "", "", "", False, None

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

    escola_ativa = EscolaView(e_id, e_inep, e_nome, e_gestor, e_resp, e_cargo, e_status, e_dt)

    # Trata Submissão do Formulário de Homologação / Reabertura
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'confirmar' and e_id:
            resp_nome = request.form.get('responsavel_final', '').strip().upper()
            cargo_nome = request.form.get('cargo_funcao', '').strip().upper()
            now_dt = datetime.now()
            try:
                sql_up = db.text("""
                    UPDATE escola 
                    SET status_confirmacao = TRUE,
                        data_confirmacao = :dt,
                        responsavel_preenchimento = :resp,
                        cargo_funcao = :cargo
                    WHERE id = :eid
                """)
                db.session.execute(sql_up, {
                    "dt": now_dt,
                    "resp": resp_nome,
                    "cargo": cargo_nome,
                    "eid": e_id
                })
                db.session.commit()
            except Exception as e:
                print(f"[ERRO HOMOLOGAÇÃO]: {e}")
                db.session.rollback()

            return redirect(url_for('confirmacao_final.confirmacao_final', inep=e_inep))

        elif action == 'reabrir' and e_id:
            try:
                sql_reopen = db.text("""
                    UPDATE escola 
                    SET status_confirmacao = FALSE,
                        data_confirmacao = NULL
                    WHERE id = :eid
                """)
                db.session.execute(sql_reopen, {"eid": e_id})
                db.session.commit()
            except Exception as e:
                print(f"[ERRO REABERTURA]: {e}")
                db.session.rollback()

            return redirect(url_for('confirmacao_final.confirmacao_final', inep=e_inep))

    # 2. Consolidação de Indicadores para Snapshot
    total_professores = 0
    total_ch_autorizada = 0
    total_ch_alocada = 0

    if e_id or e_inep:
        clean_inep = e_inep.lstrip('0')
        try:
            sql_profs = db.text("""
                SELECT p.id, COALESCE(p.carga_horaria_autorizada, p.carga_horaria_original, 40)
                FROM professores p
                WHERE p.escola_id = :eid 
                   OR LTRIM(TRIM(CAST(p.escola_inep AS VARCHAR)), '0') = :inep
                   OR p.escola_id IN (
                       SELECT id FROM escola 
                       WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :inep
                   )
            """)
            r_profs = db.session.execute(sql_profs, {"eid": e_id, "inep": clean_inep}).fetchall()
            total_professores = len(r_profs)
            for r in r_profs:
                total_ch_autorizada += int(r[1] or 40)
        except Exception as e:
            print(f"[ERRO PROFESSORES CONFIRMAÇÃO]: {e}")
            db.session.rollback()

        try:
            sql_ch_at = db.text("""
                SELECT SUM(COALESCE(ch_semanal, 0))
                FROM atuacao
                WHERE escola_id = :eid 
                   OR escola_id IN (
                       SELECT id FROM escola 
                       WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :inep
                   )
            """)
            sum_at = db.session.execute(sql_ch_at, {"eid": e_id, "inep": clean_inep}).scalar()
            total_ch_alocada = int(sum_at or total_ch_autorizada)
        except Exception:
            db.session.rollback()

    total_apoio = 0
    if e_id or e_inep:
        try:
            sql_apoio = db.text("""
                SELECT COUNT(id) FROM apoio_clt 
                WHERE escola_id = :eid OR escola_inep = :inep
            """)
            cnt_ap = db.session.execute(sql_apoio, {"eid": e_id, "inep": e_inep}).scalar()
            total_apoio = int(cnt_ap or 0)
        except Exception:
            db.session.rollback()

    saldo_ch = total_ch_autorizada - total_ch_alocada

    resumo = {
        'total_professores': total_professores,
        'total_apoio': total_apoio,
        'total_ch_autorizada': total_ch_autorizada,
        'total_ch_alocada': total_ch_alocada,
        'saldo_ch': saldo_ch
    }

    # 3. Lista de Pendências Impeditivas e Alertas
    pendencias = []
    alertas = []

    if total_professores == 0:
        pendencias.append("Nenhum professor cadastrado para esta Unidade Escolar na aba Professores.")
    if saldo_ch != 0:
        alertas.append(f"Existe uma diferença de {abs(saldo_ch)}h entre a CH Autorizada e a CH Alocada na Atuação.")

    pode_confirmar = len(pendencias) == 0

    # 4. Lista de todas as escolas para o dropdown de navegação
    todas_escolas = []
    try:
        sql_todas = db.text("SELECT id, COALESCE(inep_visual, CAST(id AS VARCHAR)), nome FROM escola ORDER BY nome")
        rows_todas = db.session.execute(sql_todas).fetchall()
        todas_escolas = [EscolaView(r[0], r[1], r[2]) for r in rows_todas]
    except Exception:
        db.session.rollback()

    print(f"\n[DIAGNÓSTICO CONFIRMAÇÃO FINAL] Escola: {e_nome} | INEP: {e_inep} | Professores: {total_professores} | Homologado: {e_status}\n")

    return render_template(
        'confirmacao_final.html',
        escola=escola_ativa,
        inep_selecionado=e_inep,
        todas_escolas=todas_escolas,
        resumo=resumo,
        pendencias=pendencias,
        alertas=alertas,
        pode_confirmar=pode_confirmar
    )