import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Configurações de credenciais e servidor SMTP
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 465))
EMAIL_REMETENTE = os.getenv('EMAIL_SISTEMA', 'franciscogambarra@see.pb.gov.br')
SENHA_REMETENTE = os.getenv('SENHA_APP', 'rdresavxegovlbbb')


def enviar_email(email_destino: str, assunto: str, corpo_html: str, corpo_texto: str = "") -> bool:
    """
    Função genérica para envio de e-mails usando SMTP SSL.
    """
    mensagem = MIMEMultipart("alternative")
    mensagem["Subject"] = assunto
    mensagem["From"] = EMAIL_REMETENTE
    mensagem["To"] = email_destino

    # Adiciona versão em texto simples caso o cliente de e-mail do usuário não suporte HTML
    if corpo_texto:
        mensagem.attach(MIMEText(corpo_texto, "plain", "utf-8"))

    # Adiciona versão HTML
    mensagem.attach(MIMEText(corpo_html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_REMETENTE, SENHA_REMETENTE)
            server.sendmail(EMAIL_REMETENTE, email_destino, mensagem.as_string())
        return True
    except Exception as e:
        print(f"[ERRO MAIL SERVICE] Falha ao enviar e-mail para {email_destino}: {e}")
        return False


def enviar_email_redefinicao(email_destino: str, link_redefinicao: str) -> bool:
    """
    Serviço específico para submissão do e-mail de redefinição de senha.
    """
    assunto = "Redefinição de Senha"

    corpo_texto = f"""
Olá,

Recebemos uma solicitação para redefinir a sua senha.
Para criar uma nova senha, acesse o link abaixo:

{link_redefinicao}

Se você não fez essa solicitação, desconsidere esta mensagem.
"""

    corpo_html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
    </head>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 25px; border-radius: 8px; border: 1px solid #e0e0e0;">
            <h2 style="color: #0056b3; margin-top: 0;">Redefinição de Senha</h2>
            <p>Recebemos uma solicitação para redefinir a senha da sua conta.</p>
            <p>Clique no botão abaixo para cadastrar uma nova senha:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{link_redefinicao}" 
                   style="background-color: #0056b3; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                   Redefinir Senha
                </a>
            </p>
            <p style="font-size: 13px; color: #666;">
                Se o botão não funcionar, copie e cole o link a seguir no navegador:<br>
                <a href="{link_redefinicao}" style="color: #0056b3;">{link_redefinicao}</a>
            </p>
            <hr style="border: 0; border-top: 1px solid #eee; margin-top: 30px;">
            <p style="font-size: 12px; color: #888; margin-bottom: 0;">Se você não solicitou esta alteração, ignore este e-mail.</p>
        </div>
    </body>
    </html>
    """

    return enviar_email(
        email_destino=email_destino,
        assunto=assunto,
        corpo_html=corpo_html,
        corpo_texto=corpo_texto
    )