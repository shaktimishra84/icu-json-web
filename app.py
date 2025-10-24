from pathlib import Path
import json, re, streamlit as st

st.set_page_config(page_title="ICU JSON Viewer", layout="wide")

DATA_DIR = Path(__file__).parent / "data" / "algorithms"
files = sorted(DATA_DIR.glob("*.json"))
if not files:
    st.error(f"No JSONs found in {DATA_DIR}"); st.stop()

def pretty(p: Path):
    n = re.sub(r"\.json$", "", p.name, flags=re.I)
    n = re.sub(r"\.(final|fixed|clean|polished|v\d+)+", "", n, flags=re.I)
    return re.sub(r"^\d+_", "", n).replace("_", " ")

st.sidebar.title("ICU JSON Viewer")
q = st.sidebar.text_input("Search")
view = [p for p in files if (q.lower() in p.name.lower())] if q else files

choice = st.sidebar.selectbox("File", view, index=0, format_func=pretty)
st.header(pretty(choice))
st.json(json.loads(choice.read_text(encoding="utf-8")), expanded=False)
