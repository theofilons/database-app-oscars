import json
from flask import Flask, render_template, request, abort
import db  # Importamos o teu ficheiro de conexão

APP = Flask(__name__)

db.connect()

@APP.route('/')
def index():
    return render_template('index.html')

@APP.route('/dashboard')
def dashboard():
    top_films = db.execute('''
        SELECT f.film, COUNT(*) as wins
        FROM nomeacao n
        JOIN filme f ON TRIM(n.filmId) = TRIM(f.filmId)
        WHERE n.winner IN ('1', 'TRUE', 'True', 'true', 1)
        GROUP BY f.film
        ORDER BY wins DESC
        LIMIT 5
    ''').fetchall()
    
    films_labels = [row['film'] for row in top_films]
    films_data = [row['wins'] for row in top_films]
    
    nom_by_year = db.execute('''
        SELECT c.year, COUNT(*) as total
        FROM nomeacao n
        JOIN cerimonia c ON n.ceremony = c.ceremony
        GROUP BY c.year
        ORDER BY c.year ASC
    ''').fetchall()

    years_labels = [row['year'] for row in nom_by_year]
    years_data = [row['total'] for row in nom_by_year]

    return render_template('dashboard.html', 
                           films_labels=json.dumps(films_labels), 
                           films_data=json.dumps(films_data),
                           years_labels=json.dumps(years_labels), 
                           years_data=json.dumps(years_data))

@APP.route('/estatisticas')
def estatisticas():
    totais = db.execute('''
        SELECT 
            (SELECT COUNT(*) FROM cerimonia) as total_cerimonias,
            (SELECT COUNT(DISTINCT filmId) FROM nomeacao WHERE filmId IS NOT NULL AND filmId <> '') as filmes_nomeados,
            (SELECT COUNT(*) FROM nomeacao) as total_nomeacoes
    ''').fetchone()

    historico = db.execute('''
        SELECT c.year, c.ceremony, COUNT(n.nomId) as total_nomeacoes
        FROM cerimonia c
        LEFT JOIN nomeacao n ON n.ceremony = c.ceremony
        GROUP BY c.ceremony, c.year
        ORDER BY c.year ASC LIMIT 20
    ''').fetchall()

    return render_template('estatisticas.html', totais=totais, historico=historico)

@APP.route('/filmes')
def lista_filmes():
    busca = request.args.get('q')
    if busca:
        filmes = db.execute('SELECT * FROM filme WHERE film LIKE ? LIMIT 50', ('%' + busca + '%',)).fetchall()
    else:
        filmes = db.execute('SELECT * FROM filme LIMIT 50').fetchall()
    return render_template('filmes.html', filmes=filmes)

@APP.route('/filme/<string:id>')
def filme(id):
    filme_info = db.execute('SELECT filmId, film FROM filme WHERE filmId = ?', [id]).fetchone()
    if filme_info is None:
        abort(404)

    nomeacoes = db.execute('''
        SELECT DISTINCT n.nomId,n.detail,n.citation,n.note, n.winner, c.category, cer.year, cer.ceremony, e.nominee AS nominee_name
        FROM nomeacao AS n
        JOIN categoria AS c ON n.catId = c.catId
        JOIN cerimonia AS cer ON n.ceremony = cer.ceremony
        LEFT JOIN nomeadas AS ns ON n.nomId = ns.nomId
        LEFT JOIN entidade AS e ON ns.nomineeId = e.nomineeId
        WHERE n.filmId = ?   
    AND NOT (
    n.winner = 0
    AND EXISTS (
        SELECT 1
        FROM nomeacao n2
        WHERE n2.filmId = n.filmId
          AND n2.ceremony = n.ceremony
          AND n2.catId = n.catId
          AND n2.winner = 1
    )
)
    ORDER BY n.winner DESC, c.canonicalCategory ASC 
    ''', [id]).fetchall()

    return render_template('pagina-filme.html', movie=filme_info, nominations=nomeacoes)

@APP.route('/pessoas')
def lista_pessoas():
    busca = request.args.get('q')
    if busca:
        pessoas = db.execute('SELECT DISTINCT * FROM entidade WHERE nominee LIKE ? LIMIT 50', ('%' + busca + '%',)).fetchall()
    else:
        pessoas = db.execute('SELECT * FROM entidade LIMIT 50').fetchall()
    return render_template('pessoas.html', pessoas=pessoas)

@APP.route('/pessoa/<string:id>')
def pessoa(id):
    pessoa_info = db.execute('SELECT * FROM entidade WHERE nomineeId = ?', [id]).fetchone()
    if pessoa_info is None:
        abort(404)

    historico = db.execute('''
        SELECT DISTINCT c.year, cat.category, f.film, f.filmId, n.winner
        FROM nomeadas ns
        JOIN nomeacao n ON ns.nomId = n.nomId
        JOIN cerimonia c ON n.ceremony = c.ceremony
        JOIN categoria cat ON n.catId = cat.catId
        LEFT JOIN filme f ON n.filmId = f.filmId
        WHERE ns.nomineeId = ?
        ORDER BY c.year DESC
    ''', [id]).fetchall()

    return render_template('pessoa.html', pessoa=pessoa_info, historico=historico)

@APP.route('/cerimonias')
def lista_cerimonias():
    cerimonias = db.execute('SELECT * FROM cerimonia where year <> 2024 ORDER BY ceremony DESC').fetchall()
    return render_template('cerimonias.html', cerimonias=cerimonias)

@APP.route('/cerimonia/<int:ceremony_id>')
def cerimonia(ceremony_id):
    cerimonia_info = db.execute('SELECT * FROM cerimonia WHERE ceremony = ?', [ceremony_id]).fetchone()
    if cerimonia_info is None:
        abort(404)

    sql_query = """SELECT DISTINCT c.category, f.film, f.filmId, e.nominee, e.nomineeId, n.winner 
        FROM nomeacao n JOIN categoria c ON n.catId = c.catId LEFT JOIN filme f ON n.filmId = f.filmId 
        LEFT JOIN nomeadas ns ON n.nomId = ns.nomId LEFT JOIN entidade e ON ns.nomineeId = e.nomineeId 
        WHERE n.ceremony = ? ORDER BY c.category;"""
    
    vencedores = db.execute(sql_query.strip(), [ceremony_id]).fetchall()

    return render_template('cerimonia.html', info=cerimonia_info, vencedores=vencedores)


@APP.route('/categorias')
def lista_categorias():
    categorias = db.execute('SELECT * FROM categoria ORDER BY category ASC').fetchall()
    
    return render_template('categorias.html', categorias=categorias)

@APP.route('/categoria/<int:id>')
def categoria(id):
    cat_info = db.execute('SELECT * FROM categoria WHERE catId = ?', [id]).fetchone()
    
    sql_query = """
        SELECT DISTINCT 
            cer.year, 
            f.film, 
            f.filmId, 
            e.nominee,
            e.nomineeId
        FROM nomeacao n
        JOIN cerimonia cer ON n.ceremony = cer.ceremony
        LEFT JOIN filme f ON n.filmId = f.filmId
        LEFT JOIN nomeadas ns ON n.nomId = ns.nomId
        LEFT JOIN entidade e ON ns.nomineeId = e.nomineeId
        WHERE n.catId = ? 
          AND (n.winner = 1 OR n.winner = '1' OR LOWER(n.winner) = 'true' OR LOWER(n.winner) = 'yes' OR LOWER(n.winner) = 'y')
        ORDER BY 
            CAST(SUBSTR(cer.year, 1, 4) AS INTEGER) DESC,
            cer.year DESC;
    """
    
    todos_vencedores = db.execute(sql_query.strip(), [id]).fetchall()
 
    return render_template('categoria.html', cat=cat_info, vencedores=todos_vencedores)

@APP.route('/top-vencedores')
def top_vencedores():
    top_list = db.execute('''
        SELECT f.film, COUNT(DISTINCT n.nomId) total_nomeacoes
        FROM nomeacao n
        JOIN filme f ON f.filmId = n.filmId
        JOIN categoria cat ON cat.catId = n.catId
        WHERE n.filmId IS NOT NULL
        AND n.filmId <> ''
        AND cat.class NOT IN ('Special', 'SciTech')
        GROUP BY n.filmId, f.film
        ORDER BY total_nomeacoes DESC, f.film
        LIMIT 10;

    ''').fetchall()
    return render_template('top-vencedores.html', top_list=top_list)