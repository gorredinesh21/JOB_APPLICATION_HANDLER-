import json
import subprocess
import os
from jinja2 import Environment, FileSystemLoader

# =========================================================
# 🔧 CONFIGURATION
# =========================================================
CONFIG = {
    "JSON_PATH": "data_schema.json",
    "TEMPLATE_PATH": "standard_template.tex",
    "BUILD_DIR": "build",
    "OUTPUT_PDF": "generated_resume.pdf",
    "LATEX_COMPILER": "pdflatex"
}

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
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"[ERROR] JSON file not found: {json_path}")

    with open(json_path, "r") as f:
        data = json.load(f)

    return sanitize_data(data)

# =========================================================
# 🧩 Render LaTeX template
# =========================================================
def render_latex(data, template_path, output_tex):

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"[ERROR] Template not found: {template_path}")

    env = Environment(
        loader=FileSystemLoader("."),
        block_start_string='<<%',
        block_end_string='%>>',
        variable_start_string='<<',
        variable_end_string='>>',
        comment_start_string='<#',
        comment_end_string='#>',
        autoescape=False
    )

    template = env.get_template(template_path)
    rendered_tex = template.render(**data)

    with open(output_tex, "w") as f:
        f.write(rendered_tex)

    print(f"[✓] Generated LaTeX file: {output_tex}")

# =========================================================
# 📄 Compile PDF
# =========================================================
def compile_pdf(tex_file, build_dir, output_pdf, compiler="pdflatex"):

    if not os.path.exists(build_dir):
        os.makedirs(build_dir)

    try:
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

        if result.returncode != 0:
            print("[✗] LaTeX compilation failed!")
            print("\n===== LATEX OUTPUT =====\n")
            print(result.stdout)
            print("\n========================\n")
            return

        generated_pdf = os.path.join(
            build_dir,
            os.path.basename(tex_file).replace(".tex", ".pdf")
        )

        final_pdf_path = os.path.join(".", output_pdf)

        os.replace(generated_pdf, final_pdf_path)

        print(f"[✓] PDF generated: {final_pdf_path}")

    except Exception as e:
        print(f"[✗] Error running LaTeX: {e}")

# =========================================================
# 🚀 MAIN
# =========================================================
def main():

    json_path = CONFIG["JSON_PATH"]
    template_path = CONFIG["TEMPLATE_PATH"]
    build_dir = CONFIG["BUILD_DIR"]
    output_pdf = CONFIG["OUTPUT_PDF"]
    compiler = CONFIG["LATEX_COMPILER"]

    output_tex = os.path.join(build_dir, "temporary.tex")

    print("[INFO] Loading JSON data...")
    data = load_json(json_path)

    print("[INFO] Rendering LaTeX template...")
    render_latex(data, template_path, output_tex)

    print("[INFO] Compiling PDF...")
    compile_pdf(output_tex, build_dir, output_pdf, compiler)

# =========================================================
if __name__ == "__main__":
    main()
