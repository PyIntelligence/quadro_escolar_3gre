# app/utils/smart_merge.py

def preencher_campo_se_vazio(objeto, campo, valor_novo):
    """
    Preenche um atributo do objeto SOMENTE se o campo atual estiver vazio ou nulo.
    NUNCA sobrescreve dados que você já digitou ou salvou previamente.
    """
    if valor_novo is None:
        return False

    val_novo_str = str(valor_novo).strip()
    if not val_novo_str or val_novo_str.upper() in ['NONE', 'NULL', 'NAN', 'UNDEFINED', '']:
        return False

    valor_atual = getattr(objeto, campo, None)

    # Se estiver Nulo/Vazio no banco local
    if valor_atual is None:
        setattr(objeto, campo, val_novo_str)
        return True

    val_atual_str = str(valor_atual).strip()

    # Se estiver marcado com valor padrão sem informação
    if val_atual_str.upper() in ['NONE', 'NULL', 'NAN', '', '0', '0.0', 'N/A', 'NAO INFORMADO', 'NÃO INFORMADO']:
        setattr(objeto, campo, val_novo_str)
        return True

    # Já possui valor digitado pelo usuário: mantém intacto
    return False