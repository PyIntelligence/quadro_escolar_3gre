# app/routes/atuacao.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.extensions import db

atuacao_bp = Blueprint('atuacao', __name__)


def converter_para_int(val, padrao=40):
    try:
        if val is None:
            return padrao
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return padrao


class EscolaView:
    def __init__(self, e_id, inep, nome):
        self.id = e_id
        self.inep_visual = str(inep or '').strip()
        self.codigo_inep = str(inep or '').strip()
        self.inep = str(inep or '').strip()
        self.nome = nome or "ESCOLA"
        self.unidade_escolar = nome or "ESCOLA"


def resolver_escola_oficial(val):
    if not val:
        return None
    val_str = str(val).strip()
    val_clean = val_str.lstrip('0')

    try:
        sql = db.text("""
            SELECT id, inep_visual, nome FROM escola 
            WHERE LTRIM(TRIM(CAST(inep_visual AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(inep_visual AS VARCHAR)) = :raw
            LIMIT 1
        """)
        row = db.session.execute(sql, {"clean": val_clean, "raw": val_str}).fetchone()
        if row:
            return row
    except Exception:
        db.session.rollback()

    try:
        sql_g = db.text("""
            SELECT id, codigo_inep AS inep_visual, unidade_escolar AS nome 
            FROM escola_gestao 
            WHERE LTRIM(TRIM(CAST(codigo_inep AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(codigo_inep AS VARCHAR)) = :raw
            LIMIT 1
        """)
        row = db.session.execute(sql_g, {"clean": val_clean, "raw": val_str}).fetchone()
        if row:
            return row
    except Exception:
        db.session.rollback()

    return None


def obter_escola_atual():
    candidatos = [
        request.args.get('inep'),
        request.args.get('codigo_inep'),
        session.get('active_inep'),
        session.get('escola_inep'),
    ]
    for cand in candidatos:
        row = resolver_escola_oficial(cand)
        if row:
            session['active_inep'] = str(row[1] or '').strip()
            return EscolaView(row[0], str(row[1] or '').strip(), str(row[2] or '').strip())

    try:
        row = db.session.execute(db.text("SELECT id, inep_visual, nome FROM escola ORDER BY id LIMIT 1")).fetchone()
        if row:
            return EscolaView(row[0], str(row[1] or '').strip(), str(row[2] or '').strip())
    except Exception:
        db.session.rollback()
    return None


@atuacao_bp.route('/atuacao', methods=['GET', 'POST'])
def atuacao():
    escola_obj = obter_escola_atual()
    if not escola_obj:
        flash('Selecione uma escola para acessar a Atuação.', 'warning')
        return redirect('/escolas')

    inep_param = request.args.get('inep') or escola_obj.codigo_inep
    inep_clean = str(inep_param).strip().lstrip('0')
    e_id = escola_obj.id

    # 1. Garante colunas e remove restrições do PostgreSQL
    try:
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS atuacao (
                id SERIAL PRIMARY KEY,
                escola_id INT,
                professor_id INT,
                codigo_inep VARCHAR(20),
                matricula VARCHAR(50),
                professor_nome VARCHAR(150),
                atividade_componente VARCHAR(150),
                componente_curricular VARCHAR(150),
                turno VARCHAR(30) DEFAULT 'INTEGRAL',
                etapa_modalidade VARCHAR(100) DEFAULT 'ENSINO MÉDIO',
                area VARCHAR(100) DEFAULT 'LINGUAGENS',
                ch_semanal INT DEFAULT 13,
                turmas_atendidas VARCHAR(255),
                dias_atuacao VARCHAR(100) DEFAULT 'SEGUNDA-FEIRA',
                situacao_preenchimento VARCHAR(30) DEFAULT 'COMPLETO',
                situacao_normativa VARCHAR(30) DEFAULT 'CONFORME',
                grupo_atuacao VARCHAR(100) DEFAULT 'COMPONENTE CURRICULAR',
                natureza_ch VARCHAR(100) DEFAULT 'INTERAÇÃO PEDAGÓGICA',
                impacta_matriz VARCHAR(10) DEFAULT 'SIM',
                compoe_bloco_regencia VARCHAR(10) DEFAULT 'SIM',
                limite_regra VARCHAR(255) DEFAULT 'CONFORME MATRIZ CURRICULAR HOMOLOGADA',
                base_normativa VARCHAR(255) DEFAULT 'PORTARIA Nº 028/2026/SEE-PB',
                validacao_condicao VARCHAR(255) DEFAULT 'HABILITAÇÃO / PERFIL',
                observacoes TEXT,
                ch_autorizada INT DEFAULT 40
            );

            -- REMOVE CHAVES ESTRANGEIRAS QUE POSSAM BLOQUEAR A GRAVAÇÃO
            ALTER TABLE atuacao DROP CONSTRAINT IF EXISTS atuacao_escola_id_fkey;
            ALTER TABLE atuacao DROP CONSTRAINT IF EXISTS atuacao_professor_id_fkey;

            -- GARANTE A CRIAÇÃO DAS COLUNAS NECESSÁRIAS
            ALTER TABLE atuacao ADD COLUMN IF NOT EXISTS componente_curricular VARCHAR(150);
            ALTER TABLE atuacao ADD COLUMN IF NOT EXISTS atividade_componente VARCHAR(150);
            ALTER TABLE atuacao ADD COLUMN IF NOT EXISTS professor_id INT;
            ALTER TABLE atuacao ADD COLUMN IF NOT EXISTS escola_id INT;
            ALTER TABLE atuacao ADD COLUMN IF NOT EXISTS codigo_inep VARCHAR(20);
            ALTER TABLE atuacao ADD COLUMN IF NOT EXISTS matricula VARCHAR(50);
            ALTER TABLE atuacao ADD COLUMN IF NOT EXISTS impacta_matriz VARCHAR(10);
            ALTER TABLE atuacao ADD COLUMN IF NOT EXISTS compoe_bloco_regencia VARCHAR(10);

            -- REMOVE RESTRIÇÕES NOT NULL
            ALTER TABLE atuacao ALTER COLUMN componente_curricular DROP NOT NULL;
            ALTER TABLE atuacao ALTER COLUMN atividade_componente DROP NOT NULL;
            ALTER TABLE atuacao ALTER COLUMN professor_id DROP NOT NULL;
            ALTER TABLE atuacao ALTER COLUMN escola_id DROP NOT NULL;
            ALTER TABLE atuacao ALTER COLUMN codigo_inep DROP NOT NULL;
            ALTER TABLE atuacao ALTER COLUMN matricula DROP NOT NULL;
            ALTER TABLE atuacao ALTER COLUMN professor_nome DROP NOT NULL;

            ALTER TABLE professores ADD COLUMN IF NOT EXISTS codigo_inep VARCHAR(20);
            ALTER TABLE professores ADD COLUMN IF NOT EXISTS escola_id INT;
        """))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO ESTRUTURA BANCO ATUAÇÃO]: {e}")

    # 2. Converte automaticamente o tipo das colunas no banco Neon de Boolean para VARCHAR(10)
    try:
        db.session.execute(db.text("""
            ALTER TABLE atuacao ALTER COLUMN impacta_matriz TYPE VARCHAR(10) USING (
                CASE 
                    WHEN CAST(impacta_matriz AS VARCHAR) IN ('true', 't', '1', 'TRUE', 'SIM') THEN 'SIM' 
                    ELSE 'NÃO' 
                END
            );
            ALTER TABLE atuacao ALTER COLUMN compoe_bloco_regencia TYPE VARCHAR(10) USING (
                CASE 
                    WHEN CAST(compoe_bloco_regencia AS VARCHAR) IN ('true', 't', '1', 'TRUE', 'SIM') THEN 'SIM' 
                    ELSE 'NÃO' 
                END
            );
        """))
        db.session.commit()
    except Exception:
        db.session.rollback()

    # 3. Processa POST (Ações manuais)
    if request.method == 'POST':
        action = request.form.get('action', 'add')
        if action == 'add':
            matricula = request.form.get('matricula', '').strip().upper()
            prof_nome = request.form.get('professor_nome', '').strip().upper()
            componente = request.form.get('atividade_componente', '').strip().upper()
            turno = request.form.get('turno', '').strip().upper()
            etapa = request.form.get('etapa_modalidade', '').strip().upper()
            area = request.form.get('area', '').strip().upper()
            ch = converter_para_int(request.form.get('ch_semanal'), 0)
            turmas = request.form.get('turmas_atendidas', '').strip().upper()
            dias = request.form.get('dias_atuacao', '').strip().upper()
            ch_aut = converter_para_int(request.form.get('ch_autorizada'), 40)

            sql_ins = db.text("""
                INSERT INTO atuacao (
                    escola_id, codigo_inep, matricula, professor_nome, atividade_componente, componente_curricular,
                    turno, etapa_modalidade, area, ch_semanal, turmas_atendidas, dias_atuacao, ch_autorizada
                ) VALUES (
                    :e_id, :inep, :mat, :prof, :comp, :comp, :turno, :etapa, :area, :ch, :turmas, :dias, :ch_aut
                )
            """)
            try:
                db.session.execute(sql_ins, {
                    "e_id": e_id, "inep": inep_clean, "mat": matricula, "prof": prof_nome,
                    "comp": componente, "turno": turno, "etapa": etapa, "area": area,
                    "ch": ch, "turmas": turmas, "dias": dias, "ch_aut": ch_aut
                })
                db.session.commit()
                flash('Atribuição salva com sucesso!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao salvar: {str(e)}', 'danger')

        elif action == 'delete':
            reg_id = request.form.get('id')
            if reg_id:
                try:
                    db.session.execute(db.text("DELETE FROM atuacao WHERE id = :id"), {"id": reg_id})
                    db.session.commit()
                    flash('Linha removida.', 'success')
                except Exception:
                    db.session.rollback()

        return redirect(url_for('atuacao.atuacao', inep=inep_param))

    # 4. SINCRONIZAÇÃO AUTOMÁTICA DOS PROFESSORES DO SIAGE
    try:
        sql_profs = db.text("""
            SELECT * FROM professores 
            WHERE escola_id = :e_id
               OR LTRIM(TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)) = :raw
        """)
        profs_encontrados = db.session.execute(sql_profs, {
            "e_id": e_id,
            "clean": inep_clean,
            "raw": str(inep_param).strip()
        }).mappings().fetchall()

        print(f"[DIAGNÓSTICO SIAGE] Professores encontrados para escola_id {e_id} (INEP {inep_clean}): {len(profs_encontrados)}")

        for p in profs_encontrados:
            p_id = p.get('id')
            mat = str(p.get('matricula') or p.get('mat') or 'S/M').strip()
            nome = str(p.get('nome') or p.get('nome_professor') or p.get('servidor') or 'PROFESSOR').strip().upper()
            ch_aut = converter_para_int(p.get('carga_horaria') or p.get('ch') or p.get('ch_semanal'), 40)
            comp = str(p.get('disciplina') or p.get('componente') or p.get('funcao') or p.get('cargo') or 'COMPONENTE CURRICULAR').strip().upper()
            turno_p = str(p.get('turno') or 'INTEGRAL').strip().upper()
            turmas_p = str(p.get('turma') or p.get('turmas') or '').strip().upper()

            sql_check = db.text("""
                SELECT COUNT(*) FROM atuacao 
                WHERE (matricula = :mat OR professor_nome = :nome)
                  AND (escola_id = :e_id OR LTRIM(TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)), '0') = :clean)
            """)
            qtd_existente = db.session.execute(sql_check, {"mat": mat, "nome": nome, "e_id": e_id, "clean": inep_clean}).scalar() or 0

            if qtd_existente == 0:
                ch_regencia = int(ch_aut * 0.65) if ch_aut > 0 else 27
                ch_extraclasse = ch_aut - ch_regencia

                # 1ª Linha: Regência de Classe / Componente Curricular
                sql_auto_reg = db.text("""
                    INSERT INTO atuacao (
                        escola_id, professor_id, codigo_inep, matricula, professor_nome, atividade_componente, componente_curricular,
                        turno, ch_semanal, ch_autorizada, turmas_atendidas, grupo_atuacao, natureza_ch
                    ) VALUES (
                        :e_id, :p_id, :inep, :mat, :nome, :comp, :comp, :turno, :ch_reg, :ch_aut, :turmas, 'COMPONENTE CURRICULAR', 'INTERAÇÃO PEDAGÓGICA - MATRIZ'
                    )
                """)
                db.session.execute(sql_auto_reg, {
                    "e_id": e_id, "p_id": p_id, "inep": inep_clean, "mat": mat, "nome": nome, "comp": comp,
                    "turno": turno_p, "ch_reg": ch_regencia, "ch_aut": ch_aut, "turmas": turmas_p
                })

                # 2ª Linha: Extraclasse / Planejamento
                sql_auto_extra = db.text("""
                    INSERT INTO atuacao (
                        escola_id, professor_id, codigo_inep, matricula, professor_nome, atividade_componente, componente_curricular,
                        turno, ch_semanal, ch_autorizada, grupo_atuacao, natureza_ch, impacta_matriz
                    ) VALUES (
                        :e_id, :p_id, :inep, :mat, :nome, 
                        'ATIVIDADES EXTRACLASSE / PLANEJAMENTO - RDDI/140', 'ATIVIDADES EXTRACLASSE / PLANEJAMENTO - RDDI/140',
                        :turno, :ch_extra, :ch_aut, 'ATIVIDADE EXTRACLASSE', 'EXTRACLASSE / PLANEJAMENTO', 'NÃO'
                    )
                """)
                db.session.execute(sql_auto_extra, {
                    "e_id": e_id, "p_id": p_id, "inep": inep_clean, "mat": mat, "nome": nome,
                    "turno": turno_p, "ch_extra": ch_extraclasse, "ch_aut": ch_aut
                })

                print(f"[POPULOU ATUAÇÃO] Professor inserido: {nome} ({mat})")

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO NA SINCRONIZAÇÃO SIAGE ATUAÇÃO]: {e}")

    # 5. Lista para Dropdown
    professores_lista = []
    try:
        sql_p = db.text("""
            SELECT * FROM professores 
            WHERE escola_id = :e_id
               OR LTRIM(TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)), '0') = :clean
               OR TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)) = :raw
            ORDER BY id ASC
        """)
        professores_lista = [dict(r) for r in db.session.execute(sql_p, {"e_id": e_id, "clean": inep_clean, "raw": str(inep_param).strip()}).mappings().fetchall()]
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO DROPDOWN PROFESSORES]: {e}")

    # 6. Registros para exibição na tabela de Atuação
    atuacoes = []
    try:
        sql_a = db.text("""
            SELECT * FROM atuacao 
            WHERE escola_id = :e_id OR LTRIM(TRIM(CAST(COALESCE(codigo_inep, '') AS VARCHAR)), '0') = :clean
            ORDER BY id ASC
        """)
        rows = [dict(r) for r in db.session.execute(sql_a, {"e_id": e_id, "clean": inep_clean}).mappings().fetchall()]

        totais_ch = {}
        for r in rows:
            mat = r.get('matricula') or 'S/M'
            totais_ch[mat] = totais_ch.get(mat, 0) + converter_para_int(r.get('ch_semanal'), 0)

        for r in rows:
            mat = r.get('matricula') or 'S/M'
            ch_aut = converter_para_int(r.get('ch_autorizada'), 40)
            ch_reg = totais_ch.get(mat, 0)
            ch_rest = ch_aut - ch_reg

            if ch_reg == ch_aut:
                sit_ch = "CH COMPLETA"
            elif ch_reg < ch_aut:
                sit_ch = "CH INCOMPLETA"
            else:
                sit_ch = "CH EXCEDIDA"

            r['ch_registrada_calc'] = ch_reg
            r['ch_restante_calc'] = ch_rest
            r['situacao_ch_calc'] = sit_ch
            atuacoes.append(r)
    except Exception as e:
        db.session.rollback()
        print(f"[ERRO BUSCA ATUACOES]: {e}")

    return render_template(
        'atuacao.html',
        escola=escola_obj,
        inep=inep_param,
        atuacoes=atuacoes,
        professores_lista=professores_lista
    )


@atuacao_bp.route('/autosave_atuacao', methods=['POST'])
def autosave_atuacao():
    data = request.get_json(silent=True) or {}
    reg_id = data.get('id')
    campo = data.get('campo')
    valor = data.get('valor')

    campos_validos = {
        'matricula', 'professor_nome', 'atividade_componente', 'componente_curricular', 'turno', 'etapa_modalidade',
        'area', 'ch_semanal', 'turmas_atendidas', 'dias_atuacao', 'situacao_preenchimento',
        'situacao_normativa', 'grupo_atuacao', 'natureza_ch', 'impacta_matriz',
        'compoe_bloco_regencia', 'limite_regra', 'base_normativa', 'validacao_condicao',
        'observacoes', 'ch_autorizada'
    }

    if not reg_id or campo not in campos_validos:
        return jsonify({"status": "erro", "mensagem": "Parâmetros inválidos"}), 400

    try:
        sql = db.text(f"UPDATE atuacao SET {campo} = :val WHERE id = :id")
        db.session.execute(sql, {"val": valor, "id": reg_id})
        db.session.commit()
        return jsonify({"status": "sucesso"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500