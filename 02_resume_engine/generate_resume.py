import json
import subprocess
import os
import argparse
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

# =========================================================
# 🔧 CONFIGURATION
# =========================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    "JSON_ROOT": os.path.join(SCRIPT_DIR, "LLM_GENERATED_JSONS"),
    "OUTPUT_ROOT": os.path.join(SCRIPT_DIR, "LLM_COMPILED_PDFS"),
    "TEMPLATE_PATH": os.path.join(SCRIPT_DIR, "standard_template.tex"),
    "BUILD_DIR": os.path.join(SCRIPT_DIR, "build"),
    "LATEX_COMPILER": os.getenv("LATEX_COMPILER", "pdflatex")
}


def parse_args():
    parser = argparse.ArgumentParser(description="Compile tailored resume JSON files to PDFs.")
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Compile JSON files for this date in YYYY-MM-DD format.",
    )
    return parser.parse_args()

# =========================================================
# 🧠 Escape LaTeX special characters
# =========================================================
def escape_latex(text):
    if not isinstance(text, str):
        return text

    replacements = {
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}"
    }

    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    return text

# =========================================================
# 🧠 Recursively sanitize JSON
# =========================================================
def sanitize_data(data):
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(i) for i in data]
    elif isinstance(data, str):
        return escape_latex(data)
    else:
        return data

# =========================================================
# 📥 Load JSON
# =========================================================
def load_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return sanitize_data(data)

# =========================================================
# 🧩 Render LaTeX template
# =========================================================
def render_latex(data, template_path, output_tex):

    env = Environment(
        loader=FileSystemLoader(os.path.dirname(template_path)),
        block_start_string='<<%',
        block_end_string='%>>',
        variable_start_string='<<',
        variable_end_string='>>',
        comment_start_string='<#',
        comment_end_string='#>',
        autoescape=False
    )

    template = env.get_template(os.path.basename(template_path))
    rendered_tex = template.render(**data)

    with open(output_tex, "w") as f:
        f.write(rendered_tex)

# =========================================================
# 📄 Compile PDF
# =========================================================
def compile_pdf(tex_file, build_dir, output_pdf, compiler="pdflatex"):

    result = subprocess.run(
        [
            compiler,
            "-interaction=nonstopmode",
            "-output-directory", build_dir,
            tex_file
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    generated_pdf = os.path.join(
        build_dir,
        os.path.basename(tex_file).replace(".tex", ".pdf")
    )

    if not os.path.exists(generated_pdf):
        print("[✗] PDF not generated")
        return False

    os.replace(generated_pdf, output_pdf)
    return True

# =========================================================
# 🚀 MAIN
# =========================================================
def main():
    args = parse_args()

    json_dir = os.path.join(CONFIG["JSON_ROOT"], args.date)
    output_dir = os.path.join(CONFIG["OUTPUT_ROOT"], args.date)
    build_dir = CONFIG["BUILD_DIR"]

    # 🔥 Check JSON folder exists
    if not os.path.exists(json_dir):
        print(f"[INFO] No JSON folder found for today: {json_dir}")
        return

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(build_dir, exist_ok=True)

    json_files = [f for f in os.listdir(json_dir) if f.endswith(".json")]

    print(f"[INFO] Found {len(json_files)} JSON files")

    failed_count = 0

    for i, json_file in enumerate(json_files):

        print(f"[{i}] Processing: {json_file}")

        try:
            json_path = os.path.join(json_dir, json_file)
            data = load_json(json_path)

            tex_path = os.path.join(build_dir, "temporary.tex")

            render_latex(data, CONFIG["TEMPLATE_PATH"], tex_path)

            pdf_name = json_file.replace(".json", ".pdf")
            output_pdf_path = os.path.join(output_dir, pdf_name)

            success = compile_pdf(
                tex_path,
                build_dir,
                output_pdf_path,
                CONFIG["LATEX_COMPILER"]
            )

            if success:
                print(f"[✓] Generated: {output_pdf_path}")
            else:
                print(f"[✗] Failed: {json_file}")
                failed_count += 1

        except Exception as e:
            print(f"[✗] Error processing {json_file}: {e}")
            failed_count += 1

    print("\n==============================")
    print(f"[INFO] Total failures: {failed_count}")
    print("==============================")

# =========================================================
if __name__ == "__main__":
    main()
