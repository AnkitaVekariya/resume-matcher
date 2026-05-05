from flask import Flask, render_template, request
import re
import os
import PyPDF2
import docx2txt
import numpy as np
from sentence_transformers import SentenceTransformer, util

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'

# 🔥 Load model once
model = SentenceTransformer('all-MiniLM-L6-v2')

# 🔥 Skill database (expand anytime)
skills_list = [
    "python", "java", "c++", "machine learning", "deep learning",
    "data science", "sql", "flask", "django", "html", "css",
    "javascript", "react", "node", "nlp", "pandas", "numpy",
    "tensorflow", "pytorch", "excel", "aws", "docker"
]


# -------------------------------
# Helper Functions
# -------------------------------

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z ]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_skills(text):
    found = []
    for skill in skills_list:
        if skill in text:
            found.append(skill)
    return found


def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text


def extract_text_from_docx(file_path):
    return docx2txt.process(file_path)


def extract_text_from_txt(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


def extract_text(file_path):
    if file_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith(".docx"):
        return extract_text_from_docx(file_path)
    elif file_path.endswith(".txt"):
        return extract_text_from_txt(file_path)
    return ""


# -------------------------------
# Routes
# -------------------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/matcher", methods=["POST"])
def matcher():

    job_description = request.form.get("job_description")
    resumes_files = request.files.getlist("resumes")

    if not resumes_files or not job_description:
        return render_template("index.html", message="Please upload resumes and job description")

    resumes = []
    filenames = []
    resume_skills_list = []

    # 🔧 Process resumes
    for file in resumes_files:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        text = extract_text(filepath)
        text = clean_text(text)

        if text.strip():
            resumes.append(text)
            filenames.append(file.filename)
            resume_skills_list.append(extract_skills(text))

    if not resumes:
        return render_template("index.html", message="No valid resume content found")

    # 🔧 Clean JD
    job_description = clean_text(job_description)

    # 🔥 Extract JD skills
    jd_skills = extract_skills(job_description)

    # 🔥 BERT similarity
    jd_embedding = model.encode(job_description, convert_to_tensor=True)
    resume_embeddings = model.encode(resumes, convert_to_tensor=True)

    similarities = util.cos_sim(jd_embedding, resume_embeddings)[0].cpu().numpy()

    # 🔥 Skill score
    skill_scores = []
    for r_skills in resume_skills_list:
        if len(jd_skills) == 0:
            score = 0
        else:
            score = len(set(jd_skills) & set(r_skills)) / len(jd_skills)
        skill_scores.append(score)

    # 🔥 Combine scores (HYBRID MODEL)
    final_scores = []
    for i in range(len(similarities)):
        final = (0.7 * similarities[i]) + (0.3 * skill_scores[i])
        final_scores.append(final)

    final_scores = np.array(final_scores)

    # 🔝 Ranking
    top_indices = final_scores.argsort()[-3:][::-1]

    top_resumes = [filenames[i] for i in top_indices]
    similarity_score = [round(final_scores[i] * 100, 2) for i in top_indices]

    # 🔥 Matched + Missing Skills
    matched_skills = []
    missing_skills = []

    for i in top_indices:
        matched = list(set(jd_skills) & set(resume_skills_list[i]))
        missing = list(set(jd_skills) - set(resume_skills_list[i]))

        matched_skills.append(matched)
        missing_skills.append(missing)

    return render_template(
        "index.html",
        message="Top matching resumes:",
        top_resumes=top_resumes,
        similarity_score=similarity_score,
        matched_skills=matched_skills,
        missing_skills=missing_skills
    )


# -------------------------------
# Run App
# -------------------------------

if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    app.run(debug=True)