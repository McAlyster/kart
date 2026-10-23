#!/usr/bin/env bash
# sync-app.sh — recopie une branche de KART dans app/ (dépôt dockerisé).
#
# Organisation des dossiers (worktrees git d'un même dépôt), dans KART/ :
#
#   dossier                    branche                            rôle
#   src-main/                  main                               source (instance KART d'origine)
#   src-candidature2027/       feature/candidature2027            source (instance Kandidature)
#   docker-main/               feature/docKART                    version Docker de src-main
#   docker-candidature2027/    feature/docKART-candidature2027    version Docker de src-candidature2027
#
# Lancé depuis un dossier docker-X, le script recopie app/ depuis le dossier src-X voisin.
#
# Règle : app/ doit rester identique à la source. Seuls diffèrent les fichiers
# Docker/outillage (racine du dépôt + exclusions ci-dessous) et un écart de fond
# toléré : CorsMiddleware placé en tête dans app/kart/settings.py (sinon le front
# Vue en localhost est bloqué par CORS).
#
# Prérequis (une fois) :
#   git worktree add ../src-main              main
#   git worktree add ../src-candidature2027   feature/candidature2027
#
# Usage : ./sync-app.sh                  (source déduite de la branche courante, avec pull)
#         ./sync-app.sh --no-pull        (sans mettre à jour la source)
#         ./sync-app.sh --from <dossier> (autre worktree source, pour une branche hors tableau)
#
# Le script ne commite pas : il affiche ce qui a changé et la commande de commit.

set -euo pipefail

cd "$(dirname "$0")"

branch=$(git branch --show-current)
case "$branch" in
  feature/docKART)                 SRC_DIR=../src-main;              EXPECTED=main ;;
  feature/docKART-candidature2027) SRC_DIR=../src-candidature2027;   EXPECTED=feature/candidature2027 ;;
  *)                               SRC_DIR="";                       EXPECTED="" ;;
esac

PULL=1
while [ $# -gt 0 ]; do
  case "$1" in
    --no-pull) PULL=0 ;;
    --from) SRC_DIR="$2"; shift ;;
    *) echo "Option inconnue : $1" >&2; exit 1 ;;
  esac
  shift
done

# --- garde-fous
if [ -z "$branch" ] || [ "$branch" = "main" ]; then
  echo "Erreur : à lancer depuis une branche dockerisée (branche actuelle : ${branch:-aucune})." >&2; exit 1
fi
if [ -z "$SRC_DIR" ]; then
  echo "Erreur : pas de source connue pour la branche $branch. Précise-la : --from <worktree>." >&2; exit 1
fi
if [ -n "$(git status --porcelain -- app requirements.txt requirements-dev.txt)" ]; then
  echo "Erreur : modifications non commitées dans app/ ou requirements*. Commite ou range-les d'abord." >&2
  git status --short -- app requirements.txt requirements-dev.txt >&2; exit 1
fi
if ! git -C "$SRC_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  echo "Erreur : $SRC_DIR introuvable. Crée-le avec : git worktree add $SRC_DIR ${EXPECTED:-<branche>}" >&2; exit 1
fi
src_branch=$(git -C "$SRC_DIR" branch --show-current)
if [ -n "$EXPECTED" ] && [ "$src_branch" != "$EXPECTED" ]; then
  echo "Erreur : $branch doit suivre $EXPECTED, mais $SRC_DIR est sur $src_branch." >&2; exit 1
fi

# --- mise à jour de la source
if [ "$PULL" = 1 ]; then
  git -C "$SRC_DIR" pull --ff-only
fi
src_sha=$(git -C "$SRC_DIR" rev-parse --short HEAD)
echo "Synchro de app/ ($branch) depuis $src_branch ($src_sha)"
echo

# --- copie de la source dans app/
rsync -r --delete --checksum \
  --exclude .git --exclude __pycache__ --exclude '*.pyc' --exclude .DS_Store \
  --exclude /requirements.txt --exclude /requirements-dev.txt --exclude /.gitignore \
  --exclude /.travis.yml --exclude /entrypoint.sh --exclude /openapi-schema.json --exclude /transferring \
  --exclude /kart/site_settings.py --exclude /media --exclude /static \
  "$SRC_DIR"/ app/

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

# --- requirements : versions de la source reportées dans ceux de la racine (ajouts Docker conservés)
for f in requirements.txt requirements-dev.txt; do
  [ -f "$SRC_DIR/$f" ] || continue
  python3 - "$SRC_DIR/$f" "$f" <<'PY'
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
    print(f"{dst} : versions alignées sur la source :"); print('\n'.join(changed))
missing = [v for k, v in main_pkgs.items() if k not in seen and not any(key(x) == k for x in out if pkg(x))]
if missing:
    print(f"ATTENTION : {dst} : paquets de la source absents de la racine, à ajouter à la main :")
    print('\n'.join('    ' + v for v in missing))
PY
done

# --- bilan
echo
if [ -z "$(git status --porcelain -- app requirements.txt requirements-dev.txt)" ]; then
  echo "Déjà à jour avec $src_branch ($src_sha). Rien à commiter."
else
  git status --short -- app requirements.txt requirements-dev.txt
  echo
  echo "Vérifie (git diff), puis :"
  echo "  git add -A app requirements.txt requirements-dev.txt && git commit -m \"chore: sync app/ with $src_branch ($src_sha)\""
fi
