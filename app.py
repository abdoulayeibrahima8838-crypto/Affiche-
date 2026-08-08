"""
Affiche+ — Backend Flask
Génère des affiches publicitaires à partir d'une photo produit + infos texte,
via l'API Gemini (modèle image "Nano Banana").

INSTALLATION LOCALE :
    pip install flask google-genai pillow python-dotenv --break-system-packages

VARIABLES D'ENVIRONNEMENT (à définir sur Render, ou dans un fichier .env en local) :
    GEMINI_API_KEY   -> ta clé API Gemini (aistudio.google.com)

LANCEMENT LOCAL :
    python3 app.py
    puis ouvre http://localhost:5000

DÉPLOIEMENT RENDER (comme Fisca AI) :
    - Build command : pip install -r requirements.txt
    - Start command : gunicorn app:app
    - Ajouter la variable d'environnement GEMINI_API_KEY dans les settings du service
"""

import os
import uuid
import base64
from flask import Flask, render_template, request, jsonify, send_from_directory
from PIL import Image
from google import genai

app = Flask(__name__)

UPLOAD_DIR = os.path.join(app.root_path, "static", "uploads")
GENERATED_DIR = os.path.join(app.root_path, "static", "generated")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)

# ---- Bibliothèque de styles (MVP : 4 styles fixes, comme dans la maquette) ----
STYLES = {
    "sobre":    "style sobre et élégant, tons neutres, typographie fine, épuré",
    "festif":   "style coloré et festif, fond dynamique, ambiance vivante et chaleureuse",
    "artisanal": "style nature et artisanal, textures organiques, tons terreux, authentique",
    "premium":  "style moderne et premium, fond dégradé sophistiqué, finitions soignées",
}

CATEGORIES = {
    "boutique": "affiche publicitaire pour un produit à vendre sur les réseaux sociaux (WhatsApp Statut / Instagram)",
    "evenement": "affiche d'invitation pour un événement (mariage, baptême, anniversaire, fête)",
}


def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY n'est pas configurée dans les variables d'environnement.")
    return genai.Client(api_key=api_key)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """
    Reçoit : photo (fichier), category, style, titre, prix_date, contact
    Retourne : JSON avec l'URL de l'affiche générée, ou une erreur claire.
    """
    try:
        photo = request.files.get("photo")
        category = request.form.get("category", "boutique")
        style_key = request.form.get("style", "sobre")
        titre = request.form.get("titre", "").strip()
        prix_date = request.form.get("prix_date", "").strip()
        contact = request.form.get("contact", "").strip()

        if not photo:
            return jsonify({"ok": False, "error": "Aucune photo reçue."}), 400
        if not titre:
            return jsonify({"ok": False, "error": "Le titre est obligatoire."}), 400

        # Sauvegarde temporaire de la photo uploadée
        ext = os.path.splitext(photo.filename)[1] or ".jpg"
        upload_name = f"{uuid.uuid4().hex}{ext}"
        upload_path = os.path.join(UPLOAD_DIR, upload_name)
        photo.save(upload_path)

        image_produit = Image.open(upload_path)
        style_desc = STYLES.get(style_key, STYLES["sobre"])
        contexte = CATEGORIES.get(category, CATEGORIES["boutique"])

        prompt = f"""
        Crée une {contexte}.

        Utilise la photo fournie en gardant le sujet bien visible et net.
        Style visuel : {style_desc}.
        Ajoute un fond attrayant qui met en valeur le sujet sans le cacher.

        Intègre ces textes de façon lisible et bien positionnée sur l'affiche :
        - Titre : "{titre}"
        {f'- Prix ou date : "{prix_date}"' if prix_date else ""}
        {f'- Contact : "{contact}"' if contact else ""}

        Format carré, adapté pour un post Instagram ou un statut WhatsApp.
        """

        client = get_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt, image_produit],
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                output_name = f"{uuid.uuid4().hex}.png"
                output_path = os.path.join(GENERATED_DIR, output_name)
                with open(output_path, "wb") as f:
                    f.write(part.inline_data.data)
                return jsonify({
                    "ok": True,
                    "url": f"/static/generated/{output_name}"
                })

        return jsonify({"ok": False, "error": "Le modèle n'a pas renvoyé d'image. Réessaie."}), 502

    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": f"Erreur inattendue : {e}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
