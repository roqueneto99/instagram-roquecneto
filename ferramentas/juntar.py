"""Junta a base da OIT (escores) com as traduções e gera ferramentas/dados.json."""
import json, pathlib, sys
P = pathlib.Path(__file__).parent
CAT = {"Exposed: Gradient 4": 4, "Exposed: Gradient 3": 3, "Exposed: Gradient 2": 2,
       "Exposed: Gradient 1": 1, "Minimal Exposure": 0, "Not Exposed": -1}
base = {o["c"]: o for o in json.load(open(P / "base_en.json"))}
pt = {}
for i in range(1, 7):
    f = P / f"parte{i}_pt.json"
    if not f.exists():
        sys.exit(f"falta {f.name}")
    for o in json.load(open(f)):
        pt[o["c"]] = o
erros = []
saida = []
for c, b in base.items():
    t = pt.get(c)
    if not t:
        erros.append(f"{c} sem tradução"); continue
    if len(t["tasks"]) != len(b["tasks"]):
        erros.append(f"{c} tarefas {len(t['tasks'])} != {len(b['tasks'])}"); continue
    txt = json.dumps(t, ensure_ascii=False)
    if "—" in txt:
        erros.append(f"{c} tem travessão")
    saida.append({"c": c, "t": t["t"].strip(), "b": [x.strip() for x in t.get("busca", [])][:6],
                  "m": b["m"], "m23": b["m23"], "g": CAT[b["cat"]],
                  "k": [[x["s"], y.strip().rstrip(";").strip()] for x, y in zip(b["tasks"], t["tasks"])]})
if erros:
    print("\n".join(erros)); sys.exit(1)
out = P.parent / "ferramentas" / "dados.json"
out.write_text(json.dumps({"fonte": "Gmyrek et al. (2025), OIT WP140, CC BY 4.0", "o": saida}, ensure_ascii=False, separators=(",", ":")))
print(len(saida), "ocupações", sum(len(o["k"]) for o in saida), "tarefas", out.stat().st_size // 1024, "KB")
