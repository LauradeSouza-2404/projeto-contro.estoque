from flask import Flask, render_template, request

app = Flask(__name__)


@app.route("/")
def inicio():
    return render_template("cadastro_defensivo.html")


@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    nome = request.form["nome"]
    principio_ativo = request.form["principio_ativo"]
    fabricante = request.form["fabricante"]
    quantidade = request.form["quantidade"]
    unidade = request.form["unidade"]
    lote = request.form["lote"]
    validade = request.form["validade"]

    return f"""
    <h1>Defensivo cadastrado com sucesso!</h1>

    <p><strong>Nome:</strong> {nome}</p>
    <p><strong>Princípio ativo:</strong> {principio_ativo}</p>
    <p><strong>Fabricante:</strong> {fabricante}</p>
    <p><strong>Quantidade:</strong> {quantidade} {unidade}</p>
    <p><strong>Lote:</strong> {lote}</p>
    <p><strong>Validade:</strong> {validade}</p>

    <a href="/">Cadastrar outro defensivo</a>
    """


if __name__ == "__main__":
    app.run(debug=True)