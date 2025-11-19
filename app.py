"""
Flask Web Application for PDF to Markdown Conversion
Provides a web interface to upload PDFs and convert them using LlamaParse
"""

from flask import Flask, render_template, request, send_file, jsonify, flash, redirect, url_for
import os
from werkzeug.utils import secure_filename
from pathlib import Path
import threading
import uuid
from datetime import datetime
from llama_parse import LlamaParse
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import anthropic
from dotenv import load_dotenv
from obsidian_pdf_converter import ObsidianPDFConverter
import pdfplumber
from pypdf import PdfReader

# Load environment variables from .env file
load_dotenv()

# Configuration des API from environment variables
LLAMA_CLOUD_API_KEY = os.getenv('LLAMA_CLOUD_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# Qdrant Cloud Configuration
QDRANT_URL = os.getenv('QDRANT_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')

# Validate API keys
if not all([LLAMA_CLOUD_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY]):
    raise ValueError("Missing API keys. Please check your .env file. Copy .env.example to .env and fill in your keys.")

# Initialiser les clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Qdrant client - Lazy initialization
_qdrant_client = None

def get_qdrant_client():
    """Obtenir le client Qdrant (lazy initialization)."""
    global _qdrant_client
    if _qdrant_client is None:
        # Use Qdrant Cloud if URL and API key are provided
        if QDRANT_URL and QDRANT_API_KEY:
            print(f"✓ Connecting to Qdrant Cloud: {QDRANT_URL}")
            _qdrant_client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY,
                timeout=60  # Increase timeout for cloud connection
            )
        else:
            # Fallback to local storage
            print("✓ Using local Qdrant storage: ./qdrant_storage")
            _qdrant_client = QdrantClient(
                path="./qdrant_storage",
                force_disable_check_same_thread=True  # Fix SQLite threading issue with Flask
            )
    return _qdrant_client

app = Flask(__name__)
app.secret_key = 'votre-cle-secrete-changez-moi'  # Changez ceci en production
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

# Créer les dossiers s'ils n'existent pas
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Stocker l'état des conversions
conversions = {}

# Stocker l'état des conversions Obsidian
obsidian_conversions = {}

# Initialiser le parser LlamaParse
parser = LlamaParse(
    api_key=LLAMA_CLOUD_API_KEY,
    result_type="markdown",  # Retourne directement du markdown
    verbose=True,
    language="fr"  # Spécifier le français
)

# Initialiser le text splitter pour chunking intelligent
def create_text_splitter(chunk_size=1000, chunk_overlap=200):
    """Créer un text splitter optimisé pour le markdown."""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=lambda text: len(tiktoken.get_encoding("cl100k_base").encode(text)),
        separators=["\n\n", "\n", " ", ""],  # Priorité: paragraphes, lignes, espaces
        is_separator_regex=False
    )


def chunk_markdown(markdown_text, chunk_size=1000, chunk_overlap=200):
    """
    Découper le markdown en chunks intelligents.

    Args:
        markdown_text: Texte markdown à découper
        chunk_size: Taille maximale en tokens (défaut: 1000)
        chunk_overlap: Chevauchement entre chunks pour maintenir le contexte (défaut: 200)

    Returns:
        Liste de dictionnaires contenant les chunks et leurs métadonnées
    """
    text_splitter = create_text_splitter(chunk_size, chunk_overlap)
    chunks = text_splitter.split_text(markdown_text)

    # Encoder pour compter les tokens précisément
    encoding = tiktoken.get_encoding("cl100k_base")

    # Créer des métadonnées pour chaque chunk
    chunk_data = []
    for i, chunk in enumerate(chunks):
        tokens = encoding.encode(chunk)
        chunk_data.append({
            'chunk_id': i + 1,
            'content': chunk,
            'token_count': len(tokens),
            'char_count': len(chunk),
            'preview': chunk[:100] + '...' if len(chunk) > 100 else chunk
        })

    return chunk_data


def get_openai_embeddings(texts, model="text-embedding-3-small"):
    """
    Générer des embeddings avec OpenAI.

    Args:
        texts: Liste de textes à encoder
        model: Modèle OpenAI à utiliser

    Returns:
        Liste de vecteurs d'embeddings
    """
    response = openai_client.embeddings.create(
        model=model,
        input=texts
    )
    return [item.embedding for item in response.data]


def ensure_qdrant_collection(collection_name, vector_size=1536):
    """Créer une collection Qdrant si elle n'existe pas."""
    client = get_qdrant_client()
    try:
        client.get_collection(collection_name)
        print(f"✓ Collection '{collection_name}' existe déjà")
    except Exception:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
        print(f"✓ Collection '{collection_name}' créée")


def inject_to_qdrant(chunks, collection_name="pdf_documents", job_id=None, filename=None):
    """
    Injecter les chunks dans Qdrant avec embeddings OpenAI.

    Args:
        chunks: Liste de chunks avec contenu et métadonnées
        collection_name: Nom de la collection Qdrant
        job_id: ID du job (optionnel)
        filename: Nom du fichier source (optionnel)

    Returns:
        Dictionnaire avec statistiques d'injection
    """
    # S'assurer que la collection existe
    ensure_qdrant_collection(collection_name)

    # Extraire les textes des chunks
    texts = [chunk['content'] for chunk in chunks]

    # Générer les embeddings par batch (OpenAI limite à 2048 textes par requête)
    batch_size = 100
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        embeddings = get_openai_embeddings(batch_texts)
        all_embeddings.extend(embeddings)
        print(f"✓ Embeddings générés: {len(all_embeddings)}/{len(texts)}")

    # Créer les points pour Qdrant
    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, all_embeddings)):
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "text": chunk['content'],
                "chunk_id": chunk['chunk_id'],
                "token_count": chunk['token_count'],
                "char_count": chunk['char_count'],
                "job_id": job_id,
                "filename": filename,
                "source": "llamaparse"
            }
        )
        points.append(point)

    # Injecter dans Qdrant
    client = get_qdrant_client()
    client.upsert(
        collection_name=collection_name,
        points=points
    )

    # Statistiques
    collection_info = client.get_collection(collection_name)

    return {
        "injected_chunks": len(points),
        "total_tokens": sum(chunk['token_count'] for chunk in chunks),
        "collection_name": collection_name,
        "total_vectors_in_collection": collection_info.points_count
    }


def convert_pdf_async(job_id, pdf_path, output_path):
    """Convertir un PDF en arrière-plan avec pdfplumber (fallback: LlamaParse)."""
    global conversions

    print(f"[Job {job_id}] Thread démarré! Début du traitement...")

    method_used = None
    full_text = None
    pages_count = 0

    try:
        # Try pdfplumber first
        conversions[job_id]['status'] = 'processing'
        conversions[job_id]['message'] = 'Extraction avec pdfplumber...'

        print(f"[Job {job_id}] Trying pdfplumber: {pdf_path}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                markdown_lines = []
                pages_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        markdown_lines.append(f"---\n### Page {page_num} of {pages_count}\n")
                        markdown_lines.append(text)
                        markdown_lines.append("\n")

                full_text = "\n".join(markdown_lines)

                # Quality gate
                if len(full_text.strip()) < 100:
                    raise ValueError(f"Text too short ({len(full_text)} chars)")

                method_used = "pdfplumber"
                print(f"[Job {job_id}] ✓ pdfplumber successful")

        except Exception as pdfplumber_error:
            print(f"[Job {job_id}] ⚠️  pdfplumber failed: {str(pdfplumber_error)}")

            # Fallback to LlamaParse
            conversions[job_id]['message'] = 'pdfplumber échoué, essai avec LlamaParse...'
            print(f"[Job {job_id}] Trying LlamaParse fallback...")

            try:
                documents = parser.load_data(pdf_path)
                full_text = "\n\n".join([doc.text for doc in documents])
                pages_count = len(documents)

                if len(full_text.strip()) < 100:
                    raise ValueError(f"Text too short ({len(full_text)} chars)")

                method_used = "llamaparse"
                print(f"[Job {job_id}] ✓ LlamaParse successful")

            except Exception as llamaparse_error:
                print(f"[Job {job_id}] ❌ LlamaParse also failed: {str(llamaparse_error)}")
                raise ValueError(f"Both methods failed. pdfplumber: {str(pdfplumber_error)}, LlamaParse: {str(llamaparse_error)}")

        print(f"[Job {job_id}] Conversion réussie avec {method_used}, sauvegarde...")
        conversions[job_id]['message'] = f'Sauvegarde du markdown ({method_used})...'

        # Sauvegarder le markdown
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)

        print(f"[Job {job_id}] Terminé avec {method_used}!")
        conversions[job_id]['status'] = 'completed'
        conversions[job_id]['message'] = f'Conversion terminée ({method_used})!'
        conversions[job_id]['output_path'] = output_path
        conversions[job_id]['pages'] = pages_count
        conversions[job_id]['method'] = method_used
        conversions[job_id]['completed_at'] = datetime.now().isoformat()

    except Exception as e:
        print(f"[Job {job_id}] ERREUR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        conversions[job_id]['status'] = 'error'
        conversions[job_id]['message'] = f'Erreur: {str(e)}'


@app.route('/')
def index():
    """Page d'accueil avec formulaire d'upload."""
    return render_template('index.html', models_loaded=True)


@app.route('/admin')
def admin():
    """Admin page for uploading documents."""
    return render_template('admin.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Gérer l'upload du fichier PDF."""
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Seuls les fichiers PDF sont acceptés'}), 400

    try:
        # Créer un ID unique pour ce job
        job_id = str(uuid.uuid4())

        # Sauvegarder le fichier
        filename = secure_filename(file.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
        file.save(pdf_path)

        # Préparer le chemin de sortie
        output_filename = Path(filename).stem + '.md'
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{job_id}_{output_filename}")

        # Initialiser l'état de la conversion
        conversions[job_id] = {
            'status': 'queued',
            'message': 'En attente...',
            'filename': filename,
            'pdf_path': pdf_path,
            'output_path': output_path,
            'started_at': datetime.now().isoformat()
        }

        # Lancer la conversion en arrière-plan
        thread = threading.Thread(
            target=convert_pdf_async,
            args=(job_id, pdf_path, output_path)
        )
        thread.daemon = True
        thread.start()

        print(f"✓ Thread lancé pour job {job_id} (Thread ID: {thread.ident})")

        return jsonify({
            'job_id': job_id,
            'message': 'Conversion démarrée',
            'filename': filename
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/status/<job_id>')
def get_status(job_id):
    """Obtenir le statut d'une conversion."""
    if job_id not in conversions:
        return jsonify({'error': 'Job introuvable'}), 404

    return jsonify(conversions[job_id])


@app.route('/download/<job_id>')
def download_file(job_id):
    """Télécharger le fichier markdown converti."""
    if job_id not in conversions:
        return jsonify({'error': 'Job introuvable'}), 404

    conversion = conversions[job_id]

    if conversion['status'] != 'completed':
        return jsonify({'error': 'Conversion non terminée'}), 400

    output_path = conversion['output_path']

    if not os.path.exists(output_path):
        return jsonify({'error': 'Fichier introuvable'}), 404

    return send_file(
        output_path,
        as_attachment=True,
        download_name=os.path.basename(output_path).split('_', 1)[1]  # Retirer l'ID du nom
    )


@app.route('/models/status')
def models_status():
    """Vérifier le statut de l'API (toujours prêt avec LlamaParse)."""
    return jsonify({
        'loaded': True,
        'loading': False
    })


@app.route('/qdrant/collections')
def list_collections():
    """Lister toutes les collections Qdrant."""
    try:
        client = get_qdrant_client()
        collections = client.get_collections().collections

        collections_info = []
        for col in collections:
            info = client.get_collection(col.name)
            collections_info.append({
                'name': col.name,
                'vectors_count': info.points_count,
                'vector_size': info.config.params.vectors.size
            })

        return jsonify({'collections': collections_info})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/qdrant/search', methods=['POST'])
def search_qdrant():
    """Rechercher dans Qdrant avec une requête texte."""
    try:
        data = request.get_json()
        query = data.get('query', '')
        collection_name = data.get('collection_name', 'pdf_documents')
        limit = data.get('limit', 5)

        if not query:
            return jsonify({'error': 'Query is required'}), 400

        # Générer l'embedding de la requête
        embedding = get_openai_embeddings([query])[0]

        # Rechercher dans Qdrant
        client = get_qdrant_client()
        results = client.search(
            collection_name=collection_name,
            query_vector=embedding,
            limit=limit,
            with_payload=True
        )

        # Formater les résultats
        search_results = []
        for hit in results:
            search_results.append({
                'score': hit.score,
                'text': hit.payload.get('text', ''),
                'chunk_id': hit.payload.get('chunk_id'),
                'filename': hit.payload.get('filename'),
                'token_count': hit.payload.get('token_count')
            })

        return jsonify({
            'query': query,
            'results': search_results,
            'count': len(search_results)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/qdrant/viewer')
def qdrant_viewer():
    """Page de visualisation Qdrant."""
    return render_template('qdrant_viewer.html')


@app.route('/chunk/<job_id>', methods=['POST'])
def chunk_document(job_id):
    """
    Découper un document markdown en chunks intelligents.

    Body JSON:
    {
        "chunk_size": 1000,  # optionnel, défaut: 1000 tokens
        "chunk_overlap": 200  # optionnel, défaut: 200 tokens
    }
    """
    if job_id not in conversions:
        return jsonify({'error': 'Job introuvable'}), 404

    conversion = conversions[job_id]

    if conversion['status'] != 'completed':
        return jsonify({'error': 'Conversion non terminée'}), 400

    output_path = conversion['output_path']

    if not os.path.exists(output_path):
        return jsonify({'error': 'Fichier markdown introuvable'}), 404

    try:
        # Lire le paramètres
        data = request.get_json() or {}
        chunk_size = data.get('chunk_size', 1000)
        chunk_overlap = data.get('chunk_overlap', 200)

        # Lire le markdown
        with open(output_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()

        # Chunker le texte
        chunks = chunk_markdown(markdown_text, chunk_size, chunk_overlap)

        # Calculer les statistiques
        total_tokens = sum(chunk['token_count'] for chunk in chunks)

        return jsonify({
            'job_id': job_id,
            'filename': conversion['filename'],
            'total_chunks': len(chunks),
            'total_tokens': total_tokens,
            'chunk_size': chunk_size,
            'chunk_overlap': chunk_overlap,
            'chunks': chunks
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/inject/<job_id>', methods=['POST'])
def inject_document(job_id):
    """
    Injecter un document chunké dans Qdrant avec embeddings OpenAI.

    Body JSON:
    {
        "chunk_size": 1000,  # optionnel, défaut: 1000 tokens
        "chunk_overlap": 200,  # optionnel, défaut: 200 tokens
        "collection_name": "pdf_documents"  # optionnel, défaut: "pdf_documents"
    }
    """
    if job_id not in conversions:
        return jsonify({'error': 'Job introuvable'}), 404

    conversion = conversions[job_id]

    if conversion['status'] != 'completed':
        return jsonify({'error': 'Conversion non terminée'}), 400

    output_path = conversion['output_path']

    if not os.path.exists(output_path):
        return jsonify({'error': 'Fichier markdown introuvable'}), 404

    try:
        # Lire les paramètres
        data = request.get_json() or {}
        chunk_size = data.get('chunk_size', 1000)
        chunk_overlap = data.get('chunk_overlap', 200)
        collection_name = data.get('collection_name', 'pdf_documents')

        # Lire le markdown
        with open(output_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()

        # Chunker le texte
        chunks = chunk_markdown(markdown_text, chunk_size, chunk_overlap)

        # Injecter dans Qdrant
        stats = inject_to_qdrant(
            chunks,
            collection_name=collection_name,
            job_id=job_id,
            filename=conversion['filename']
        )

        return jsonify({
            'job_id': job_id,
            'filename': conversion['filename'],
            'success': True,
            **stats
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/auto-pipeline/<job_id>', methods=['POST'])
def auto_pipeline(job_id):
    """
    Pipeline automatique : Chunking + Embeddings + Injection dans Qdrant.

    Body JSON:
    {
        "chunk_size": 1000,  # optionnel
        "chunk_overlap": 200,  # optionnel
        "collection_name": "pdf_documents"  # optionnel
    }
    """
    if job_id not in conversions:
        return jsonify({'error': 'Job introuvable'}), 404

    conversion = conversions[job_id]

    if conversion['status'] != 'completed':
        return jsonify({'error': 'Conversion non terminée'}), 400

    output_path = conversion['output_path']

    if not os.path.exists(output_path):
        return jsonify({'error': 'Fichier markdown introuvable'}), 404

    try:
        # Lire les paramètres
        data = request.get_json() or {}
        chunk_size = data.get('chunk_size', 1000)
        chunk_overlap = data.get('chunk_overlap', 200)
        collection_name = data.get('collection_name', 'pdf_documents')

        # Étape 1 : Lire le markdown
        with open(output_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()

        # Étape 2 : Chunker le texte
        chunks = chunk_markdown(markdown_text, chunk_size, chunk_overlap)
        total_tokens = sum(chunk['token_count'] for chunk in chunks)

        # Étape 3 : Injecter dans Qdrant (avec embeddings)
        stats = inject_to_qdrant(
            chunks,
            collection_name=collection_name,
            job_id=job_id,
            filename=conversion['filename']
        )

        return jsonify({
            'job_id': job_id,
            'filename': conversion['filename'],
            'success': True,
            'total_chunks': len(chunks),
            'total_tokens': total_tokens,
            'method': conversion.get('method', 'unknown'),  # Add conversion method
            **stats
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/generate-draft', methods=['POST'])
def generate_draft():
    """
    Générer un draft de post Substack avec Claude.

    Body JSON:
    {
        "keywords": "decision-making, founder psychology",
        "collection_name": "pdf_documents",
        "top_k": 10
    }
    """
    try:
        data = request.get_json()
        keywords = data.get('keywords', '')
        collection_name = data.get('collection_name', 'pdf_documents')
        top_k = data.get('top_k', 10)

        if not keywords:
            return jsonify({'error': 'Keywords required'}), 400

        print(f"🔍 Génération de draft pour: '{keywords}'")

        # Étape 1: Recherche sémantique dans Qdrant
        embedding = get_openai_embeddings([keywords])[0]
        client = get_qdrant_client()

        results = client.search(
            collection_name=collection_name,
            query_vector=embedding,
            limit=top_k,
            with_payload=True
        )

        if not results:
            return jsonify({'error': 'Aucun contenu trouvé dans la base de données'}), 404

        # Étape 2: Préparer le contexte pour Claude
        context_chunks = []
        for hit in results:
            context_chunks.append({
                'text': hit.payload.get('text', ''),
                'score': hit.score,
                'filename': hit.payload.get('filename', 'unknown'),
                'chunk_id': hit.payload.get('chunk_id', 0)
            })

        # Construire le contexte textuel
        context_text = "\n\n---\n\n".join([
            f"[Source: {chunk['filename']}, Chunk #{chunk['chunk_id']}, Relevance: {chunk['score']:.2f}]\n{chunk['text']}"
            for chunk in context_chunks
        ])

        print(f"📚 Trouvé {len(context_chunks)} chunks pertinents")

        # Étape 3: Appeler Claude pour générer le draft
        prompt = f"""Tu es un curateur de connaissances pour le Substack "Tao of Founders".

Ta mission est d'extraire les citations et insights les plus pertinents issus de ma base de connaissances pour créer une note Substack courte.

MOTS-CLÉS: {keywords}

EXTRAITS DE MA BASE DE CONNAISSANCES:
{context_text}

INSTRUCTIONS:
Crée une note Substack courte (150-300 mots) qui met en avant les meilleures citations et insights.

FORMAT DE RÉPONSE:
1. Un titre court et accrocheur
2. Une phrase d'introduction (1-2 lignes)
3. 2-4 citations ou insights clés avec:
   - La citation exacte entre guillemets
   - Le nom de l'auteur ou la source du document
   - Un mini-commentaire de contexte si nécessaire (1 ligne)
4. Une phrase de conclusion (optionnelle, 1 ligne max)

STYLE:
- Direct et concis
- Met en valeur les citations, pas ton analyse
- Format type "notes de lecture" ou "highlights"
- Utilise des emojis pour les bullet points (📌, 💡, 🎯, etc.)

EXEMPLE DE FORMAT:
**Titre accrocheur**

Introduction en 1 ligne.

💡 "Citation exacte ici" — Auteur ou Source

📌 "Autre citation pertinente" — Auteur ou Source

🎯 "Troisième citation" — Auteur ou Source

Conclusion courte (optionnelle)."""

        message = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        draft = message.content[0].text

        print(f"✅ Draft généré ({len(draft)} caractères)")

        return jsonify({
            'success': True,
            'keywords': keywords,
            'chunks_found': len(context_chunks),
            'sources': [{'filename': c['filename'], 'score': c['score']} for c in context_chunks],
            'draft': draft,
            'usage': {
                'input_tokens': message.usage.input_tokens,
                'output_tokens': message.usage.output_tokens
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/draft-generator')
def draft_generator():
    """Page de génération de drafts Substack."""
    return render_template('draft_generator.html')


@app.route('/quote-extractor')
def quote_extractor():
    """Quote extraction page - raw citations without translation."""
    return render_template('quote_extractor.html')


@app.route('/generate-content', methods=['POST'])
def generate_content():
    """
    Generate content based on custom instructions using Claude AI.
    Uses relevance filtering to prevent hallucination.

    Body JSON:
    {
        "keywords": "decision-making, founder psychology",
        "instructions": "Extract the 5 best quotes...",
        "collection_name": "pdf_documents",
        "top_k": 10,
        "min_score": 0.3  # optionnel, seuil minimum de pertinence
    }
    """
    try:
        data = request.get_json()
        keywords = data.get('keywords', '')
        instructions = data.get('instructions', '')
        collection_name = data.get('collection_name', 'pdf_documents')
        top_k = data.get('top_k', 10)
        min_score = data.get('min_score', 0.3)  # Seuil de pertinence minimum

        if not keywords:
            return jsonify({'error': 'Keywords required'}), 400

        if not instructions:
            return jsonify({'error': 'Instructions required'}), 400

        print(f"🔍 Generating content for: '{keywords}'")
        print(f"📝 Instructions: {instructions[:100]}...")
        print(f"🎯 Min relevance score: {min_score}")

        # Step 1: Semantic search in Qdrant
        embedding = get_openai_embeddings([keywords])[0]
        client = get_qdrant_client()

        results = client.search(
            collection_name=collection_name,
            query_vector=embedding,
            limit=top_k,
            with_payload=True,
            score_threshold=min_score  # Filtre Qdrant: rejette les résultats < min_score
        )

        if not results:
            return jsonify({
                'error': 'No relevant content found in the database',
                'message': f'No passages found with relevance score above {min_score:.0%}. Try different keywords or lower the threshold.'
            }), 404

        # Step 2: Prepare context for Claude with relevance scores
        context_chunks = []
        for hit in results:
            context_chunks.append({
                'text': hit.payload.get('text', ''),
                'score': hit.score,
                'filename': hit.payload.get('filename', 'unknown'),
                'chunk_id': hit.payload.get('chunk_id', 0)
            })

        # Calculate average relevance score
        avg_score = sum(chunk['score'] for chunk in context_chunks) / len(context_chunks)
        max_score = context_chunks[0]['score']

        print(f"📚 Found {len(context_chunks)} relevant chunks (avg score: {avg_score:.2%}, max: {max_score:.2%})")

        # Build context text with relevance scores visible to Claude
        context_text = "\n\n---\n\n".join([
            f"[Source: {chunk['filename']}, Chunk #{chunk['chunk_id']}, Relevance Score: {chunk['score']:.2%}]\n{chunk['text']}"
            for chunk in context_chunks
        ])

        # Step 3: Call Claude with STRICT anti-hallucination instructions
        prompt = f"""You are an AI assistant helping to extract and generate content from a knowledge base.

TOPIC/KEYWORDS: {keywords}

RELEVANT CONTENT FROM KNOWLEDGE BASE:
{context_text}

USER INSTRUCTIONS:
{instructions}

CRITICAL RULES - YOU MUST FOLLOW THESE:
1. ONLY use information from the passages above
2. DO NOT invent, create, or fabricate any content
3. READ THE ACTUAL CONTENT first before deciding if it's relevant - don't just look at relevance scores
4. ONLY refuse if you actually read the passages and there are NO substantive quotes/content about the topic
5. If relevance scores are above 40%, the content is likely relevant enough - just read it and extract what's valuable
6. Quality over quantity: If the user asks for 5 quotes but only 2 are truly relevant, provide only 2
7. Never make up quotes, statistics, or facts that aren't explicitly in the source material
8. Use this refusal response ONLY if you truly cannot find ANY relevant substantive content after reading:
   "NOT_ENOUGH_RELEVANT_DATA: After reading all passages, I could not find substantive quotes/content about '{keywords}' that meet quality standards."

SPECIAL RULES FOR QUOTE EXTRACTION (if user asks for quotes):
⚠️ CRITICAL: COPY QUOTES EXACTLY AS WRITTEN - DO NOT PARAPHRASE, REFORMULATE, OR MODIFY ANYTHING
- Extract quotes WORD-FOR-WORD from the passages above
- DO NOT change any words, even to make them "sound better"
- DO NOT summarize or shorten quotes - copy them exactly
- DO NOT add your own words or explanations to quotes
- If you must cut a quote for length, use [...] to show removed parts, but what you include must be EXACT
- Include citations/references if they appear in the original quote (e.g., "Smith, 2020")

WHAT TO EXTRACT:
- DO NOT extract section titles, headers, or chapter names
- DO NOT extract questions without their answers
- DO NOT extract incomplete sentences or sentence fragments
- DO NOT extract survey/questionnaire items (e.g., "Item 1:", "Q3:", "Scale 2:", etc.)
- DO NOT extract measurement scales or rating items
- A good quote must be SUBSTANTIVE: it should convey a complete idea, insight, or argument
- A good quote should be at least 10-15 words long (unless it's a truly powerful short statement)
- Prefer quotes that contain explanations, arguments, insights, or actionable advice
- Academic definitions are OK if they are complete and substantive (15+ words with explanation)
- Avoid quotes that are just lists or statements without depth
- Each quote should stand alone and make sense without additional context
- Prioritize quotes with intellectual or practical value
- DO NOT use the examples below - they are just FORMAT illustrations, not real quotes to extract

WHAT TO AVOID (format examples only - DO NOT copy these):
- Avoid: Titles like "Introduction", "The Problem", "Chapter 3"
- Avoid: Questions without answers like "What is leadership?"
- Avoid: Transition words like "In conclusion", "Furthermore"

WHAT A GOOD QUOTE LOOKS LIKE (format examples only - extract from the actual passages above):
- Good format: Complete sentences with insights and explanations (15+ words)
- Good format: Statements that convey wisdom, research findings, or actionable advice
- Good format: Quotes that would be valuable to read even without knowing the context

IMPORTANT: Extract quotes ONLY from the passages provided above. Do NOT use or copy the format examples.

DECISION PROCESS:
1. READ all the passages carefully
2. Look for substantive quotes/content that match the topic
3. If you find at least 1-2 good quotes, extract them (even if fewer than requested)
4. ONLY refuse if you truly find NOTHING relevant after reading all passages
5. Don't refuse just because of relevance scores - read the actual content first!"""

        message = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        generated_content = message.content[0].text.strip()

        # Step 4: Check if Claude refused due to low relevance
        if generated_content.startswith("NOT_ENOUGH_RELEVANT_DATA"):
            print(f"⚠️  Claude refused - insufficient relevant data")
            return jsonify({
                'success': False,
                'error': 'Insufficient relevant data',
                'message': generated_content.replace("NOT_ENOUGH_RELEVANT_DATA: ", ""),
                'chunks_found': len(context_chunks),
                'avg_relevance': avg_score,
                'max_relevance': max_score,
                'sources': [{'filename': c['filename'], 'score': c['score']} for c in context_chunks]
            }), 422  # 422 Unprocessable Entity

        print(f"✅ Content generated ({len(generated_content)} characters)")

        return jsonify({
            'success': True,
            'keywords': keywords,
            'chunks_found': len(context_chunks),
            'avg_relevance': avg_score,
            'max_relevance': max_score,
            'sources': [{'filename': c['filename'], 'score': c['score']} for c in context_chunks],
            'source_chunks': context_chunks,  # Full chunks for verification
            'content': generated_content,
            'usage': {
                'input_tokens': message.usage.input_tokens,
                'output_tokens': message.usage.output_tokens
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/extract-quotes', methods=['POST'])
def extract_quotes():
    """
    Extract the most relevant quotes without any reformulation or translation.

    Body JSON:
    {
        "keywords": "decision-making, founder psychology",
        "collection_name": "pdf_documents",
        "top_k": 10
    }
    """
    try:
        data = request.get_json()
        keywords = data.get('keywords', '')
        collection_name = data.get('collection_name', 'pdf_documents')
        top_k = data.get('top_k', 10)

        if not keywords:
            return jsonify({'error': 'Keywords required'}), 400

        print(f"🔍 Extracting quotes for: '{keywords}'")

        # Step 1: Semantic search in Qdrant (automatically takes best matches)
        embedding = get_openai_embeddings([keywords])[0]
        client = get_qdrant_client()

        results = client.search(
            collection_name=collection_name,
            query_vector=embedding,
            limit=top_k,
            with_payload=True
        )

        if not results:
            return jsonify({'error': 'No content found'}), 404

        # Step 2: Use Claude to extract only pure quotes with authors
        # Prepare context for Claude with chunk IDs
        context_chunks = []
        for i, hit in enumerate(results):
            context_chunks.append({
                'chunk_id': i,
                'text': hit.payload.get('text', ''),
                'filename': hit.payload.get('filename', 'unknown'),
                'score': hit.score
            })

        context_text = "\n\n---\n\n".join([
            f"[CHUNK_{chunk['chunk_id']}] [Source: {chunk['filename']}, Relevance: {chunk['score']:.2f}]\n{chunk['text']}"
            for chunk in context_chunks
        ])

        # Ask Claude to extract only quotes with authors in JSON format
        prompt = f"""Extract the 3-5 best quotes related to "{keywords}" from these sources.

{context_text}

Return a valid JSON array. Each quote must have:
- quote: the exact text
- author: author name or document name
- chunk_id: number from 0 to {len(context_chunks)-1}

Example format:
[
  {{"quote": "example text", "author": "John Doe", "chunk_id": 0}}
]

Requirements:
- Use the chunk_id from [CHUNK_X] markers
- Keep quotes short (1-3 sentences max)
- Return ONLY valid JSON, no explanations"""

        message = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text.strip()

        # Parse JSON response
        import json
        import re

        print(f"📝 Claude response:\n{response_text}\n")

        # Extract JSON from response (in case there's extra text)
        json_match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
        quotes_json = []

        if json_match:
            try:
                quotes_json = json.loads(json_match.group())
                print(f"✅ Successfully parsed {len(quotes_json)} quotes")
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON parse error: {e}")
                print(f"Raw JSON: {json_match.group()[:500]}")
                # Fallback: try to extract quotes manually from the text
                quotes_json = []
        else:
            print("⚠️  No JSON array found in response")

        # Format as markdown with relevance scores
        markdown_lines = [f"# {keywords}", ""]

        if quotes_json:
            # Use Claude's extracted quotes
            for item in quotes_json:
                quote = item.get('quote', '')
                author = item.get('author', 'Unknown')
                chunk_id = item.get('chunk_id', 0)

                # Get the relevance score from the original chunk
                relevance = context_chunks[chunk_id]['score'] if chunk_id < len(context_chunks) else 0

                markdown_lines.append(f'> "{quote}"')
                markdown_lines.append(f"— {author} ({relevance:.1%} relevance)")
                markdown_lines.append("")

            print(f"✅ {len(quotes_json)} quotes extracted from Claude")
        else:
            # Fallback: return direct chunks from Qdrant
            print("⚠️  Falling back to direct Qdrant results")
            for i, chunk in enumerate(context_chunks[:5]):  # Limit to top 5
                text = chunk['text'][:300]  # First 300 chars
                markdown_lines.append(f'> {text}...')
                markdown_lines.append(f"— {chunk['filename']} ({chunk['score']:.1%} relevance)")
                markdown_lines.append("")

        markdown_content = "\n".join(markdown_lines)

        return jsonify({
            'success': True,
            'keywords': keywords,
            'quotes_count': len(results),
            'markdown': markdown_content,
            'sources': [
                {
                    'filename': hit.payload.get('filename'),
                    'score': hit.score,
                    'text_preview': hit.payload.get('text', '')[:200] + '...'
                }
                for hit in results
            ]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/obsidian-converter')
def obsidian_converter():
    """Page du convertisseur Obsidian."""
    return render_template('obsidian_converter.html')


@app.route('/obsidian-convert', methods=['POST'])
def obsidian_convert():
    """Convertir un PDF avec le convertisseur Obsidian (pdfplumber)."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are accepted'}), 400

    try:
        # Create unique job ID
        job_id = str(uuid.uuid4())

        # Save file
        filename = secure_filename(file.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
        file.save(pdf_path)

        # Initialize Obsidian converter with LlamaParse fallback
        converter = ObsidianPDFConverter(
            vault_root=app.config['UPLOAD_FOLDER'],
            llamaparse_api_key=LLAMA_CLOUD_API_KEY
        )

        # Convert PDF
        print(f"[Obsidian] Converting {filename}...")
        success = converter.convert_pdf(Path(pdf_path), force=True)

        if not success:
            return jsonify({'error': 'Conversion failed'}), 500

        # Get conversion info from tracking data
        pdf_rel_path = Path(pdf_path).name
        tracking_info = converter.tracking_data['processed'].get(pdf_rel_path, {})

        # Read markdown file
        md_path = Path(pdf_path).with_suffix('.md')
        with open(md_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

        # Get preview (first 50 lines)
        lines = markdown_content.split('\n')
        preview = '\n'.join(lines[:50])
        if len(lines) > 50:
            preview += f'\n\n... ({len(lines) - 50} more lines)'

        # Store conversion info
        obsidian_conversions[job_id] = {
            'filename': filename,
            'pdf_path': str(pdf_path),
            'md_path': str(md_path),
            'tracking_info': tracking_info
        }

        return jsonify({
            'success': True,
            'job_id': job_id,
            'filename': filename,
            'category': tracking_info.get('category', 'general'),
            'tags': tracking_info.get('tags', []),
            'pages': tracking_info.get('pages', 0) if isinstance(tracking_info.get('pages'), int) else 0,
            'markdown_size': len(markdown_content),
            'preview': preview,
            'method': tracking_info.get('method', 'unknown')  # Add conversion method
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/obsidian-download/<job_id>')
def obsidian_download(job_id):
    """Download converted Obsidian markdown."""
    if job_id not in obsidian_conversions:
        return jsonify({'error': 'Job not found'}), 404

    conversion = obsidian_conversions[job_id]
    md_path = conversion['md_path']

    if not os.path.exists(md_path):
        return jsonify({'error': 'File not found'}), 404

    return send_file(
        md_path,
        as_attachment=True,
        download_name=Path(md_path).name
    )


@app.route('/database-overview')
def database_overview():
    """Page d'aperçu de la base de données."""
    return render_template('database_overview.html')


@app.route('/api/database/documents')
def get_all_documents():
    """
    Récupérer tous les documents de la base de données avec leurs métadonnées.

    Query params:
    - collection_name: nom de la collection (défaut: pdf_documents)
    - limit: nombre de documents à retourner (défaut: 100)
    - offset: décalage pour la pagination (défaut: 0)
    """
    try:
        collection_name = request.args.get('collection_name', 'pdf_documents')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        client = get_qdrant_client()

        # Vérifier si la collection existe
        try:
            collection_info = client.get_collection(collection_name)
            total_count = collection_info.points_count
        except Exception:
            return jsonify({
                'error': f'Collection "{collection_name}" not found',
                'documents': [],
                'total': 0
            }), 404

        # Récupérer les documents avec scroll (pagination efficace)
        points, next_offset = client.scroll(
            collection_name=collection_name,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False  # Pas besoin des vecteurs pour l'aperçu
        )

        # Organiser les documents par fichier
        documents_by_file = {}
        for point in points:
            filename = point.payload.get('filename', 'Unknown')
            if filename not in documents_by_file:
                documents_by_file[filename] = {
                    'filename': filename,
                    'chunks': [],
                    'total_tokens': 0,
                    'total_chars': 0,
                    'chunk_count': 0,
                    'job_id': point.payload.get('job_id'),
                    'source': point.payload.get('source', 'unknown')
                }

            documents_by_file[filename]['chunks'].append({
                'id': point.id,
                'chunk_id': point.payload.get('chunk_id'),
                'text_preview': point.payload.get('text', '')[:200] + '...' if len(point.payload.get('text', '')) > 200 else point.payload.get('text', ''),
                'token_count': point.payload.get('token_count', 0),
                'char_count': point.payload.get('char_count', 0)
            })

            documents_by_file[filename]['total_tokens'] += point.payload.get('token_count', 0)
            documents_by_file[filename]['total_chars'] += point.payload.get('char_count', 0)
            documents_by_file[filename]['chunk_count'] += 1

        # Convertir en liste
        documents = list(documents_by_file.values())

        # Trier par nombre de chunks (documents les plus importants en premier)
        documents.sort(key=lambda x: x['chunk_count'], reverse=True)

        return jsonify({
            'collection_name': collection_name,
            'documents': documents,
            'total_documents': len(documents),
            'total_chunks': len(points),
            'total_chunks_in_collection': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': next_offset is not None
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/documents/list')
def list_unique_documents():
    """
    Liste TOUS les documents uniques dans la collection (scalable).
    Retourne seulement les métadonnées de base sans charger tout le contenu.

    Query params:
    - collection_name: nom de la collection (défaut: pdf_documents)
    - search: terme de recherche pour filtrer par nom de fichier (optionnel)
    """
    try:
        collection_name = request.args.get('collection_name', 'pdf_documents')
        search_term = request.args.get('search', '').lower()

        client = get_qdrant_client()

        # Vérifier si la collection existe
        try:
            collection_info = client.get_collection(collection_name)
            total_chunks = collection_info.points_count
        except Exception:
            return jsonify({
                'error': f'Collection "{collection_name}" not found',
                'documents': []
            }), 404

        # Scanner TOUS les chunks pour extraire les noms de fichiers uniques
        # Utiliser scroll avec limit élevé pour être efficace
        documents_dict = {}
        offset = None

        while True:
            # Scroll en batches de 1000 (efficace sans charger tout en mémoire)
            points, offset = client.scroll(
                collection_name=collection_name,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            # Extraire les métadonnées de chaque point
            for point in points:
                filename = point.payload.get('filename', 'Unknown')

                # Filtrer par recherche si spécifié
                if search_term and search_term not in filename.lower():
                    continue

                if filename not in documents_dict:
                    documents_dict[filename] = {
                        'filename': filename,
                        'chunk_count': 0,
                        'total_tokens': 0,
                        'source': point.payload.get('source', 'unknown'),
                        'job_id': point.payload.get('job_id', 'unknown')
                    }

                documents_dict[filename]['chunk_count'] += 1
                documents_dict[filename]['total_tokens'] += point.payload.get('token_count', 0)

            # Si plus de résultats, arrêter
            if offset is None:
                break

        # Convertir en liste et trier
        documents = list(documents_dict.values())
        documents.sort(key=lambda x: x['chunk_count'], reverse=True)

        return jsonify({
            'collection_name': collection_name,
            'documents': documents,
            'total_documents': len(documents),
            'total_chunks': total_chunks,
            'search_term': search_term if search_term else None
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/stats')
def get_database_stats():
    """Obtenir les statistiques globales de la base de données."""
    try:
        client = get_qdrant_client()
        collections = client.get_collections().collections

        stats = {
            'collections': [],
            'total_vectors': 0
        }

        for col in collections:
            info = client.get_collection(col.name)
            stats['collections'].append({
                'name': col.name,
                'vectors_count': info.points_count,
                'vector_size': info.config.params.vectors.size if hasattr(info.config.params, 'vectors') else 0
            })
            stats['total_vectors'] += info.points_count

        return jsonify(stats)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("APPLICATION WEB LLAMAPARSE - PDF TO MARKDOWN")
    print("=" * 60)
    print("\n🚀 Démarrage de l'application...")

    # Get port from environment variable (for Render deployment)
    port = int(os.environ.get('PORT', 8080))

    print(f"\nAccédez à l'application sur: http://localhost:{port}")
    print("\nAppuyez sur Ctrl+C pour arrêter le serveur")
    print("=" * 60 + "\n")

    # In production (Render), debug should be False and use gunicorn
    # For local development, use debug=True
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
