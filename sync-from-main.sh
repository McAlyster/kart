#!/usr/bin/env bash
# Recopie la branche main de KART dans app/ (branche feature/docKART).
#
# docKART = main dockerisé : app/ doit rester identique à main. Seuls diffèrent
# les fichiers Docker/outillage (racine du dépôt + exclusions ci-dessous) et un
# écart de fond toléré : CorsMiddleware placé en tête dans app/kart/settings.py
# (sinon le front Vue en localhost est bloqué par CORS).
#
# Prérequis : un worktree de main à côté de ce dépôt
#   git worktree add ../kart-main main
#
# Usage : ./sync-from-main.sh                     (pull de main puis synchro)
#         ./sync-from-main.sh --no-pull           (synchro sur le main local tel quel)
#         ./sync-from-main.sh --from ../kart-c27  (synchro depuis un autre worktree,
#              ex. une feature pas encore fusionnée : à faire sur une branche locale
#              temporaire, jamais sur feature/docKART)
#
# Le script ne commite pas : il affiche ce qui a changé et la commande de commit.
# A supprimer quand feature/docKART deviendra main.

set -euo pipefail

cd "$(dirname "$0")"
MAIN_DIR="${MAIN_DIR:-../kart-main}"
PULL=1
while [ $# -gt 0 ]; do
  case "$1" in
    --no-pull) PULL=0 ;;
    --from) MAIN_DIR="$2"; shift ;;
    *) echo "Option inconnue : $1" >&2; exit 1 ;;
  esac
  shift
done

# --- garde-fous
branch=$(git branch --show-current)
if [ "$branch" = "main" ] || [ -z "$branch" ]; then
  echo "Erreur : à lancer sur feature/docKART ou une branche dérivée (branche actuelle : ${branch:-aucune})." >&2; exit 1
fi
if [ -n "$(git status --porcelain -- app requirements.txt requirements-dev.txt)" ]; then
  echo "Erreur : modifications non commitées dans app/ ou requirements*. Commite ou range-les d'abord." >&2
  git status --short -- app requirements.txt requirements-dev.txt >&2; exit 1
fi
if ! git -C "$MAIN_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  echo "Erreur : $MAIN_DIR introuvable. Crée-le avec : git worktree add $MAIN_DIR main" >&2; exit 1
fi
src_branch=$(git -C "$MAIN_DIR" branch --show-current)
if [ "$src_branch" != "main" ] && [ "$branch" = "feature/docKART" ]; then
  echo "Erreur : feature/docKART ne doit suivre que main (source : $src_branch)." >&2
  echo "  Crée une branche locale temporaire : git switch -c docKART-${src_branch##*/}" >&2; exit 1
fi

# --- mise à jour de main
if [ "$PULL" = 1 ]; then
  git -C "$MAIN_DIR" pull --ff-only
fi
main_sha=$(git -C "$MAIN_DIR" rev-parse --short HEAD)

# --- copie de main dans app/
rsync -r --delete --checksum \
  --exclude .git --exclude __pycache__ --exclude '*.pyc' --exclude .DS_Store \
  --exclude /requirements.txt --exclude /requirements-dev.txt --exclude /.gitignore \
  --exclude /.travis.yml --exclude /entrypoint.sh --exclude /openapi-schema.json --exclude /transferring \
  --exclude /kart/site_settings.py --exclude /media --exclude /static \
  "$MAIN_DIR"/ app/

# --- settings.py : version de main + CorsMiddleware remonté en tête
python3 - app/kart/settings.py <<'PY'
import re, sys
path = sys.argv[1]
s = open(path, encoding='utf-8').read()
cors = "'corsheaders.middleware.CorsMiddleware',"
m = re.search(r"^MIDDLEWARE = [\(\[]\n", s, flags=re.M)
if not m or cors not in s:
    print("ATTENTION : MIDDLEWARE ou CorsMiddleware introuvable dans settings.py : remets CorsMiddleware en tête à la main.")
    sys.exit(0)
s = re.sub(r"^[ \t]*" + re.escape(cors) + r"[ \t]*\n", "", s, count=1, flags=re.M)
block = ("    # CorsMiddleware doit passer avant les middlewares qui generent la\n"
         "    # reponse (CommonMiddleware, CsrfViewMiddleware, ...) sinon les headers\n"
         "    # CORS ne sont jamais ajoutes et le front Vue en localhost:5173 se fait\n"
         "    # bloquer par le navigateur (voir doc django-cors-headers).\n"
         "    " + cors + "\n")
s = s[:m.end()] + block + s[m.end():]
open(path, 'w', encoding='utf-8').write(s)
print("settings.py : version de la source, CorsMiddleware remonté en tête.")
PY

# --- requirements : versions de main reportées dans ceux de la racine (ajouts Docker conservés)
for f in requirements.txt requirements-dev.txt; do
  [ -f "$MAIN_DIR/$f" ] || continue
  python3 - "$MAIN_DIR/$f" "$f" <<'PY'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
key = lambda line: re.split(r"[=<>!~ ;]", line.strip(), 1)[0].lower()  # extras inclus : pkg[x] != pkg
pkg = lambda line: line.strip() and not line.lstrip().startswith('#')
main_lines = [l.rstrip('\n') for l in open(src, encoding='utf-8')]
main_pkgs = {key(l): l.strip() for l in main_lines if pkg(l)}
out, seen, changed = [], set(), []
for l in open(dst, encoding='utf-8').read().splitlines():
    k = key(l) if pkg(l) else None
    if k and k in main_pkgs:
        seen.add(k)
        if l.strip() != main_pkgs[k]:
            changed.append(f"    {l.strip()} -> {main_pkgs[k]}")
            l = main_pkgs[k]
    out.append(l)
open(dst, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
if changed:
    print(f"{dst} : versions alignées sur main :"); print('\n'.join(changed))
missing = [v for k, v in main_pkgs.items() if k not in seen and not any(key(x) == k for x in out if pkg(x))]
if missing:
    print(f"ATTENTION : {dst} : paquets de main absents de la racine, à ajouter à la main :")
    print('\n'.join('    ' + v for v in missing))
PY
done

# --- bilan
echo
if [ -z "$(git status --porcelain -- app requirements.txt requirements-dev.txt)" ]; then
  echo "Déjà à jour avec $src_branch ($main_sha). Rien à commiter."
else
  git status --short -- app requirements.txt requirements-dev.txt
  echo
  echo "Vérifie (git diff), puis :"
  echo "  git add -A app requirements.txt requirements-dev.txt && git commit -m \"chore: sync app/ with $src_branch ($main_sha)\""
fi
