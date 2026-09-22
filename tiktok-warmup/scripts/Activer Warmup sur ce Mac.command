#!/bin/bash
# Double-clique ce fichier dans le Finder (une seule fois).
# Il installe l’agent Mac : plus besoin de taper des commandes.
set -euo pipefail
cd "$(dirname "$0")/.."
clear
echo ""
echo "  Warmup Peachtint — activation sur ce Mac"
echo "  (cette fenêtre peut se fermer quand c’est fini)"
echo ""
/usr/bin/python3 -m agent.install_mac 2>&1 || {
  echo ""
  echo "  Échec. Vérifie que Xcode Command Line Tools est installé."
  echo "  (Réglages → Général → Mise à jour → outils développeur)"
  echo ""
  read -r -p "Appuie sur Entrée pour fermer…"
  exit 1
}
sleep 3
