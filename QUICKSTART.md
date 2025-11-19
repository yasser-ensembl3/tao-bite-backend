# 🚀 Quick Start Guide

## Option 1 : Lancement ultra-rapide (recommandé)

### macOS / Linux

```bash
cd backend
./start.sh
```

### Windows

```cmd
cd backend
start.bat
```

Le script s'occupe automatiquement de :
- ✅ Créer l'environnement virtuel
- ✅ Installer les dépendances
- ✅ Vérifier la configuration
- ✅ Lancer le serveur

---

## Option 2 : Lancement manuel

### Étape 1 : Créer l'environnement virtuel

```bash
python3 -m venv venv
```

### Étape 2 : Activer l'environnement

**macOS/Linux :**
```bash
source venv/bin/activate
```

**Windows :**
```cmd
venv\Scripts\activate
```

### Étape 3 : Installer les dépendances

```bash
pip install -r requirements.txt
```

### Étape 4 : Configurer les clés API

1. Copiez le fichier de configuration :
   ```bash
   cp .env.example .env
   ```

2. Éditez `.env` et ajoutez vos clés :
   ```env
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   LLAMA_CLOUD_API_KEY=llx-...
   ```

### Étape 5 : Lancer le serveur

```bash
python app.py
```

---

## 🎯 Vérifier que ça fonctionne

Une fois le serveur lancé, ouvrez votre navigateur :

**Test API :**
```
http://localhost:8080/api/database/stats
```

Vous devriez voir un JSON avec les statistiques de la base de données.

---

## 📝 Obtenir les clés API

### OpenAI (requis - pour les embeddings)
1. Allez sur https://platform.openai.com/api-keys
2. Créez une clé API
3. Copiez-la dans `.env`

### Anthropic Claude (requis - pour la génération de contenu)
1. Allez sur https://console.anthropic.com/
2. Créez une clé API
3. Copiez-la dans `.env`

### LlamaParse (optionnel - pour PDFs complexes)
1. Allez sur https://cloud.llamaindex.ai/
2. Créez un compte et obtenez une clé API
3. Copiez-la dans `.env`

### Qdrant Cloud (optionnel - sinon utilise le stockage local)
1. Allez sur https://cloud.qdrant.io/
2. Créez un cluster gratuit
3. Copiez l'URL et la clé API dans `.env`

---

## 🆘 Problèmes fréquents

### "python3: command not found"
- Sur Windows, utilisez `python` au lieu de `python3`
- Installez Python depuis https://www.python.org/downloads/

### "pip: command not found"
```bash
python -m pip install -r requirements.txt
```

### "Port 8080 already in use"
1. Ouvrez `app.py`
2. Cherchez la ligne `app.run(host='0.0.0.0', port=8080, debug=True)`
3. Changez `8080` par `8081` ou un autre port

### Le serveur démarre mais les API ne fonctionnent pas
- Vérifiez que vos clés API dans `.env` sont valides
- Redémarrez le serveur après avoir modifié `.env`

---

## 🎨 Interface Web (optionnel)

Ce dossier contient uniquement le backend. Pour l'interface web complète :
1. Retournez au dossier parent : `cd ..`
2. Lancez l'application principale : `python app.py`

L'interface sera disponible sur http://localhost:8080

---

## 💡 Conseils

- **En développement** : Le mode debug est activé, le serveur redémarre automatiquement à chaque modification
- **En production** : Utilisez Gunicorn ou Waitress (voir README.md)
- **Stockage** : Par défaut, les fichiers sont stockés dans `./uploads/` et `./outputs/`
- **Base de données** : Si vous n'utilisez pas Qdrant Cloud, la base locale est dans `./qdrant_storage/`
