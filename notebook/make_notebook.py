"""Generates notebook/analysis.ipynb (run with the system python3, which has nbformat):

    python3 notebook/make_notebook.py
    jupyter nbconvert --to notebook --execute --inplace notebook/analysis.ipynb     # optional: run it, keep outputs
"""
import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))
nb = nbf.v4.new_notebook()
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

nb.cells = [
    md("""# Newsroom: analysis notebook

Companion to the web app (`app/app.py`). Set `CORPUS` to any built corpus (`corpora/<id>.toml` with a
`data/<id>/index.db`); sections 1–8 read that index, section 9 reads the cross-collection index
(`data/global.db`) and every built corpus.

**Contents:** 0. what is built · 1. corpus overview · 2. full-text search · 3. entities · 4. network analysis
(centrality, bridges, communities) · 5. lead-finding queries · 6. direct relations (email / registry data) ·
7. timelines · 8. this corpus's entities elsewhere · 9. across all collections (shared entities, collection overlap,
cross-collection timelines) · 10. Gephi export.

> Entities marked `auto=1` were detected automatically (codenames, NER, patterns) and are noisier than the curated ones.
> Co-occurrence is not a relationship: always read the pages. Across collections, entities are matched by type and name,
> so different people with the same name are merged there."""),
    code("""CORPUS = 'snowden'          # any id from corpora/*.toml that has been built

import os, re, sys, json, sqlite3, math, collections
import pandas as pd, networkx as nx, matplotlib.pyplot as plt
PROJECT = os.path.abspath('..') if os.path.basename(os.getcwd()) == 'notebook' else os.getcwd()
sys.path.insert(0, PROJECT)
from lib.config import load_corpus, list_corpora
from lib import globalindex

C = load_corpus(CORPUS)
con = sqlite3.connect(f'file:{C.db_path}?mode=ro', uri=True)
sql = lambda q, *a: pd.read_sql_query(q, con, params=a)
has_table = lambda name, c=con: c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None
pd.set_option('display.max_colwidth', 120); pd.set_option('display.width', 200)
palette = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948']

def tidy(ax, ylabel=''):
    ax.set_xlabel(''); ax.set_ylabel(ylabel); ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()

print(C.title, '→', C.db_path)
sql("SELECT k, v FROM meta")"""),
    md("## 0. What is built\n\nEvery configured corpus, with its index if it has one. The app's library page shows the same."),
    code("""rows = []
for c in list_corpora():
    row = {'corpus': c.id, 'title': c.title, 'built': ''}
    if c.exists():
        x = sqlite3.connect(f'file:{c.db_path}?mode=ro', uri=True)
        meta = dict(x.execute('SELECT k, v FROM meta'))
        row.update(built=meta.get('built', '')[:10], documents=int(meta.get('documents', 0)), pages=int(meta.get('pages', 0)),
                   entities=x.execute('SELECT COUNT(*) FROM entities').fetchone()[0], ner=meta.get('ner', ''))
        x.close()
    rows.append(row)
status = pd.DataFrame(rows).set_index('corpus')
status.sort_values('documents', ascending=False, na_position='last')"""),
    md("## 1. Corpus overview"),
    code("""sql('''SELECT collection, COUNT(*) docs, SUM(pages) pages, SUM(ocr_pages) ocr_pages
          FROM documents GROUP BY collection ORDER BY docs DESC LIMIT 30''')"""),
    code("""display(sql("SELECT kind, COUNT(*) docs FROM documents GROUP BY kind ORDER BY docs DESC"))
display(sql("SELECT origin, COUNT(*) docs FROM documents GROUP BY origin ORDER BY docs DESC LIMIT 20"))
display(sql("SELECT classification, COUNT(*) docs FROM documents GROUP BY classification ORDER BY docs DESC"))"""),
    code("""LO, HI = globalindex.year_range(C, con)       # the corpus's chart years, as in the app
yr = sql("SELECT year, COUNT(*) n FROM documents WHERE year BETWEEN ? AND ? GROUP BY year", LO, HI)
ax = yr.plot.bar(x='year', y='n', legend=False, figsize=(11, 3), color=palette[0], width=0.85)
ax.set_title('Documents by (estimated) year')
step = max(1, len(yr) // 25)
ax.set_xticks(range(0, len(yr), step)); ax.set_xticklabels(yr.year[::step])
tidy(ax, 'documents')"""),
    md("## 2. Full-text search\n\n`search()` uses SQLite FTS5 syntax: `\"exact phrase\"`, `prefix*`, `A OR B`, `A NOT B`, `NEAR(a b, 10)`."),
    code("""def search(q, limit=20):
    return sql('''SELECT d.title, d.doc_date, d.collection, p.page_no,
                         snippet(pages_fts, 0, '«', '»', ' … ', 24) AS snippet, d.id
                  FROM pages_fts JOIN pages p ON p.rowid = pages_fts.rowid JOIN documents d ON d.id = p.doc_id
                  WHERE pages_fts MATCH ? ORDER BY bm25(pages_fts) LIMIT ?''', q, limit)

def page(doc_id, page_no):
    r = con.execute('SELECT text FROM pages WHERE doc_id=? AND page_no=?', (doc_id, page_no)).fetchone()
    print(r[0] if r else '(not found)')

example = (C.ui.get('search_examples') or ['"human rights"'])[0]
print('query:', example)
search(example, 8)"""),
    md("## 3. Entities"),
    code("""sql("SELECT type, COUNT(*) entities, SUM(auto) auto_detected FROM entities GROUP BY type ORDER BY entities DESC")"""),
    code("""for t in [r[0] for r in con.execute("SELECT DISTINCT type FROM entities")]:
    print(f'--- {t}')
    display(sql("SELECT name, doc_count, mention_count, first_year, last_year, auto FROM entities WHERE type=? ORDER BY doc_count DESC LIMIT 12", t))"""),
    md("""## 4. Network analysis

A weighted graph from the co-occurrence table. Hubs connect to almost everything, so entities in more than `MAX_DF`
documents (the corpus's "hide hubs" setting) are left out, edges need at least `MIN_DOCS` shared documents, and only the
`NODE_CAP` most documented entities are kept so centrality stays quick on big corpora (cablegate has 95,000 entities)."""),
    code("""MIN_DOCS, MAX_DF, NODE_CAP = 3, C.ui.get('hide_hubs', 800), 3000
ents = sql("SELECT id, name, type, doc_count, auto FROM entities WHERE doc_count <= ? ORDER BY doc_count DESC LIMIT ?",
           MAX_DF, NODE_CAP).set_index('id')
ids = ','.join(map(str, ents.index))
edges = sql(f"SELECT src, dst, docs, npmi FROM edges WHERE docs >= ? AND src IN ({ids}) AND dst IN ({ids})", MIN_DOCS)
G = nx.Graph()
for i, r in ents.iterrows():
    G.add_node(i, name=r['name'], type=r['type'], docs=int(r['doc_count']), auto=int(r['auto']))
G.add_weighted_edges_from(edges[['src', 'dst', 'docs']].itertuples(index=False), weight='docs')
for s, d, n in edges[['src', 'dst', 'npmi']].itertuples(index=False):
    G[s][d]['npmi'] = n
G.remove_nodes_from([n for n in list(G) if G.degree(n) == 0])
print(G)"""),
    code("""# Betweenness (sampled for speed): entities that bridge otherwise separate parts of the corpus
bc = nx.betweenness_centrality(G, k=min(400, len(G)), weight=None, seed=1)
df = pd.DataFrame({'name': nx.get_node_attributes(G, 'name'), 'type': nx.get_node_attributes(G, 'type'),
                   'docs': nx.get_node_attributes(G, 'docs'), 'degree': dict(G.degree()), 'betweenness': bc})
# "bridge score": betweenness relative to how common the entity is
df['bridge_score'] = df.betweenness / df.docs.pow(0.5)
df.sort_values('betweenness', ascending=False).head(25)"""),
    code("""df[df.docs >= 5].sort_values('bridge_score', ascending=False).head(25)"""),
    code("""# Communities (Louvain on shared-document weights)
comms = nx.community.louvain_communities(G, weight='docs', seed=7, resolution=1.2)
rows = []
for i, c in enumerate(sorted(comms, key=len, reverse=True)[:20]):
    top = sorted(c, key=lambda n: -G.nodes[n]['docs'])[:14]
    rows.append({'community': i, 'size': len(c), 'top members': ', '.join(G.nodes[n]['name'] for n in top)})
pd.DataFrame(rows)"""),
    md("""## 5. Lead-finding queries

Pairs that co-occur far more than chance predicts (high NPMI), restricted to interesting type combinations. These are
leads, not facts: open the documents."""),
    code("""def distinctive_pairs(type_a, type_b, min_docs=3, limit=30):
    return sql('''SELECT a.name AS a, b.name AS b, e.docs, ROUND(e.npmi, 3) npmi, a.doc_count a_docs, b.doc_count b_docs
                  FROM edges e JOIN entities a ON a.id=e.src JOIN entities b ON b.id=e.dst
                  WHERE ((a.type=? AND b.type=?) OR (a.type=? AND b.type=?)) AND e.docs >= ?
                  ORDER BY e.npmi DESC LIMIT ?''', type_a, type_b, type_b, type_a, min_docs, limit)

distinctive_pairs('person', 'organization')"""),
    code("""distinctive_pairs('company', 'place')"""),
    code("""distinctive_pairs('person', 'program', min_docs=2)"""),
    code("""def entity_id(name):
    r = con.execute('SELECT id FROM entities WHERE name=? ORDER BY doc_count DESC LIMIT 1', (name,)).fetchone()
    return r[0] if r else None

def docs_with_both(a, b, limit=25):
    return sql('''SELECT d.id, d.title, d.doc_date, d.collection FROM documents d
                  WHERE d.id IN (SELECT doc_id FROM mentions WHERE entity_id=?)
                    AND d.id IN (SELECT doc_id FROM mentions WHERE entity_id=?)
                  ORDER BY d.doc_date LIMIT ?''', entity_id(a), entity_id(b), limit)

top_people = [r[0] for r in con.execute("SELECT name FROM entities WHERE type='person' AND auto=0 ORDER BY doc_count DESC LIMIT 2")]
print(top_people)
docs_with_both(*top_people) if len(top_people) == 2 else None"""),
    md("""## 6. Direct relations

Typed links from structured data: email sender → recipient, ICIJ officer → company, registered addresses. Empty for
corpora without structured sources."""),
    code("""rel = sql('''SELECT a.name AS source, r.type, b.name AS target, r.docs, r.first_date, r.last_date
               FROM relations r JOIN entities a ON a.id=r.src JOIN entities b ON b.id=r.dst
               ORDER BY r.docs DESC LIMIT 40''') if has_table('relations') else pd.DataFrame()
rel"""),
    code("""# Who talks to whom: directed email graph, ranked by PageRank
if len(rel):
    R = nx.DiGraph()
    for s, t, d in con.execute('''SELECT a.name, b.name, r.docs FROM relations r JOIN entities a ON a.id=r.src
                                   JOIN entities b ON b.id=r.dst WHERE r.type IN ('emailed', 'messaged')'''):
        R.add_edge(s, t, weight=d)
    if len(R):
        pr = nx.pagerank(R, weight='weight')
        display(pd.Series(pr).sort_values(ascending=False).head(20).rename('pagerank').to_frame())"""),
    md("""## 7. Timelines

Share of each year's dated documents that mention an entity, which corrects for uneven coverage. Years with fewer than
`min_year_docs` dated documents are left out, as in the app: one document makes a 100% spike. (The query starts from the
entity so SQLite can use the mentions index; filtering on year first makes it scan the whole table.)"""),
    code("""def year_counts(c, entity_ids, lo, hi):
    if not entity_ids:
        return pd.Series(dtype=int)
    q = f'''SELECT d.year, COUNT(DISTINCT d.id) n FROM mentions m JOIN documents d ON d.id = m.doc_id
            WHERE m.entity_id IN ({','.join('?' * len(entity_ids))}) AND d.year BETWEEN ? AND ? GROUP BY d.year'''
    return pd.read_sql_query(q, c, params=[*entity_ids, lo, hi]).set_index('year').n

def timeline(names, start=None, end=None, min_year_docs=5):
    start, end = start or LO, end or HI
    tot = sql("SELECT year, COUNT(*) n FROM documents WHERE year BETWEEN ? AND ? GROUP BY year", start, end).set_index('year').n
    tot = tot[tot >= min_year_docs]
    return pd.DataFrame({n: (100 * year_counts(con, [entity_id(n)] if entity_id(n) else [], start, end) / tot)
                             .reindex(tot.index).fillna(0) for n in names})

places = [r[0] for r in con.execute("SELECT name FROM entities WHERE type='place' ORDER BY doc_count DESC LIMIT 6")][1:6]
t = timeline(places)
ax = t.plot(figsize=(11, 3.5), color=palette[:len(t.columns)], linewidth=2)
tidy(ax, "% of year's documents")
t.round(1).tail(15)"""),
    md("""## 8. This corpus's entities elsewhere

The cross-collection index (`data/global.db`, the one behind the app's `/all/` pages) merges entities from every built
corpus by type and folded name. Opening it here rebuilds it first if a corpus index changed since it was made."""),
    code("""built = [c for c in list_corpora() if c.exists()]
gcon, updating = globalindex.open_current(built)
gsql = lambda q, *a: pd.read_sql_query(q, gcon, params=a)
gsql("SELECT cid AS corpus, title, docs, lo AS first_year, hi AS last_year FROM corpora ORDER BY docs DESC")"""),
    code("""# named entities of this corpus (not places or themes) that also appear in other collections
gsql('''SELECT e.name, e.type, SUM(l.doc_count) AS docs_here, e.doc_count AS docs_everywhere, e.n_corpora AS collections
        FROM local l JOIN entities e ON e.gkey = l.gkey
        WHERE l.cid = ? AND e.n_corpora > 1 AND e.auto = 0 AND e.type NOT IN ('place', 'idea')
        GROUP BY e.gkey ORDER BY e.n_corpora DESC, docs_here DESC LIMIT 25''', CORPUS)"""),
    code("""def across(name, etype=None):
    \"\"\"Where an entity appears, collection by collection (matched like the app: type and folded name).\"\"\"
    keys = [globalindex.gkey(etype, name)] if etype else \\
           [r[0] for r in gcon.execute("SELECT gkey FROM entities WHERE gkey IN (" + ','.join('?' * 9) + ")",
                                       [globalindex.gkey(t, name) for t in ('person', 'agency', 'company', 'program', 'technology',
                                                                            'place', 'organization', 'idea', 'identifier')])]
    if not keys:
        return pd.DataFrame()
    return gsql(f'''SELECT e.type, l.cid AS corpus, l.name AS name_there, l.doc_count AS docs, l.mention_count AS mentions
                    FROM local l JOIN entities e ON e.gkey = l.gkey WHERE l.gkey IN ({','.join('?' * len(keys))})
                    ORDER BY l.doc_count DESC''', *keys)

across(top_people[0] if top_people else 'United States')"""),
    md("""## 9. Across all collections

Entities found in the most collections, how much the collections overlap, and an entity's documents per year in every
collection that mentions it."""),
    code("""gsql('''SELECT name, type, n_corpora AS collections, doc_count AS documents, first_year, last_year
        FROM entities WHERE auto = 0 AND type NOT IN ('place', 'idea')
        ORDER BY n_corpora DESC, doc_count DESC LIMIT 30''')"""),
    code("""# collection overlap: share of named (non-auto) entities two collections have in common (Jaccard)
pairs = gsql('''SELECT a.cid AS a, b.cid AS b, COUNT(DISTINCT a.gkey) shared FROM local a JOIN local b ON a.gkey = b.gkey
                JOIN entities e ON e.gkey = a.gkey WHERE e.auto = 0 AND a.cid < b.cid GROUP BY a.cid, b.cid''')
sizes = gsql('''SELECT l.cid, COUNT(DISTINCT l.gkey) n FROM local l JOIN entities e ON e.gkey = l.gkey
                WHERE e.auto = 0 GROUP BY l.cid''').set_index('cid').n
names = list(sizes.index)
jac = pd.DataFrame(0.0, index=names, columns=names)
for a, b, s in pairs.itertuples(index=False):
    jac.loc[a, b] = jac.loc[b, a] = s / (sizes[a] + sizes[b] - s)
fig, ax = plt.subplots(figsize=(7.5, 6))
im = ax.imshow(jac.values, cmap='Blues', vmin=0)
ax.set_xticks(range(len(names))); ax.set_xticklabels(names, rotation=60, ha='right')
ax.set_yticks(range(len(names))); ax.set_yticklabels(names)
for i in range(len(names)):
    for j in range(len(names)):
        if i != j and jac.iat[i, j] >= 0.005:
            ax.text(j, i, f'{jac.iat[i, j]:.2f}', ha='center', va='center', fontsize=7,
                    color='white' if jac.iat[i, j] > jac.values.max() * 0.6 else '#333')
ax.set_title('Shared named entities between collections (Jaccard)')
fig.colorbar(im, ax=ax, shrink=0.8); plt.tight_layout()
pairs.sort_values('shared', ascending=False).head(15)"""),
    code("""def across_years(name, etype='person'):
    \"\"\"Documents per year mentioning an entity, by collection (each document once per collection).\"\"\"
    gk = globalindex.gkey(etype, name)
    bounds = {r[0]: (r[1], r[2]) for r in gcon.execute('SELECT cid, lo, hi FROM corpora')}
    keys = collections.defaultdict(list)
    for cid, key in gcon.execute('SELECT cid, key FROM local WHERE gkey = ?', (gk,)):
        keys[cid].append(key)
    out = {}
    for cid, ks in keys.items():
        c = load_corpus(cid)
        x = sqlite3.connect(f'file:{c.db_path}?mode=ro', uri=True)
        ids = [r[0] for r in x.execute(f"SELECT id FROM entities WHERE key IN ({','.join('?' * len(ks))})", ks)]
        out[cid] = year_counts(x, ids, *bounds[cid])
        x.close()
    return pd.DataFrame(out).fillna(0).astype(int).sort_index()

who = gsql('''SELECT name FROM entities WHERE type = 'person' AND auto = 0 ORDER BY n_corpora DESC, doc_count DESC LIMIT 1''').name[0]
print('the named person found in the most collections:', who, '(pass any name to across_years)')
by_year = across_years(who)
ax = by_year.plot.area(figsize=(11, 3.5), color=palette[:len(by_year.columns)], linewidth=0)
ax.set_title(f'{who}: documents per year, by collection')
tidy(ax, 'documents')
by_year.sum().rename('documents').to_frame().T"""),
    md("## 10. Export for Gephi / other tools"),
    code("""out = os.path.join(C.data_dir, 'graph.gexf')
H = G.copy()
for n in H:
    H.nodes[n]['label'] = H.nodes[n].pop('name')
nx.write_gexf(H, out)
print('wrote', out, H)"""),
]
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
path = os.path.join(HERE, "analysis.ipynb")
nbf.write(nb, path)
print("wrote", path)
