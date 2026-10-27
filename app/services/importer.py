# app/services/importer.py

import pandas as pd
from datetime import datetime
from app.extensions import db
from app.models.professor import Professor
from app.models.escola import EscolaGestao

# Dicionário de Sinônimos/Aliases para Tolerância a Falhas
ALIAS_MAP = {
    'matricula': ['matricula', 'matrícula', 'mat_servidor', 'cd_matricula', 'matricula_servidor'],
    'cpf': ['cpf', 'cpf_servidor', 'nr_cpf', 'documento_cpf'],
    'nome': ['nome', 'nome completo', 'nome_servidor', 'nm_servidor', 'servidor'],
    'vinculo': ['vinculo', 'vínculo', 'situacao_vinculo', 'tp_vinculo', 'tipo_vinculo'],
    'utb_esta_escola': ['utb_esta_escola', 'utb esta escola?', 'utb_local'],
    'utb_informada': ['utb_informada', 'utb informada', 'escola_utb'],
    'forma_atuacao': ['forma_atuacao', 'forma de atuação', 'forma de atuacao', 'atuacao'],
    'carga_horaria_original': ['carga_horaria_original', 'ch orig.', 'ch_vinculo', 'carga_horaria', 'ch_original'],
    'possui_ch_fora': ['possui_ch_fora', 'ch fora?', 'possui_ch_fora?'],
    'outra_unidade': ['outra_unidade', 'outra unidade/função', 'outra_escola'],
    'ch_fora': ['ch_fora', 'ch fora', 'carga_horaria_fora'],
    'conselho_escolar': ['conselho_escolar', 'conselho escolar'],
    'areas_planejamento': ['areas_planejamento', 'áreas planejamento', 'areas de planejamento'],
    'dias_planejamento': ['dias_planejamento', 'dias planej.'],
    'reducao_legal_vigente': ['reducao_legal_vigente', 'redução vigente?', 'reducao_legal'],
    'carga_horaria_autorizada': ['carga_horaria_autorizada', 'ch aut.', 'ch_autorizada'],
    'regencia_autorizada': ['regencia_autorizada', 'regência aut.', 'regencia_autorizada'],
    'ato_autorizacao': ['ato_autorizacao', 'ato autorização', 'portaria'],
    'fundamento_legal': ['fundamento_legal', 'fundamento legal'],
    'validade_ato': ['validade_ato', 'validade ato', 'dt_validade_ato'],
    'situacao_cadastro': ['situacao_cadastro', 'conferido?', 'st_cadastro'],
    'observacoes': ['observacoes', 'observações', 'obs']
}

def normalizar_cabecalho(coluna):
    """Limpa e padroniza os nomes de colunas recebidos."""
    return str(coluna).strip().lower()

def buscar_campo_mapeado(coluna_norm):
    """Retorna o nome do campo oficial no banco a partir do nome da coluna encontrada."""
    for campo_bd, aliases in ALIAS_MAP.items():
        if coluna_norm in aliases:
            return campo_bd
    return None

def processar_e_salvar_professores(df_ou_dict_list, escola_id=None, escola_inep=None):
    """
    Aceita um DataFrame do Pandas (Excel/CSV) ou uma lista de dicionários (API do SIAGE)
    e realiza a gravação/atualização (upsert) no banco de dados.
    """
    if isinstance(df_ou_dict_list, list):
        df = pd.DataFrame(df_ou_dict_list)
    else:
        df = df_ou_dict_list

    # Normaliza os cabeçalhos recebidos
    col_mapping = {}
    for col in df.columns:
        col_norm = normalizar_cabecalho(col)
        campo_bd = buscar_campo_mapeado(col_norm)
        if campo_bd:
            col_mapping[col] = campo_bd

    # Renomeia o dataframe para as colunas padronizadas do Banco
    df_mapped = df.rename(columns=col_mapping)

    # Resolve Escola se INEP for fornecido
    if not escola_id and escola_inep:
        escola = EscolaGestao.query.filter_by(inep=str(escola_inep)).first()
        if escola:
            escola_id = escola.id

    registros_processados = 0

    for _, row in df_mapped.iterrows():
        matricula = str(row.get('matricula', '')).strip() if pd.notna(row.get('matricula')) else None
        
        if not matricula:
            continue  # Pula registros sem matrícula

        # Tenta localizar professor existente para atualização (upsert)
        professor = Professor.query.filter_by(matricula=matricula, escola_id=escola_id).first()
        if not professor:
            professor = Professor(matricula=matricula, escola_id=escola_id)

        # Atualiza os campos dinamicamente
        for campo in ALIAS_MAP.keys():
            if campo in df_mapped.columns and pd.notna(row[campo]):
                valor = row[campo]
                
                # Trata datas
                if campo == 'validade_ato':
                    if isinstance(valor, str):
                        try:
                            valor = datetime.strptime(valor, '%Y-%m-%d').date()
                        except ValueError:
                            try:
                                valor = datetime.strptime(valor, '%d/%m/%Y').date()
                            except ValueError:
                                valor = None
                    elif hasattr(valor, 'date'):
                        valor = valor.date()

                # Trata valores do tipo string para UPPERCASE
                elif isinstance(valor, str):
                    valor = valor.strip().upper()

                setattr(professor, campo, valor)

        if escola_inep:
            professor.escola_inep = str(escola_inep)

        db.session.add(professor)
        registros_processados += 1

    db.session.commit()
    return registros_processados