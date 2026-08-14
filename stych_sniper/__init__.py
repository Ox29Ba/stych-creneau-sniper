"""stych_sniper — bot de veille des créneaux de conduite Stych.

Modules :
  - config    : chargement de la config (filtres) + secrets (env)
  - client    : connexion à Stych et récupération des créneaux
  - filters   : application des filtres utilisateur
  - state     : mémoire des créneaux déjà vus (détection des nouveaux)
  - notifier  : envoi des notifications Telegram
"""

__version__ = "1.0.0"
