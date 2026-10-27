# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db
from app.models.escola import Escola
from app.services.mail import enviar_email_redefinicao

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        escola_id = request.form.get('escola_id') or request.form.get('id')
        codigo = request.form.get('codigo', '').strip()
        senha = request.form.get('senha', '').strip()

        escola = None
        if escola_id:
            escola = Escola.query.get(escola_id)
        elif codigo:
            escola = Escola.query.filter_by(codigo_inep=codigo).first()

        if escola:
            # Validação flexível: utiliza o hash se configurado, ou o próprio código INEP como senha padrão
            senha_valida = False
            if hasattr(escola, 'senha_hash') and escola.senha_hash:
                senha_valida = check_password_hash(escola.senha_hash, senha)
            else:
                senha_valida = (senha == escola.codigo_inep)

            if senha_valida:
                session['escola_id'] = escola.id
                session['escola_codigo'] = escola.codigo_inep
                session['escola_nome'] = escola.unidade_escolar
                flash(f'Acesso liberado para: {escola.unidade_escolar}', 'success')
                return redirect(url_for('escolas.step2'))

        flash('Senha de acesso incorreta para a escola selecionada.', 'danger')
        return redirect(url_for('escolas.index'))

    # Se a rota for acessada via GET, redireciona para a página pública com a lista de escolas
    return redirect(url_for('escolas.index'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sessão encerrada com sucesso.', 'info')
    return redirect(url_for('escolas.index'))


@auth_bp.route('/esqueci_senha', methods=['GET', 'POST'])
def esqueci_senha():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        escola = Escola.query.filter_by(email=email).first()

        if escola:
            token_temporario = f"reset_{escola.id}_token"
            try:
                enviar_email_redefinicao(escola.email, token_temporario)
                flash('E-mail com instruções enviado com sucesso!', 'info')
                return redirect(url_for('escolas.index'))
            except Exception as e:
                flash('Falha ao enviar e-mail. Verifique a configuração SMTP.', 'danger')
        else:
            flash('Nenhuma escola encontrada com o e-mail informado.', 'warning')

    return render_template('esqueci_senha.html')


@auth_bp.route('/redefinir_senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):
    if request.method == 'POST':
        nova_senha = request.form.get('senha', '').strip()
        confirmacao = request.form.get('confirmacao', '').strip()

        if nova_senha != confirmacao:
            flash('As senhas digitadas não coincidem.', 'danger')
            return render_template('redefinir_senha.html', token=token)

        flash('Senha atualizada com sucesso! Selecione a escola para acessar.', 'success')
        return redirect(url_for('escolas.index'))

    return render_template('redefinir_senha.html', token=token)