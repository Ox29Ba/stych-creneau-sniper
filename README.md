# 🚗 Stych Créneau Sniper

> Bot de veille qui surveille en continu les créneaux de conduite sur
> [Stych](https://www.stych.fr) et t'envoie une **notification Telegram**
> dès qu'une place se libère (typiquement les désistements de dernière minute).

Réserver ses heures de conduite chez Stych, c'est la course : les bons
créneaux partent vite, et les places qui se libèrent (désistements la veille)
sont impossibles à attraper si on rafraîchit le site à la main. Ce bot fait
le guet pour toi, 24h/24, et te prévient en quelques secondes.

**Fonctionne pour n'importe quel élève Stych** : il te suffit de tes propres
identifiants et d'un bot Telegram (tout est expliqué plus bas).

---

## ✨ Fonctionnalités

- 🔔 **Notification Telegram** instantanée dès qu'un nouveau créneau apparaît.
- 🎯 **Filtres puissants et configurables** (sans toucher au code) :
  lieu (département / ville / code postal / arrêt), durée, jour, plage de
  dates, plage horaire, moniteur, nombre de crédits.
- 🧠 **Anti-spam** : ne te prévient que pour les créneaux **jamais vus**, pas à
  chaque vérification.
- 📈 **Historique des désistements** : chaque place détectée est journalisée dans
  `historique.csv` (heure de détection, date, lieu…) pour repérer les habitudes.
- ☁️ **24/7 gratuit** via GitHub Actions (ton Mac peut rester éteint).
- 🪶 **Léger** : de simples requêtes HTTP (pas de navigateur), une exécution
  prend quelques secondes.

---

## ⚠️ Avertissement

Projet **non officiel**, sans aucun lien avec Stych. Il automatise
simplement la consultation de **ton propre compte**. Utilise-le de manière
raisonnable (l'intervalle par défaut de 5 minutes est volontairement modéré) :
un usage trop agressif pourrait surcharger le service ou aller à l'encontre de
ses conditions d'utilisation. **Tu es responsable de l'usage que tu en fais.**
Le bot ne réserve rien automatiquement : il te **prévient**, c'est toi qui
réserves.

---

## 🚀 Démarrage rapide

### 1. Prérequis

- Python 3.10+
- Un compte élève Stych
- Un compte Telegram

### 2. Créer ton bot Telegram (2 min)

1. Sur Telegram, ouvre **[@BotFather](https://t.me/BotFather)**, envoie `/newbot`
   et suis les instructions. Il te donne un **token** (`123456789:AA...`).
2. Ouvre **[@userinfobot](https://t.me/userinfobot)** et lance-le : il te donne
   ton **chat ID** (un nombre).
3. **Important** : envoie un premier message (« bonjour ») à TON bot, sinon il
   n'a pas le droit de t'écrire.

### 3. Installer

```bash
git clone https://github.com/<ton-user>/stych-creneau-sniper.git
cd stych-creneau-sniper
pip install -r requirements.txt

cp .env.example .env               # puis remplis tes secrets
cp config.example.yaml config.yaml # puis règle tes filtres
```

Édite `.env` avec tes identifiants Stych + ton token/chat ID Telegram.

### 4. Tester

```bash
python main.py --test-telegram   # tu dois recevoir un message de test
python main.py --list-lieux      # affiche tous les lieux et leurs id
python main.py --dry-run         # cherche les créneaux SANS notifier
```

Quand tout marche :

```bash
python main.py
```

---

## 🎯 Configurer les filtres

Tout se passe dans `config.yaml`. **Tout est optionnel** — un critère vide est
ignoré. Un créneau est retenu s'il passe **tous** les critères définis.

Exemple : « seulement le week-end, à Paris ou Vincennes, après 17h, en 1h30 » :

```yaml
filtres:
  departements: ["75", "94"]
  villes: ["PARIS", "VINCENNES"]
  jours: [6, 7]            # samedi, dimanche
  heure_min: "17:00"
  durees_exactes: [1.5]    # 1h30
```

| Filtre            | Exemple                | Effet                                           |
|-------------------|------------------------|-------------------------------------------------|
| `departements`    | `["75", "94"]`         | Codes département                               |
| `villes`          | `["PARIS"]`            | Nom de ville (insensible à la casse)            |
| `codes_postaux`   | `["75011"]`            | Code postal exact                               |
| `arrets`          | `["Nation"]`           | Texte dans le nom de l'arrêt                    |
| `lieux_ids`       | `["210"]`              | id de lieu précis (voir `--list-lieux`)         |
| `duree_min/max`   | `1.5`                  | Durée en heures (0.75 = 45 min, 1.5 = 1h30)     |
| `durees_exactes`  | `[1.5]`                | Ne garder que ces durées                        |
| `credits_max`     | `2`                    | Ignore les créneaux trop coûteux en crédits     |
| `jours`           | `[6, 7]`               | 1 = lundi … 7 = dimanche                        |
| `date_debut/fin`  | `"2026-09-01"`         | Plage de dates (AAAA-MM-JJ)                      |
| `heure_min/max`   | `"17:00"`              | Fenêtre sur l'heure de **début**                |
| `moniteurs`       | `["Gregory"]`          | Nom (partiel) du moniteur                       |

> 💡 Lance `python main.py --list-lieux` pour lister tous les lieux avec leurs
> départements, villes, arrêts et id.

---

## ☁️ Faire tourner 24/7 gratuitement (GitHub Actions)

Le dépôt inclut un workflow (`.github/workflows/check-slots.yml`) qui lance la
vérification **toutes les 5 minutes**, gratuitement, même ordinateur éteint.

1. **Fork / pousse** ce dépôt sur ton GitHub (repo **public** = minutes Actions
   gratuites et illimitées ; tes secrets restent chiffrés).
2. Dans le dépôt : **Settings → Secrets and variables → Actions → New
   repository secret**, et crée ces 4 secrets :
   - `STYCH_EMAIL`
   - `STYCH_PASSWORD`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Onglet **Actions** → active les workflows.
4. Règle tes filtres dans `config.yaml` et commite.
5. (Optionnel) Lance-le à la main une première fois : **Actions → Veille
   créneaux Stych → Run workflow**.

Le bot mémorise les créneaux déjà vus dans `state.json`, re-commité
automatiquement quand il change (pour ne pas te renotifier les mêmes places).

> 🔐 **Tes secrets ne sont jamais dans le code** ni dans l'historique git. Même
> avec un dépôt public, GitHub les garde chiffrés et invisibles.

---

## 🖥️ Alternative : sur ton Mac (cron)

Pour lancer toutes les 5 minutes en local (le Mac doit rester allumé) :

```bash
crontab -e
```

puis ajoute (adapte le chemin) :

```cron
*/5 * * * * cd /chemin/vers/stych-creneau-sniper && /usr/bin/python3 main.py >> bot.log 2>&1
```

---

## 🧩 Comment ça marche

```
GitHub Actions (cron 5 min)
        │
        ▼
   main.py
        │  1. login()  ── POST /connexion/0/record3 (email + mdp)
        │  2. fetch    ── POST /elearning/planning-conduite/get-planning-proposition
        │  3. filtre   ── config.yaml
        │  4. diff     ── state.json (créneaux déjà vus)
        ▼
   Nouveaux créneaux ? ──► Notification Telegram 🔔
```

- `stych_sniper/client.py` — connexion + appel de l'API planning (JSON).
- `stych_sniper/filters.py` — logique de filtrage + description lisible.
- `stych_sniper/state.py` — mémoire des créneaux déjà vus.
- `stych_sniper/notifier.py` — envoi Telegram.
- `main.py` — orchestration + options CLI.

---

## 📈 Historique des désistements

Stych n'expose pas l'historique des annulations passées. Le bot le **construit
lui-même** : chaque nouveau créneau détecté est ajouté à `historique.csv` avec
son heure de détection. Après quelques jours, tu peux ouvrir ce fichier (Excel,
Numbers…) pour repérer **quand** les désistements tombent le plus souvent à tes
lieux, et être prêt au bon moment.

## ❓ FAQ

**Le bot réserve-t-il le créneau à ma place ?**
Non. Il te **notifie** ; tu réserves toi-même (une place se prend en quelques
clics, et une réservation automatique serait bien plus risquée).

**Toutes les 5 min, c'est assez ?**
Pour attraper des désistements, oui. Tu peux ajuster le `cron` dans le
workflow, mais évite de descendre trop bas (respect du service + limites
GitHub).

**Mes identifiants sont-ils en sécurité ?**
Ils ne sont **jamais** dans le code. En local ils vivent dans `.env` (ignoré
par git) ; sur GitHub, dans les Secrets chiffrés.

**Ça marche pour une autre auto-école que la mienne ?**
Oui, tant que c'est un compte Stych. Les lieux/filtres s'adaptent à ce que
propose ton agence.

---

## 📄 Licence

[MIT](LICENSE) — libre d'utilisation, de modification et de partage.
