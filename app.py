from flask import Flask, render_template_string, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
import plotly.express as px
import pandas as pd
import locale

# Configurar locale para formato brasileiro
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///financeiro.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# MODELOS
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    senha = db.Column(db.String(100), nullable=False)

class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    data = db.Column(db.Date, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# HTML do dashboard com suporte a PWA
TEMPLATE = """
<!doctype html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dashboard Financeiro</title>
    <link rel="manifest" href="/static/manifest.json">
    <script>
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/service-worker.js')
          .then(() => console.log("Service Worker registrado"))
          .catch(err => console.log("Erro no Service Worker", err));
      }
    </script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container mt-5">
    <h1 class="mb-4">💸 Olá, {{ current_user.nome }}!</h1>
    <a href="/logout" class="btn btn-outline-danger mb-4">Sair</a>
    <a href="/relatorio" class="btn btn-outline-secondary mb-4">📄 Baixar Relatório PDF</a>

    <form method="get" action="/" class="mb-4">
        <label for="mes">Filtrar por mês:</label>
        <input type="month" name="mes" id="mes" class="form-control" onchange="this.form.submit()">
    </form>

    <form method="post" action="/add" class="row g-3 mb-4">
        <div class="col-md-3">
            <input type="date" name="data" class="form-control" required>
        </div>
        <div class="col-md-2">
            <select name="tipo" class="form-select">
                <option value="receita">Receita</option>
                <option value="despesa">Despesa</option>
            </select>
        </div>
        <div class="col-md-3">
            <input type="text" name="descricao" class="form-control" placeholder="Descrição" required>
        </div>
        <div class="col-md-2">
            <input type="number" step="0.01" name="valor" class="form-control" placeholder="Valor" required>
        </div>
        <div class="col-md-2">
            <button type="submit" class="btn btn-primary w-100">Adicionar</button>
        </div>
    </form>

    <h3>Saldo atual: {{ saldo }}</h3>

    <div class="row mt-4">
        <div class="col-md-6">
            <h5>📊 Gráfico de barras</h5>
            {{ grafico_barras|safe }}
        </div>
        <div class="col-md-6">
            <h5>🥧 Gráfico de pizza</h5>
            {{ grafico_pizza|safe }}
        </div>
    </div>

    <h4 class="mt-5">📋 Transações</h4>
    <table class="table table-striped table-bordered">
        <thead class="table-dark">
            <tr>
                <th>Data</th>
                <th>Tipo</th>
                <th>Descrição</th>
                <th>Valor</th>
            </tr>
        </thead>
        <tbody>
        {% for t in transacoes %}
            <tr>
                <td>{{ t.data.strftime('%d/%m/%Y') }}</td>
                <td>{{ t.tipo }}</td>
                <td>{{ t.descricao }}</td>
                <td>{{ ("R$ " + "{:,.2f}".format(t.valor)).replace(",", "X").replace(".", ",").replace("X", ".") }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
</div>
</body>
</html>
"""

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']
        if Usuario.query.filter_by(nome=nome).first():
            return "Usuário já existe."
        novo = Usuario(nome=nome, senha=senha)
        db.session.add(novo)
        db.session.commit()
        return redirect(url_for('login'))
    return '''
        <h2>Cadastro</h2>
        <form method="post">
            Nome: <input type="text" name="nome"><br>
            Senha: <input type="password" name="senha"><br>
            <input type="submit" value="Cadastrar">
        </form>
    '''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']
        usuario = Usuario.query.filter_by(nome=nome, senha=senha).first()
        if usuario:
            login_user(usuario)
            return redirect(url_for('index'))
        return "Login inválido"
    return '''
        <h2>Login</h2>
        <form method="post">
            Nome: <input type="text" name="nome"><br>
            Senha: <input type="password" name="senha"><br>
            <input type="submit" value="Entrar">
        </form>
    '''

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    mes = request.args.get('mes')
    if mes:
        ano, mes_num = map(int, mes.split('-'))
        transacoes = Transacao.query.filter(
            Transacao.usuario_id == current_user.id,
            db.extract('year', Transacao.data) == ano,
            db.extract('month', Transacao.data) == mes_num
        ).all()
    else:
        transacoes = Transacao.query.filter_by(usuario_id=current_user.id).all()

    saldo_valor = sum(t.valor if t.tipo == 'receita' else -t.valor for t in transacoes)
    saldo = locale.currency(saldo_valor, grouping=True)

    df = pd.DataFrame([{
        'data': t.data.strftime('%d/%m/%Y'),
        'tipo': t.tipo,
        'descricao': t.descricao,
        'valor': t.valor
    } for t in transacoes])

    if not df.empty:
        barras = px.bar(df, x='descricao', y='valor', color='tipo', title='Transações por tipo')
        grafico_barras = barras.to_html(full_html=False)
        pizza = px.pie(df, names='tipo', values='valor', title='Distribuição de receitas e despesas')
        grafico_pizza = pizza.to_html(full_html=False)
    else:
        grafico_barras = "<p>Nenhuma transação ainda.</p>"
       